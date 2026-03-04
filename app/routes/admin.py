from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify, abort
from functools import wraps
from app import get_db, CONTACT_SETTINGS_DEFAULTS
import os, re, uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

admin = Blueprint('admin', __name__)
ALLOWED = {'png','jpg','jpeg','webp','gif'}

def allowed_file(f):
    return '.' in f and f.rsplit('.',1)[1].lower() in ALLOWED

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[\s_]+','-',text)
    text = re.sub(r'[^\w-]','',text)
    return text

def login_required(f):
    @wraps(f)
    def decorated(*args,**kwargs):
        if not session.get('admin_id'):
            return redirect(url_for('admin.login'))
        return f(*args,**kwargs)
    return decorated

def get_upload_folder():
    from flask import current_app
    return current_app.config['UPLOAD_FOLDER']

def get_banner_upload_folder():
    from flask import current_app
    return current_app.config['BANNER_UPLOAD_FOLDER']

def save_file(file, upload_folder=None):
    if not file or not file.filename or not allowed_file(file.filename):
        return None
    ext = file.filename.rsplit('.',1)[1].lower()
    fname = f"{uuid.uuid4().hex}.{ext}"
    target = upload_folder or get_upload_folder()
    os.makedirs(target, exist_ok=True)
    file.save(os.path.join(target, fname))
    return fname

def delete_file(fname, upload_folder=None):
    if not fname: return
    try:
        target = upload_folder or get_upload_folder()
        p = os.path.join(target, fname)
        if os.path.exists(p): os.remove(p)
    except: pass

def _sync_primary_image(db, pid):
    imgs = db.execute(
        'SELECT id,image_path,is_primary FROM product_images '
        'WHERE product_id=? ORDER BY is_primary DESC, order_index, id',
        (pid,)
    ).fetchall()
    if not imgs:
        db.execute('UPDATE product SET image=NULL WHERE id=?', (pid,))
        return None

    primary = None
    for img in imgs:
        if img['is_primary']:
            primary = img
            break
    if primary is None:
        primary = imgs[0]
        db.execute('UPDATE product_images SET is_primary=0 WHERE product_id=?', (pid,))
        db.execute('UPDATE product_images SET is_primary=1 WHERE id=?', (primary['id'],))

    db.execute('UPDATE product SET image=? WHERE id=?', (primary['image_path'], pid))
    return primary['id']

def si(v):
    try: return int(v) if v not in (None,'') else None
    except: return None

def sf(v):
    try: return float(v) if v not in (None,'') else None
    except: return None


def _parent_category_nodes(db, exclude_id=None):
    rows = [dict(r) for r in db.execute(
        'SELECT id,name,icon,parent_id,sort_order FROM category ORDER BY sort_order, name'
    ).fetchall()]
    by_parent = {}
    for row in rows:
        row['id'] = int(row['id'])
        row['parent_id'] = int(row['parent_id']) if row.get('parent_id') not in (None, '') else None
        by_parent.setdefault(row['parent_id'], []).append(row)

    blocked = set()
    if exclude_id:
        exclude_id = int(exclude_id)
        blocked.add(exclude_id)
        stack = [exclude_id]
        while stack:
            node_id = stack.pop()
            for child in by_parent.get(node_id, []):
                cid = int(child['id'])
                if cid in blocked:
                    continue
                blocked.add(cid)
                stack.append(cid)

    result = []
    visited = set()

    def option_label(icon, name, depth):
        title = f"{(icon or '').strip()} {name}".strip()
        if depth <= 0:
            return title
        branch = ('|   ' * (depth - 1)) + '|-- '
        return f'{branch}{title}'

    def walk(parent_id, depth):
        for node in by_parent.get(parent_id, []):
            nid = int(node['id'])
            if nid in visited or nid in blocked:
                continue
            visited.add(nid)
            result.append({
                'id': nid,
                'name': node['name'],
                'icon': (node.get('icon') or '').strip(),
                'parent_id': node['parent_id'],
                'depth': depth,
                'label': option_label(node.get('icon'), node['name'], depth),
            })
            walk(nid, depth + 1)

    walk(None, 0)

    for node in rows:
        nid = int(node['id'])
        if nid in visited or nid in blocked:
            continue
        result.append({
            'id': nid,
            'name': node['name'],
            'icon': (node.get('icon') or '').strip(),
            'parent_id': node['parent_id'],
            'depth': 0,
            'label': option_label(node.get('icon'), node['name'], 0),
        })
        walk(nid, 1)

    return result


def _root_type_nodes(db):
    return db.execute(
        'SELECT * FROM category '
        'WHERE parent_id IS NULL '
        'ORDER BY sort_order, name'
    ).fetchall()


def _preferred_product_category_id(db, cat_ids):
    selected = []
    seen = set()
    for raw in cat_ids or []:
        try:
            cid = int(raw)
        except Exception:
            continue
        if cid <= 0 or cid in seen:
            continue
        seen.add(cid)
        selected.append(cid)
    if not selected:
        return None

    parent_by_id = {
        int(r['id']): (int(r['parent_id']) if r['parent_id'] not in (None, '') else None)
        for r in db.execute('SELECT id,parent_id FROM category').fetchall()
    }
    depth_cache = {}

    def depth_of(cid):
        if cid in depth_cache:
            return depth_cache[cid]
        depth = 0
        seen_local = set()
        cur = cid
        while cur in parent_by_id and cur not in seen_local:
            seen_local.add(cur)
            parent_id = parent_by_id.get(cur)
            if parent_id is None:
                break
            depth += 1
            cur = parent_id
        depth_cache[cid] = depth
        return depth

    valid_selected = [cid for cid in selected if cid in parent_by_id]
    if not valid_selected:
        return None
    pos = {cid: idx for idx, cid in enumerate(selected)}
    return max(valid_selected, key=lambda cid: (depth_of(cid), -pos.get(cid, 0)))


def _next_category_sort_order(db, parent_id=None, exclude_id=None):
    where = ['1=1']
    params = []
    if parent_id:
        where.append('parent_id=?')
        params.append(parent_id)
    else:
        where.append('parent_id IS NULL')
    if exclude_id:
        where.append('id<>?')
        params.append(exclude_id)
    row = db.execute(
        f"SELECT COALESCE(MAX(sort_order), 0) + 1 FROM category WHERE {' AND '.join(where)}",
        params
    ).fetchone()
    return int(row[0] or 1)


def _category_sort_preview(db, parent_id=None, exclude_id=None, limit=8):
    where = ['1=1']
    params = []
    if parent_id:
        where.append('parent_id=?')
        params.append(parent_id)
    else:
        where.append('parent_id IS NULL')
    if exclude_id:
        where.append('id<>?')
        params.append(exclude_id)
    params.append(limit)
    return db.execute(
        f'SELECT id,name,sort_order FROM category '
        f"WHERE {' AND '.join(where)} "
        'ORDER BY sort_order, name LIMIT ?',
        params
    ).fetchall()


def _category_subtree_ids(db, parent_id):
    if not parent_id:
        return []
    rows = db.execute(
        'WITH RECURSIVE tree(id) AS ('
        '  SELECT ? '
        '  UNION ALL '
        '  SELECT c.id FROM category c JOIN tree t ON c.parent_id=t.id'
        ') '
        'SELECT id FROM tree',
        (parent_id,)
    ).fetchall()
    return [int(r['id']) for r in rows]


def _products_by_parent_category(db, parent_id, include_assigned=False, current_category_id=None):
    if not parent_id:
        return []
    subtree_ids = _category_subtree_ids(db, parent_id)
    if not subtree_ids:
        return []

    ph = ','.join(['?'] * len(subtree_ids))
    rows = db.execute(
        f'SELECT DISTINCT p.id,p.name,p.image,p.is_active,c.name as cat_name,c.icon as cat_icon '
        f'FROM product p '
        f'LEFT JOIN category c ON c.id=p.category_id '
        f'JOIN product_categories pc ON pc.product_id=p.id '
        f'WHERE pc.category_id IN ({ph}) '
        f'ORDER BY p.is_active DESC, p.id DESC',
        subtree_ids
    ).fetchall()

    excluded = {int(parent_id)}
    if current_category_id:
        excluded.add(int(current_category_id))
    other_category_ids = [cid for cid in subtree_ids if cid not in excluded]
    category_display_ids = [cid for cid in subtree_ids if cid != int(parent_id)]

    assigned_elsewhere_ids = set()
    if other_category_ids:
        ph_other = ','.join(['?'] * len(other_category_ids))
        linked = db.execute(
            f'SELECT DISTINCT product_id FROM product_categories '
            f'WHERE category_id IN ({ph_other})',
            other_category_ids
        ).fetchall()
        assigned_elsewhere_ids = {int(r['product_id']) for r in linked}

    product_categories_map = {}
    if category_display_ids:
        ph_display = ','.join(['?'] * len(category_display_ids))
        links = db.execute(
            f'SELECT pc.product_id, c.name '
            f'FROM product_categories pc '
            f'JOIN category c ON c.id=pc.category_id '
            f'WHERE pc.category_id IN ({ph_display}) '
            f'ORDER BY c.sort_order, c.name',
            category_display_ids
        ).fetchall()
        for row in links:
            pid = int(row['product_id'])
            name = (row['name'] or '').strip()
            if not name:
                continue
            product_categories_map.setdefault(pid, [])
            if name not in product_categories_map[pid]:
                product_categories_map[pid].append(name)

    result = []
    for r in rows:
        item = dict(r)
        assigned_cats = product_categories_map.get(int(r['id']), [])
        item['assigned_categories'] = assigned_cats
        item['assigned_categories_text'] = ', '.join(assigned_cats)
        item['assigned_elsewhere'] = 1 if int(r['id']) in assigned_elsewhere_ids else 0
        if include_assigned or not item['assigned_elsewhere']:
            result.append(item)
    return result


def normalize_promo_input(v, end_of_day=False):
    raw = (v or '').strip()
    if not raw:
        return None
    raw = raw.replace(' ', 'T')
    if 'T' not in raw:
        raw = f"{raw}T23:59:59" if end_of_day else f"{raw}T00:00:00"
    try:
        dt = datetime.fromisoformat(raw)
        return dt.replace(microsecond=0).isoformat(timespec='seconds')
    except Exception:
        return None

# ── LOGIN ──────────────────────────────────────────────────────────────
@admin.route('/login', methods=['GET','POST'])
def login():
    if session.get('admin_id'): return redirect(url_for('admin.dashboard'))
    if request.method == 'POST':
        db = get_db()
        u = db.execute('SELECT * FROM admin WHERE username=?',(request.form['username'],)).fetchone()
        if u and check_password_hash(u['password_hash'], request.form['password']):
            session['admin_id'] = u['id']
            return redirect(url_for('admin.dashboard'))
        flash("Noto'g'ri login yoki parol!",'error')
    return render_template('admin/login.html')

@admin.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin.login'))

# ── DASHBOARD ──────────────────────────────────────────────────────────
@admin.route('/')
@login_required
def dashboard():
    db = get_db()
    stats = {
        'products': db.execute('SELECT COUNT(*) FROM product').fetchone()[0],
        'active': db.execute('SELECT COUNT(*) FROM product WHERE is_active=1').fetchone()[0],
        'categories': db.execute('SELECT COUNT(*) FROM category').fetchone()[0],
        'collections': db.execute('SELECT COUNT(*) FROM collections').fetchone()[0],
        'active_collections': db.execute('SELECT COUNT(*) FROM collections WHERE is_active=1').fetchone()[0],
        'banners': db.execute('SELECT COUNT(*) FROM banners').fetchone()[0],
        'active_banners': db.execute('SELECT COUNT(*) FROM banners WHERE is_active=1').fetchone()[0],
        'orders': db.execute('SELECT COUNT(*) FROM orders').fetchone()[0],
        'new_orders': db.execute("SELECT COUNT(*) FROM orders WHERE status='yangi'").fetchone()[0],
        'revenue': db.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE status!='bekor'").fetchone()[0],
    }
    recent_collections = db.execute(
        'SELECT c.*, COUNT(pc.product_id) as prod_count '
        'FROM collections c '
        'LEFT JOIN product_collections pc ON pc.collection_id=c.id '
        'GROUP BY c.id ORDER BY c.id DESC LIMIT 6'
    ).fetchall()
    recent_banners = db.execute(
        'SELECT b.*, c.name as collection_name, c.slug as collection_slug '
        'FROM banners b LEFT JOIN collections c ON c.id=b.collection_id '
        'ORDER BY b.id DESC LIMIT 6'
    ).fetchall()
    popular = db.execute(
        'SELECT p.name, COUNT(oi.id) as cnt FROM order_items oi '
        'JOIN product p ON p.id=oi.product_id GROUP BY oi.product_id ORDER BY cnt DESC LIMIT 5'
    ).fetchall()
    return render_template(
        'admin/dashboard.html',
        stats=stats,
        recent_collections=recent_collections,
        recent_banners=recent_banners,
        popular=popular
    )

# ── KATEGORIYALAR ──────────────────────────────────────────────────────
@admin.route('/kategoriyalar')
@login_required
def categories():
    db = get_db()
    cats = db.execute(
        'SELECT c.*, p.name as parent_name, '
        '(SELECT COUNT(*) FROM category ch WHERE ch.parent_id=c.id) as child_count, '
        'COUNT(DISTINCT pc.product_id) as prod_count '
        'FROM category c '
        'LEFT JOIN category p ON p.id=c.parent_id '
        'LEFT JOIN product_categories pc ON pc.category_id=c.id '
        'GROUP BY c.id ORDER BY COALESCE(c.parent_id,0), c.sort_order, c.name'
    ).fetchall()
    return render_template('admin/categories.html', categories=cats)

@admin.route('/kategoriyalar/qoshish', methods=['GET','POST'])
@login_required
def add_category():
    db = get_db()
    parent_types = _parent_category_nodes(db)
    next_sort_order = _next_category_sort_order(db, None)
    sort_preview = _category_sort_preview(db, None)
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        if not name:
            flash('Nomi bo\'sh bo\'lishi mumkin emas','error')
            return render_template(
                'admin/category_form.html',
                cat=None,
                parent_types=parent_types,
                selected_product_ids=[],
                parent_products=[],
                next_sort_order=next_sort_order,
                sort_preview=sort_preview
            )
        slug = slugify(name)
        parent_id = si(request.form.get('parent_id'))
        sort_order = si(request.form.get('sort_order'))
        selected_product_ids = [int(x) for x in request.form.getlist('product_ids') if x]
        type_slug = slug
        is_type = 1 if not parent_id else 0
        if parent_id:
            parent = db.execute(
                'SELECT id,type FROM category WHERE id=?',
                (parent_id,)
            ).fetchone()
            if parent:
                type_slug = (parent['type'] or type_slug).strip() or type_slug
            else:
                parent_id = None
        if sort_order is None:
            sort_order = _next_category_sort_order(db, parent_id)
        try:
            cur = db.execute(
                'INSERT INTO category (name,slug,icon,type,description,sort_order,parent_id,is_type) '
                'VALUES (?,?,?,?,?,?,?,?)',
                (name, slug, request.form.get('icon','🌿'),
                 type_slug,
                 request.form.get('description',''),
                 sort_order,
                 parent_id,
                 is_type)
            )
            cid = cur.lastrowid
            _save_category_products(db, cid, selected_product_ids)
            db.commit()
            flash(f"'{name}' kategoriyasi qo'shildi!",'success')
        except Exception as e:
            flash(f'Xatolik: {e}','error')
        return redirect(url_for('admin.categories'))
    return render_template(
        'admin/category_form.html',
        cat=None,
        parent_types=parent_types,
        selected_product_ids=[],
        parent_products=[],
        next_sort_order=next_sort_order,
        sort_preview=sort_preview
    )

@admin.route('/kategoriyalar/<int:id>/tahrirlash', methods=['GET','POST'])
@login_required
def edit_category(id):
    db = get_db()
    cat = db.execute('SELECT * FROM category WHERE id=?',(id,)).fetchone()
    if not cat: abort(404)
    parent_types = _parent_category_nodes(db, exclude_id=id)
    selected_product_ids = [r[0] for r in db.execute(
        'SELECT product_id FROM product_categories WHERE category_id=?',
        (id,)
    ).fetchall()]
    parent_products = _products_by_parent_category(
        db,
        cat['parent_id'],
        current_category_id=id
    ) if cat['parent_id'] else []
    sort_preview = _category_sort_preview(db, cat['parent_id'], exclude_id=id)
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        parent_id = si(request.form.get('parent_id'))
        sort_order = si(request.form.get('sort_order'))
        selected_product_ids = [int(x) for x in request.form.getlist('product_ids') if x]
        if parent_id == id:
            parent_id = None
        type_slug = (cat['type'] or slugify(cat['name']) or 'tur').strip()
        is_type = 1 if not parent_id else 0
        if parent_id:
            parent = db.execute(
                'SELECT id,type FROM category WHERE id=?',
                (parent_id,)
            ).fetchone()
            if parent:
                type_slug = (parent['type'] or type_slug).strip() or type_slug
            else:
                parent_id = None
        if sort_order is None:
            sort_order = cat['sort_order'] if cat['sort_order'] is not None else _next_category_sort_order(db, parent_id, exclude_id=id)
        db.execute(
            'UPDATE category SET name=?,icon=?,type=?,description=?,sort_order=?,parent_id=?,is_type=? WHERE id=?',
            (name, request.form.get('icon','🌿'),
             type_slug,
             request.form.get('description',''),
             sort_order,
             parent_id, is_type, id)
        )
        _save_category_products(db, id, selected_product_ids)
        db.commit()
        flash('Kategoriya yangilandi!','success')
        return redirect(url_for('admin.categories'))
    return render_template(
        'admin/category_form.html',
        cat=cat,
        parent_types=parent_types,
        selected_product_ids=selected_product_ids,
        parent_products=parent_products,
        next_sort_order=cat['sort_order'],
        sort_preview=sort_preview
    )


@admin.route('/kategoriyalar/ota-tur-mahsulotlari')
@login_required
def parent_category_products():
    db = get_db()
    parent_id = si(request.args.get('parent_id'))
    current_category_id = si(request.args.get('current_category_id'))
    show_mode = (request.args.get('show') or '').strip().lower()
    include_assigned = show_mode == 'all'
    rows = _products_by_parent_category(
        db,
        parent_id,
        include_assigned=include_assigned,
        current_category_id=current_category_id
    ) if parent_id else []
    return jsonify({
        'success': True,
        'show_mode': 'all' if include_assigned else 'available',
        'items': [
            {
                'id': r['id'],
                'name': r['name'],
                'image': r['image'],
                'is_active': int(r['is_active'] or 0),
                'cat_name': r['cat_name'],
                'cat_icon': r['cat_icon'],
                'assigned_categories': r.get('assigned_categories', []),
                'assigned_categories_text': r.get('assigned_categories_text', ''),
                'assigned_elsewhere': int(r.get('assigned_elsewhere', 0)),
            }
            for r in rows
        ]
    })


@admin.route('/kategoriyalar/tartib-taklif')
@login_required
def category_sort_hint():
    db = get_db()
    parent_id = si(request.args.get('parent_id'))
    exclude_id = si(request.args.get('exclude_id'))
    preview_rows = _category_sort_preview(db, parent_id, exclude_id=exclude_id)
    return jsonify({
        'success': True,
        'next_sort': _next_category_sort_order(db, parent_id, exclude_id=exclude_id),
        'siblings': [
            {
                'id': r['id'],
                'name': r['name'],
                'sort_order': int(r['sort_order'] or 0),
            }
            for r in preview_rows
        ]
    })

@admin.route('/kategoriyalar/<int:id>/ochirish', methods=['POST'])
@login_required
def delete_category(id):
    db = get_db()
    db.execute('DELETE FROM category WHERE id=?',(id,))
    db.commit()
    flash("Kategoriya o'chirildi!",'success')
    return redirect(url_for('admin.categories'))

# ── KOLLEKSIYALAR ──────────────────────────────────────────────────────
@admin.route('/kolleksiyalar')
@login_required
def collections():
    db = get_db()
    rows = db.execute(
        'SELECT c.*, COUNT(pc.product_id) as prod_count '
        'FROM collections c '
        'LEFT JOIN product_collections pc ON pc.collection_id=c.id '
        'GROUP BY c.id ORDER BY c.sort_order, c.id DESC'
    ).fetchall()
    return render_template('admin/collections.html', collections=rows)

@admin.route('/kolleksiyalar/qoshish', methods=['GET', 'POST'])
@login_required
def add_collection():
    db = get_db()
    products = db.execute(
        'SELECT p.id,p.name,p.image,p.is_active,c.name as cat_name,c.icon as cat_icon '
        'FROM product p LEFT JOIN category c ON c.id=p.category_id '
        'ORDER BY p.is_active DESC, p.id DESC'
    ).fetchall()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        slug_input = request.form.get('slug', '').strip()
        description = request.form.get('description', '').strip()
        start_date = request.form.get('start_date', '').strip() or None
        end_date = request.form.get('end_date', '').strip() or None
        sort_order = si(request.form.get('sort_order')) or 0
        is_active = 1 if 'is_active' in request.form else 0
        selected_product_ids = [int(x) for x in request.form.getlist('product_ids') if x]

        if not name:
            flash("Kolleksiya nomi majburiy", 'error')
            return render_template(
                'admin/collection_form.html',
                collection=None,
                products=products,
                selected_product_ids=selected_product_ids
            )

        base_slug = slugify(slug_input or name) or f'collection-{uuid.uuid4().hex[:6]}'
        slug = _unique_collection_slug(db, base_slug)
        cur = db.execute(
            'INSERT INTO collections (name,slug,description,start_date,end_date,sort_order,is_active) '
            'VALUES (?,?,?,?,?,?,?)',
            (name, slug, description, start_date, end_date, sort_order, is_active)
        )
        cid = cur.lastrowid
        _save_collection_products(db, cid, selected_product_ids)
        db.commit()
        flash("Kolleksiya qo'shildi!", 'success')
        return redirect(url_for('admin.collections'))

    return render_template('admin/collection_form.html', collection=None, products=products, selected_product_ids=[])

@admin.route('/kolleksiyalar/<int:cid>/tahrirlash', methods=['GET', 'POST'])
@login_required
def edit_collection(cid):
    db = get_db()
    collection = db.execute('SELECT * FROM collections WHERE id=?', (cid,)).fetchone()
    if not collection:
        abort(404)

    products = db.execute(
        'SELECT p.id,p.name,p.image,p.is_active,c.name as cat_name,c.icon as cat_icon '
        'FROM product p LEFT JOIN category c ON c.id=p.category_id '
        'ORDER BY p.is_active DESC, p.id DESC'
    ).fetchall()
    existing_product_ids = [r[0] for r in db.execute(
        'SELECT product_id FROM product_collections WHERE collection_id=?',
        (cid,)
    ).fetchall()]

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        slug_input = request.form.get('slug', '').strip()
        description = request.form.get('description', '').strip()
        start_date = request.form.get('start_date', '').strip() or None
        end_date = request.form.get('end_date', '').strip() or None
        sort_order = si(request.form.get('sort_order')) or 0
        is_active = 1 if 'is_active' in request.form else 0
        selected_product_ids = [int(x) for x in request.form.getlist('product_ids') if x]

        if not name:
            flash("Kolleksiya nomi majburiy", 'error')
            return render_template(
                'admin/collection_form.html',
                collection=collection,
                products=products,
                selected_product_ids=selected_product_ids or existing_product_ids
            )

        base_slug = slugify(slug_input or name) or f'collection-{cid}'
        slug = _unique_collection_slug(db, base_slug, exclude_id=cid)

        db.execute(
            'UPDATE collections SET name=?,slug=?,description=?,start_date=?,end_date=?,sort_order=?,is_active=? '
            'WHERE id=?',
            (name, slug, description, start_date, end_date, sort_order, is_active, cid)
        )
        _save_collection_products(db, cid, selected_product_ids)
        db.commit()
        flash("Kolleksiya yangilandi!", 'success')
        return redirect(url_for('admin.collections'))

    return render_template(
        'admin/collection_form.html',
        collection=collection,
        products=products,
        selected_product_ids=existing_product_ids
    )

@admin.route('/kolleksiyalar/<int:cid>/ochirish', methods=['POST'])
@login_required
def delete_collection(cid):
    db = get_db()
    row = db.execute('SELECT id FROM collections WHERE id=?', (cid,)).fetchone()
    if not row:
        flash("Kolleksiya topilmadi", 'error')
        return redirect(url_for('admin.collections'))
    db.execute('UPDATE banners SET collection_id=NULL WHERE collection_id=?', (cid,))
    db.execute('DELETE FROM collections WHERE id=?', (cid,))
    db.commit()
    flash("Kolleksiya o'chirildi!", 'success')
    return redirect(url_for('admin.collections'))

# ── BANNERLAR ──────────────────────────────────────────────────────────
@admin.route('/bannerlar')
@login_required
def banners():
    db = get_db()
    rows = db.execute(
        'SELECT b.*, c.name as collection_name, c.slug as collection_slug, '
        'COUNT(pc.product_id) as collection_product_count '
        'FROM banners b '
        'LEFT JOIN collections c ON c.id=b.collection_id '
        'LEFT JOIN product_collections pc ON pc.collection_id=c.id '
        'GROUP BY b.id '
        'ORDER BY b.sort_order, b.id DESC'
    ).fetchall()
    return render_template('admin/banners.html', banners=rows)

@admin.route('/bannerlar/qoshish', methods=['GET', 'POST'])
@login_required
def add_banner():
    db = get_db()
    available_collections = db.execute(
        'SELECT * FROM collections ORDER BY is_active DESC, sort_order, id DESC'
    ).fetchall()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        subtitle = request.form.get('subtitle', '').strip()
        collection_id = si(request.form.get('collection_id'))
        button_link_manual = request.form.get('button_link', '').strip()
        sort_order = si(request.form.get('sort_order')) or 0
        is_active = 1 if 'is_active' in request.form else 0

        if not title:
            flash('Banner sarlavhasi majburiy', 'error')
            return render_template('admin/banner_form.html', banner=None, collections=available_collections)

        resolved_collection_id = collection_id if collection_id and collection_id > 0 else None
        button_link = button_link_manual
        if resolved_collection_id:
            selected_collection = db.execute(
                'SELECT id,slug FROM collections WHERE id=?',
                (resolved_collection_id,)
            ).fetchone()
            if not selected_collection:
                flash("Tanlangan kolleksiya topilmadi", 'error')
                return render_template('admin/banner_form.html', banner=None, collections=available_collections)
            button_link = None

        image_file = request.files.get('image')
        image_path = save_file(image_file, get_banner_upload_folder())
        if not image_path:
            flash('Banner rasmi majburiy (png/jpg/jpeg/webp/gif)', 'error')
            return render_template('admin/banner_form.html', banner=None, collections=available_collections)

        db.execute(
            'INSERT INTO banners (title, subtitle, image_path, collection_id, button_link, sort_order, is_active) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (title, subtitle, image_path, resolved_collection_id, button_link, sort_order, is_active)
        )
        db.commit()
        flash("Banner qo'shildi!", 'success')
        return redirect(url_for('admin.banners'))

    return render_template('admin/banner_form.html', banner=None, collections=available_collections)

@admin.route('/bannerlar/<int:bid>/tahrirlash', methods=['GET', 'POST'])
@login_required
def edit_banner(bid):
    db = get_db()
    banner = db.execute('SELECT * FROM banners WHERE id=?', (bid,)).fetchone()
    if not banner:
        abort(404)
    available_collections = db.execute(
        'SELECT * FROM collections ORDER BY is_active DESC, sort_order, id DESC'
    ).fetchall()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        subtitle = request.form.get('subtitle', '').strip()
        collection_id = si(request.form.get('collection_id'))
        button_link_manual = request.form.get('button_link', '').strip()
        sort_order = si(request.form.get('sort_order')) or 0
        is_active = 1 if 'is_active' in request.form else 0

        if not title:
            flash('Banner sarlavhasi majburiy', 'error')
            return render_template('admin/banner_form.html', banner=banner, collections=available_collections)

        resolved_collection_id = collection_id if collection_id and collection_id > 0 else None
        button_link = button_link_manual
        if resolved_collection_id:
            selected_collection = db.execute(
                'SELECT id,slug FROM collections WHERE id=?',
                (resolved_collection_id,)
            ).fetchone()
            if not selected_collection:
                flash("Tanlangan kolleksiya topilmadi", 'error')
                return render_template('admin/banner_form.html', banner=banner, collections=available_collections)
            button_link = None

        image_file = request.files.get('image')
        new_image = save_file(image_file, get_banner_upload_folder()) if image_file and image_file.filename else None
        image_path = new_image or banner['image_path']

        db.execute(
            'UPDATE banners SET title=?, subtitle=?, image_path=?, collection_id=?, button_link=?, sort_order=?, is_active=? '
            'WHERE id=?',
            (title, subtitle, image_path, resolved_collection_id, button_link, sort_order, is_active, bid)
        )
        db.commit()

        if new_image:
            delete_file(banner['image_path'], get_banner_upload_folder())

        flash('Banner yangilandi!', 'success')
        return redirect(url_for('admin.banners'))

    return render_template('admin/banner_form.html', banner=banner, collections=available_collections)

@admin.route('/bannerlar/<int:bid>/ochirish', methods=['POST'])
@login_required
def delete_banner(bid):
    db = get_db()
    banner = db.execute('SELECT * FROM banners WHERE id=?', (bid,)).fetchone()
    if not banner:
        flash('Banner topilmadi', 'error')
        return redirect(url_for('admin.banners'))

    delete_file(banner['image_path'], get_banner_upload_folder())
    db.execute('DELETE FROM banners WHERE id=?', (bid,))
    db.commit()
    flash("Banner o'chirildi!", 'success')
    return redirect(url_for('admin.banners'))

# ── MAHSULOTLAR ────────────────────────────────────────────────────────
@admin.route('/mahsulotlar')
@login_required
def products():
    db = get_db()
    q = request.args.get('q','').strip()
    cat_id = request.args.get('cat')
    tip = request.args.get('tip', '')
    page = request.args.get('page',1,type=int)
    per_page = 20

    # Top-level categories for product filter
    all_cats = _root_type_nodes(db)
    type_rows = db.execute(
        "SELECT DISTINCT type FROM category WHERE COALESCE(is_type,0)=0 "
        "AND type IS NOT NULL AND trim(type)<>'' ORDER BY type"
    ).fetchall()
    type_options = [r['type'] for r in type_rows]
    types_map = {slug: [] for slug in type_options}
    for c in all_cats:
        t = c['type'] if c['type'] in types_map else ''
        if t:
            types_map[t].append(dict(c))
    # Filtered cats for the select dropdown
    filtered_cats = types_map.get(tip, []) if tip else [dict(c) for c in all_cats]

    conds = []
    params = []
    if q:
        conds.append('(p.name LIKE ? OR p.origin LIKE ?)')
        params.extend([f'%{q}%']*2)
    if cat_id:
        conds.append('p.category_id=?')
        params.append(cat_id)
    elif tip:
        conds.append('EXISTS (SELECT 1 FROM product_categories pc JOIN category cc ON cc.id=pc.category_id WHERE pc.product_id=p.id AND cc.type=?)')
        params.append(tip)
    where = ('WHERE '+' AND '.join(conds)) if conds else ''
    total = db.execute(f'SELECT COUNT(*) FROM product p {where}', params).fetchone()[0]
    prods = db.execute(
        f'SELECT p.*, c.name as cat_name FROM product p LEFT JOIN category c ON c.id=p.category_id '
        f'{where} ORDER BY p.id DESC LIMIT ? OFFSET ?',
        params+[per_page,(page-1)*per_page]
    ).fetchall()
    return render_template('admin/products.html', products=prods,
                           cats=filtered_cats, types_map=types_map, type_options=type_options,
                           q=q, active_cat=cat_id, tip=tip, page=page,
                           total_pages=(total+per_page-1)//per_page, total=total)

@admin.route('/mahsulotlar/qoshish', methods=['GET','POST'])
@login_required
def add_product():
    db = get_db()
    cats = [c for c in _parent_category_nodes(db) if c.get('depth') == 0]
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        if not name:
            flash('Nomi kerak!','error')
            return render_template('admin/product_form.html', product=None, cats=cats, product_category_ids=[])
        cat_ids = [int(x) for x in request.form.getlist('category_ids') if x]
        if not cat_ids:
            flash("Kamida bitta kategoriya tanlang.", 'error')
            return render_template('admin/product_form.html', product=None, cats=cats, product_category_ids=[])
        slug = _unique_slug(db, slugify(name))
        variants = _parse_variants(request.form)
        if not variants:
            flash("Kamida bitta variant kiriting (nomi va narxi bilan).", 'error')
            return render_template(
                'admin/product_form.html',
                product=None,
                cats=cats,
                variants=variants,
                product_category_ids=cat_ids
            )
        base_variant = variants[0]
        base_price = base_variant['price']
        first_cat = _preferred_product_category_id(db, cat_ids)
        files = [f for f in request.files.getlist('images') if f and f.filename]
        saved = [s for s in (save_file(f) for f in files) if s]

        try:
            unit_type = request.form.get('unit_type', 'dona')
            cur = db.execute(
                'INSERT INTO product (name,slug,category_id,description,origin,benefits,usage_tips,'
                'price,old_price,image,is_featured,is_active,stock,unit_type,min_amount) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (name, slug, first_cat,
                 request.form.get('description'), request.form.get('origin'),
                 request.form.get('benefits'), request.form.get('usage_tips'),
                 base_price, base_variant['old_price'],
                 saved[0] if saved else None,
                 1 if 'is_featured' in request.form else 0,
                 1 if 'is_active' in request.form else 0,
                 base_variant['stock'],
                 unit_type, base_variant['min_amount'])
            )
            db.commit()
            pid = cur.lastrowid
            _save_variants(db, pid, variants)
            _save_categories(db, pid, cat_ids)
            for idx, fname in enumerate(saved):
                db.execute('INSERT INTO product_images (product_id,image_path,is_primary,order_index) VALUES (?,?,?,?)',
                           (pid, fname, 1 if idx==0 else 0, idx))
            _sync_primary_image(db, pid)
            db.commit()
            flash("Mahsulot qo'shildi!",'success')
            return redirect(url_for('admin.products'))
        except Exception as e:
            db.rollback()
            flash(f'Xatolik: {e}','error')
    return render_template('admin/product_form.html', product=None, cats=cats, product_category_ids=[])

@admin.route('/mahsulotlar/<int:pid>/tahrirlash', methods=['GET','POST'])
@login_required
def edit_product(pid):
    db = get_db()
    product = db.execute('SELECT * FROM product WHERE id=?',(pid,)).fetchone()
    if not product: abort(404)
    cats = [c for c in _parent_category_nodes(db) if c.get('depth') == 0]
    variants = db.execute('SELECT * FROM product_variants WHERE product_id=? ORDER BY id',(pid,)).fetchall()
    images = db.execute('SELECT * FROM product_images WHERE product_id=? ORDER BY is_primary DESC, order_index',(pid,)).fetchall()
    existing_cat_ids = [r[0] for r in db.execute('SELECT category_id FROM product_categories WHERE product_id=?',(pid,)).fetchall()]

    if request.method == 'POST':
        name = request.form.get('name','').strip()
        cat_ids = [int(x) for x in request.form.getlist('category_ids') if x]
        if not cat_ids:
            flash("Kamida bitta kategoriya tanlang.", 'error')
            return render_template(
                'admin/product_form.html',
                product=product,
                cats=cats,
                variants=variants,
                product_images=images,
                product_category_ids=existing_cat_ids
            )
        new_variants = _parse_variants(request.form)
        if not new_variants:
            flash("Kamida bitta variant kiriting (nomi va narxi bilan).", 'error')
            return render_template(
                'admin/product_form.html',
                product=product,
                cats=cats,
                variants=new_variants,
                product_images=images,
                product_category_ids=cat_ids or existing_cat_ids
            )
        base_variant = new_variants[0]
        base_price = base_variant['price']
        files = [f for f in request.files.getlist('images') if f and f.filename]
        saved = [s for s in (save_file(f) for f in files) if s]
        first_cat = _preferred_product_category_id(db, cat_ids)
        try:
            unit_type_e = request.form.get('unit_type', 'dona')
            if saved:
                db.execute(
                    'UPDATE product SET name=?,category_id=?,description=?,origin=?,benefits=?,usage_tips=?,'
                    'price=?,old_price=?,is_featured=?,is_active=?,stock=?,image=?,unit_type=?,min_amount=? WHERE id=?',
                    (name, first_cat,
                    request.form.get('description'), request.form.get('origin'),
                    request.form.get('benefits'), request.form.get('usage_tips'),
                    base_price, base_variant['old_price'],
                    1 if 'is_featured' in request.form else 0,
                    1 if 'is_active' in request.form else 0,
                    base_variant['stock'],
                    saved[0], unit_type_e, base_variant['min_amount'], pid)
                )
            else:
                db.execute(
                    'UPDATE product SET name=?,category_id=?,description=?,origin=?,benefits=?,usage_tips=?,'
                    'price=?,old_price=?,is_featured=?,is_active=?,stock=?,unit_type=?,min_amount=? WHERE id=?',
                    (name, first_cat,
                     request.form.get('description'), request.form.get('origin'),
                     request.form.get('benefits'), request.form.get('usage_tips'),
                     base_price, base_variant['old_price'],
                     1 if 'is_featured' in request.form else 0,
                     1 if 'is_active' in request.form else 0,
                     base_variant['stock'],
                     unit_type_e, base_variant['min_amount'], pid)
                )
            _save_variants(db, pid, new_variants)
            _save_categories(db, pid, cat_ids)
            if saved:
                start = (db.execute('SELECT COALESCE(MAX(order_index),-1) FROM product_images WHERE product_id=?',(pid,)).fetchone()[0] or -1)+1
                for idx, fname in enumerate(saved):
                    db.execute('INSERT INTO product_images (product_id,image_path,is_primary,order_index) VALUES (?,?,?,?)',
                               (pid, fname, 0, start+idx))
            _sync_primary_image(db, pid)
            db.commit()
            flash('Mahsulot yangilandi!','success')
            return redirect(url_for('admin.products'))
        except Exception as e:
            db.rollback()
            flash(f'Xatolik: {e}','error')
    return render_template('admin/product_form.html', product=product, cats=cats,
                           variants=variants, product_images=images, product_category_ids=existing_cat_ids)

@admin.route('/mahsulotlar/<int:pid>/ochirish', methods=['POST'])
@login_required
def delete_product(pid):
    db = get_db()
    imgs = db.execute('SELECT image_path FROM product_images WHERE product_id=?',(pid,)).fetchall()
    for i in imgs: delete_file(i['image_path'])
    p = db.execute('SELECT image FROM product WHERE id=?',(pid,)).fetchone()
    if p: delete_file(p['image'])
    db.execute('DELETE FROM product WHERE id=?',(pid,))
    db.commit()
    flash("Mahsulot o'chirildi!",'success')
    return redirect(url_for('admin.products'))

@admin.route('/mahsulot-rasm/<int:iid>/ochirish', methods=['POST'])
@login_required
def delete_image(iid):
    db = get_db()
    img = db.execute('SELECT * FROM product_images WHERE id=?',(iid,)).fetchone()
    if img:
        pid = img['product_id']
        delete_file(img['image_path'])
        db.execute('DELETE FROM product_images WHERE id=?',(iid,))
        primary_id = _sync_primary_image(db, pid)
        db.commit()
        return jsonify({'success': True, 'primary_id': primary_id})
    return jsonify({'success': False}), 404

@admin.route('/mahsulot-rasm/<int:iid>/asosiy', methods=['POST'])
@login_required
def set_image_primary(iid):
    db = get_db()
    img = db.execute('SELECT * FROM product_images WHERE id=?',(iid,)).fetchone()
    if not img:
        return jsonify({'success': False, 'error': 'Rasm topilmadi'}), 404
    
    pid = img['product_id']
    # Shu mahsulotning boshqa rasmlari uchun is_primary = 0
    db.execute('UPDATE product_images SET is_primary=0 WHERE product_id=?',(pid,))
    # Tanlangan rasmni asosiy qil
    db.execute('UPDATE product_images SET is_primary=1 WHERE id=?',(iid,))
    primary_id = _sync_primary_image(db, pid)
    db.commit()
    return jsonify({'success': True, 'primary_id': primary_id})


# ── SOZLAMALAR ─────────────────────────────────────────────────────────
@admin.route('/sozlamalar/kontakt', methods=['GET', 'POST'])
@login_required
def contact_settings():
    db = get_db()
    settings = _load_contact_settings(db)

    if request.method == 'POST':
        updated = {
            'contact_phone_raw': request.form.get('contact_phone_raw', '').strip(),
            'contact_phone_display': request.form.get('contact_phone_display', '').strip(),
            'contact_telegram_url': request.form.get('contact_telegram_url', '').strip(),
            'contact_telegram_label': request.form.get('contact_telegram_label', '').strip(),
            'contact_instagram_url': request.form.get('contact_instagram_url', '').strip(),
            'contact_instagram_label': request.form.get('contact_instagram_label', '').strip(),
            'contact_location_url': request.form.get('contact_location_url', '').strip(),
            'contact_location_label': request.form.get('contact_location_label', '').strip(),
        }

        if not updated['contact_phone_raw']:
            flash('Telefon majburiy maydon!', 'error')
            return render_template('admin/contact_settings.html', settings=updated)

        if not updated['contact_phone_display']:
            updated['contact_phone_display'] = updated['contact_phone_raw']

        for key, value in updated.items():
            db.execute(
                'INSERT INTO site_settings (key, value) VALUES (?, ?) '
                'ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                (key, value)
            )
        db.commit()
        flash('Kontakt sozlamalari saqlandi!', 'success')
        return redirect(url_for('admin.contact_settings'))

    return render_template('admin/contact_settings.html', settings=settings)

# ── PAROL ──────────────────────────────────────────────────────────────
@admin.route('/parol', methods=['GET','POST'])
@login_required
def change_password():
    if request.method == 'POST':
        db = get_db()
        u = db.execute('SELECT * FROM admin WHERE id=?',(session['admin_id'],)).fetchone()
        if check_password_hash(u['password_hash'], request.form['old']):
            db.execute('UPDATE admin SET password_hash=? WHERE id=?',
                       (generate_password_hash(request.form['new']), session['admin_id']))
            db.commit()
            flash("Parol o'zgartirildi!",'success')
        else:
            flash("Eski parol noto'g'ri!",'error')
    return render_template('admin/change_password.html')

# ── HELPERS ────────────────────────────────────────────────────────────
def _save_categories(db, pid, cat_ids):
    selected_ids = sorted({int(cid) for cid in cat_ids if cid})
    category_rows = db.execute('SELECT id,parent_id FROM category').fetchall()
    parent_by_id = {int(r['id']): (int(r['parent_id']) if r['parent_id'] not in (None, '') else None) for r in category_rows}
    valid_ids = set(parent_by_id.keys())
    selected_ids = [cid for cid in selected_ids if cid in valid_ids]

    if not selected_ids:
        db.execute('DELETE FROM product_categories WHERE product_id=?', (pid,))
        return

    root_cache = {}
    def root_of(cid):
        if cid in root_cache:
            return root_cache[cid]
        seen = set()
        cur = cid
        while cur and cur in parent_by_id and cur not in seen:
            seen.add(cur)
            parent_id = parent_by_id.get(cur)
            if parent_id is None:
                root_cache[cid] = cur
                return cur
            cur = parent_id
        root_cache[cid] = None
        return None

    selected_root_ids = {root_of(cid) for cid in selected_ids}
    selected_root_ids.discard(None)
    final_ids = sorted(set(selected_ids) | set(selected_root_ids))

    db.execute('DELETE FROM product_categories WHERE product_id=?', (pid,))
    for cid in final_ids:
        db.execute('INSERT OR IGNORE INTO product_categories (product_id, category_id) VALUES (?,?)', (pid, cid))


def _save_category_products(db, cid, product_ids):
    db.execute('DELETE FROM product_categories WHERE category_id=?', (cid,))
    cat = db.execute('SELECT id,parent_id FROM category WHERE id=?', (cid,)).fetchone()
    root_id = None
    if cat:
        parent_by_id = {
            int(r['id']): (int(r['parent_id']) if r['parent_id'] not in (None, '') else None)
            for r in db.execute('SELECT id,parent_id FROM category').fetchall()
        }
        cur = int(cat['id'])
        seen = set()
        while cur and cur in parent_by_id and cur not in seen:
            seen.add(cur)
            parent_id = parent_by_id.get(cur)
            if parent_id is None:
                root_id = cur
                break
            cur = parent_id

    for pid in sorted(set(product_ids)):
        db.execute(
            'INSERT OR IGNORE INTO product_categories (product_id, category_id) VALUES (?,?)',
            (pid, cid)
        )
        if root_id:
            db.execute(
                'INSERT OR IGNORE INTO product_categories (product_id, category_id) VALUES (?,?)',
                (pid, root_id)
            )

def _load_contact_settings(db):
    settings = dict(CONTACT_SETTINGS_DEFAULTS)
    rows = db.execute('SELECT key, value FROM site_settings WHERE key LIKE "contact_%"').fetchall()
    for row in rows:
        if row['key'] in settings:
            settings[row['key']] = row['value'] if row['value'] is not None else ''
    return settings

def _save_collection_products(db, collection_id, product_ids):
    db.execute('DELETE FROM product_collections WHERE collection_id=?', (collection_id,))
    for pid in sorted(set(product_ids)):
        db.execute(
            'INSERT OR IGNORE INTO product_collections (product_id, collection_id) VALUES (?, ?)',
            (pid, collection_id)
        )

def _unique_slug(db, base, exclude_id=None):
    slug, i = base, 1
    while True:
        row = db.execute('SELECT 1 FROM product WHERE slug=?'+('' if not exclude_id else ' AND id<>?'),
                         [slug]+([exclude_id] if exclude_id else [])).fetchone()
        if not row: return slug
        i += 1; slug = f'{base}-{i}'

def _unique_collection_slug(db, base, exclude_id=None):
    slug, i = base, 1
    while True:
        row = db.execute(
            'SELECT 1 FROM collections WHERE slug=?' + ('' if not exclude_id else ' AND id<>?'),
            [slug] + ([exclude_id] if exclude_id else [])
        ).fetchone()
        if not row:
            return slug
        i += 1
        slug = f'{base}-{i}'

def _parse_variants(form):
    result = []
    idxs = []
    for key in form.keys():
        if key.startswith('v_label_'):
            try:
                idxs.append(int(key.rsplit('_', 1)[1]))
            except Exception:
                pass
    for i in sorted(set(idxs)):
        label = (form.get(f'v_label_{i}') or '').strip()
        price = sf(form.get(f'v_price_{i}'))
        if not label or price is None or price <= 0:
            continue

        old_price = sf(form.get(f'v_old_price_{i}'))
        if old_price is not None and old_price <= 0:
            old_price = None
        promo_start_at = normalize_promo_input(form.get(f'v_promo_start_{i}'), end_of_day=False)
        promo_end_at = normalize_promo_input(form.get(f'v_promo_end_{i}'), end_of_day=True)
        if promo_start_at and promo_end_at:
            try:
                if datetime.fromisoformat(promo_end_at) <= datetime.fromisoformat(promo_start_at):
                    promo_end_at = None
            except Exception:
                promo_end_at = None
        if promo_end_at:
            try:
                if datetime.fromisoformat(promo_end_at) <= datetime.now():
                    old_price = None
                    promo_start_at = None
                    promo_end_at = None
            except Exception:
                promo_end_at = None
        scheduled_price = None
        if old_price is None:
            promo_start_at = None
            promo_end_at = None
        elif promo_start_at:
            try:
                if datetime.fromisoformat(promo_start_at) > datetime.now():
                    scheduled_price = float(price)
                    price = float(old_price)
                    old_price = None
            except Exception:
                promo_start_at = None

        stock_raw = form.get(f'v_stock_{i}')
        stock = si(stock_raw) if stock_raw not in (None, '') else 100
        if stock is None:
            stock = 100
        stock = max(0, stock)

        result.append({
            'label': label,
            'price': float(price),
            'old_price': float(old_price) if old_price is not None else None,
            'promo_start_at': promo_start_at,
            'promo_end_at': promo_end_at,
            'scheduled_price': scheduled_price,
            'stock': int(stock),
            # Minimal buyurtma user-side'da o'chirilgan, 1 sifatida saqlaymiz.
            'min_amount': 1.0,
        })
    return result

def _save_variants(db, pid, variants):
    db.execute('DELETE FROM product_variants WHERE product_id=?',(pid,))
    for v in variants:
        db.execute(
            'INSERT INTO product_variants (product_id,label,price,old_price,promo_start_at,promo_end_at,scheduled_price,promo_end_date,stock,min_amount) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (pid, v['label'], v['price'], v['old_price'], v.get('promo_start_at'), v.get('promo_end_at'), v.get('scheduled_price'), None, v['stock'], v['min_amount'])
        )
