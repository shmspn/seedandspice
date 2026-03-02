from flask import Blueprint, render_template, request, abort, session, jsonify, redirect, url_for, flash
from app import get_db

main = Blueprint('main', __name__)

def get_product_with_variants(db, product_id):
    p = db.execute('SELECT p.*, c.name as cat_name, c.icon as cat_icon FROM product p LEFT JOIN category c ON c.id=p.category_id WHERE p.id=?', (product_id,)).fetchone()
    if not p: return None, []
    variants = db.execute('SELECT * FROM product_variants WHERE product_id=? ORDER BY id', (product_id,)).fetchall()
    return p, variants

@main.route('/')
def index():
    db = get_db()
    banners = db.execute(
        'SELECT b.*, c.slug as collection_slug FROM banners b '
        'LEFT JOIN collections c ON c.id=b.collection_id '
        'WHERE b.is_active=1 ORDER BY b.sort_order, b.id DESC'
    ).fetchall()

    featured = db.execute(
        'SELECT p.*, c.name as cat_name, c.icon as cat_icon FROM product p '
        'LEFT JOIN category c ON c.id=p.category_id '
        'WHERE p.is_active=1 AND COALESCE(p.is_featured, 0)=1 '
        'ORDER BY COALESCE(p.cart_add_count, 0) DESC, COALESCE(p.view_count, 0) DESC, p.id DESC LIMIT 8'
    ).fetchall()
    featured_with_variants = []
    for p in featured:
        variants = db.execute('SELECT * FROM product_variants WHERE product_id=? ORDER BY id', (p['id'],)).fetchall()
        # Get primary image
        primary_img = db.execute('SELECT image_path FROM product_images WHERE product_id=? ORDER BY is_primary DESC, order_index, id LIMIT 1', (p['id'],)).fetchone()
        row = dict(p)
        row['variants'] = [dict(v) for v in variants]
        row['primary_image'] = primary_img['image_path'] if primary_img else row['image']
        featured_with_variants.append(row)

    new_arrivals = db.execute(
        'SELECT p.*, c.name as cat_name FROM product p LEFT JOIN category c ON c.id=p.category_id '
        'WHERE p.is_active=1 ORDER BY p.created_at DESC LIMIT 4'
    ).fetchall()

    return render_template('index.html',
        banners=banners,
        featured=featured_with_variants,
        new_arrivals=new_arrivals
    )

@main.route('/katalog')
def catalog():
    db = get_db()
    type_slug = (request.args.get('tur', '') or request.args.get('tip', '')).strip()
    cat_slug = (request.args.get('kategoriya', '') or '').strip()
    collection_slug = request.args.get('collection', '').strip()
    search = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'mashhur')
    page = request.args.get('page', 1, type=int)
    per_page = 12
    offset = (page-1)*per_page

    nodes = [dict(r) for r in db.execute(
        'SELECT * FROM category ORDER BY COALESCE(parent_id,0), sort_order, name'
    ).fetchall()]
    nodes_by_id = {}
    nodes_by_slug = {}
    children_by_parent = {}
    for n in nodes:
        n['is_type'] = int(n.get('is_type') or 0)
        n['parent_id'] = n.get('parent_id') if n.get('parent_id') not in ('', None) else None
        nodes_by_id[n['id']] = n
        if n.get('slug'):
            nodes_by_slug[n['slug']] = n
        children_by_parent.setdefault(n['parent_id'], []).append(n)

    def descendant_ids(start_id):
        stack = [start_id]
        seen = set()
        result = []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            result.append(current)
            for child in children_by_parent.get(current, []):
                stack.append(child['id'])
        return result

    top_types = [n for n in children_by_parent.get(None, []) if n['is_type'] == 1]
    active_type = nodes_by_slug.get(type_slug) if type_slug else None
    if not active_type and type_slug:
        for t in top_types:
            if (t.get('type') or '') == type_slug:
                active_type = t
                break

    active_category = nodes_by_slug.get(cat_slug) if cat_slug else None
    if active_category and active_category['is_type'] == 1:
        active_type = active_category
        active_category = None
    if active_category:
        parent = nodes_by_id.get(active_category.get('parent_id'))
        if parent:
            active_type = parent

    def ancestor_chain_ids(node):
        chain = []
        current = node
        safety = 0
        while current and safety < (len(nodes) + 3):
            chain.append(current['id'])
            parent_id = current.get('parent_id')
            current = nodes_by_id.get(parent_id) if parent_id else None
            safety += 1
        return chain

    active_path_ids = []
    if active_category:
        active_path_ids = ancestor_chain_ids(active_category)
    elif active_type:
        active_path_ids = ancestor_chain_ids(active_type)
    active_path_set = set(active_path_ids)

    active_root_type = None
    for node_id in reversed(active_path_ids):
        node = nodes_by_id.get(node_id)
        if node and node['is_type'] == 1 and node.get('parent_id') is None:
            active_root_type = node
            break

    active_collection = None
    conditions = ['p.is_active=1']
    params = []

    if collection_slug:
        active_collection = db.execute(
            'SELECT * FROM collections WHERE slug=? AND is_active=1 '
            'AND (start_date IS NULL OR start_date="" OR date(start_date) <= date("now")) '
            'AND (end_date IS NULL OR end_date="" OR date(end_date) >= date("now"))',
            (collection_slug,)
        ).fetchone()
        if active_collection:
            conditions.append(
                'EXISTS (SELECT 1 FROM product_collections pcl '
                'WHERE pcl.product_id=p.id AND pcl.collection_id=?)'
            )
            params.append(active_collection['id'])
        else:
            conditions.append('1=0')

    if active_category:
        conditions.append(
            'EXISTS (SELECT 1 FROM product_categories pc WHERE pc.product_id=p.id AND pc.category_id=?)'
        )
        params.append(active_category['id'])
    elif active_type:
        subtree = descendant_ids(active_type['id'])
        target_category_ids = list(subtree)
        if not target_category_ids:
            target_category_ids = [active_type['id']]
        placeholders = ','.join(['?'] * len(target_category_ids))
        conditions.append(
            f'EXISTS (SELECT 1 FROM product_categories pc '
            f'WHERE pc.product_id=p.id AND pc.category_id IN ({placeholders}))'
        )
        params.extend(target_category_ids)

    if search:
        conditions.append('(p.name LIKE ? OR p.description LIKE ? OR p.origin LIKE ?)')
        params.extend([f'%{search}%']*3)

    order = {
        'yangi': 'p.id DESC',
        'mashhur': 'COALESCE(p.cart_add_count, 0) DESC, COALESCE(p.view_count, 0) DESC, p.id DESC',
        'arzon': 'p.price ASC',
        'qimmat': 'p.price DESC',
        'nom': 'p.name ASC',
    }.get(sort, 'COALESCE(p.cart_add_count, 0) DESC, COALESCE(p.view_count, 0) DESC, p.id DESC')
    where = ' AND '.join(conditions)

    total = db.execute(f'SELECT COUNT(*) FROM product p WHERE {where}', params).fetchone()[0]
    products = db.execute(
        f'SELECT p.*, c.name as cat_name, c.icon as cat_icon FROM product p '
        f'LEFT JOIN category c ON c.id=p.category_id WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?',
        params+[per_page, offset]
    ).fetchall()

    prod_list = []
    for p in products:
        variants = db.execute('SELECT * FROM product_variants WHERE product_id=? ORDER BY id', (p['id'],)).fetchall()
        # Get primary image
        primary_img = db.execute('SELECT image_path FROM product_images WHERE product_id=? ORDER BY is_primary DESC, order_index, id LIMIT 1', (p['id'],)).fetchone()
        row = dict(p)
        row['variants'] = [dict(v) for v in variants]
        row['primary_image'] = primary_img['image_path'] if primary_img else row['image']
        prod_list.append(row)

    total_pages = (total+per_page-1)//per_page
    return render_template(
        'catalog.html',
        products=prod_list,
        search=search,
        sort=sort,
        page=page,
        total_pages=total_pages,
        total=total,
        active_collection=active_collection,
        collection=collection_slug,
        top_types=top_types,
        children_by_parent=children_by_parent,
        active_path_ids=active_path_ids,
        active_path_set=active_path_set,
        active_root_type=active_root_type,
        active_type=active_type,
        active_category=active_category,
        tur=(active_type['slug'] if active_type else '')
    )

@main.route('/mahsulot/<slug>')
def product_detail(slug):
    db = get_db()
    product = db.execute(
        'SELECT p.*, c.name as cat_name, c.icon as cat_icon, c.slug as cat_slug '
        'FROM product p LEFT JOIN category c ON c.id=p.category_id '
        'WHERE p.slug=? AND p.is_active=1', (slug,)
    ).fetchone()
    if not product: abort(404)

    # Har ochilganda ko'rishlar sonini oshiramiz (mashhur sort uchun).
    db.execute(
        'UPDATE product SET view_count = COALESCE(view_count, 0) + 1 WHERE id=?',
        (product['id'],)
    )
    db.commit()

    variants = db.execute('SELECT * FROM product_variants WHERE product_id=? ORDER BY id', (product['id'],)).fetchall()
    images = db.execute('SELECT * FROM product_images WHERE product_id=? ORDER BY is_primary DESC, order_index', (product['id'],)).fetchall()
    related_category = db.execute(
        'SELECT c.id,c.name,c.slug '
        'FROM product_categories pc '
        'JOIN category c ON c.id=pc.category_id '
        'WHERE pc.product_id=? '
        'AND COALESCE(c.is_type,0)=0 '
        'AND c.parent_id IS NOT NULL '
        'ORDER BY c.id '
        'LIMIT 1',
        (product['id'],)
    ).fetchone()
    if not related_category:
        related_category = db.execute(
            'SELECT c.id,c.name,c.slug '
            'FROM product_categories pc '
            'JOIN category c ON c.id=pc.category_id '
            'WHERE pc.product_id=? '
            'AND COALESCE(c.is_type,0)=0 '
            'ORDER BY c.id '
            'LIMIT 1',
            (product['id'],)
        ).fetchone()

    related_rows = []
    if related_category:
        related_rows = db.execute(
            'SELECT DISTINCT p.* '
            'FROM product p '
            'JOIN product_categories pc ON pc.product_id=p.id '
            'WHERE p.id!=? AND p.is_active=1 AND pc.category_id=? '
            'ORDER BY RANDOM() LIMIT 4',
            (product['id'], related_category['id'])
        ).fetchall()
    related = []
    for p in related_rows:
        row = dict(p)
        row['primary_image'] = _get_primary_image(db, p['id'], p['image'])
        rel_variants = db.execute(
            'SELECT * FROM product_variants WHERE product_id=? ORDER BY id',
            (p['id'],)
        ).fetchall()
        row['variants'] = [dict(v) for v in rel_variants]
        related.append(row)

    return render_template('product.html', product=product, variants=variants, images=images, related=related)

def _get_primary_image(db, product_id, fallback=None):
    primary = db.execute(
        'SELECT image_path FROM product_images WHERE product_id=? '
        'ORDER BY is_primary DESC, order_index, id LIMIT 1',
        (product_id,)
    ).fetchone()
    return primary['image_path'] if primary else fallback


def _popular_products_for_favorites(db, exclude_ids=None, limit=6):
    exclude_ids = [int(pid) for pid in (exclude_ids or []) if str(pid).isdigit()]
    params = []
    where = 'p.is_active=1'
    if exclude_ids:
        placeholders = ','.join(['?'] * len(exclude_ids))
        where += f' AND p.id NOT IN ({placeholders})'
        params.extend(exclude_ids)

    rows = db.execute(
        'SELECT p.*, c.name as cat_name, c.icon as cat_icon '
        'FROM product p '
        'LEFT JOIN category c ON c.id=p.category_id '
        f'WHERE {where} '
        'ORDER BY COALESCE(p.cart_add_count, 0) DESC, COALESCE(p.view_count, 0) DESC, p.is_featured DESC, p.id DESC '
        'LIMIT ?',
        params + [limit]
    ).fetchall()

    result = []
    for p in rows:
        row = dict(p)
        row['primary_image'] = _get_primary_image(db, p['id'], p['image'])
        variants = db.execute(
            'SELECT * FROM product_variants WHERE product_id=? ORDER BY id',
            (p['id'],)
        ).fetchall()
        row['variants'] = [dict(v) for v in variants]
        result.append(row)
    return result


def _favorite_product_id(key, item):
    raw = None
    if isinstance(item, dict):
        raw = item.get('product_id')
    if raw in (None, ''):
        raw = str(key).split('_v', 1)[0]
    try:
        pid = int(raw)
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def _ensure_favorites(db):
    favorites = session.get('favorites')
    if not isinstance(favorites, dict):
        favorites = {}

    legacy_cart = session.get('cart', {})
    if isinstance(legacy_cart, dict) and legacy_cart:
        for key, item in legacy_cart.items():
            if not isinstance(item, dict):
                continue

            try:
                product_id = int(item.get('product_id'))
            except (TypeError, ValueError):
                continue

            slug_row = db.execute('SELECT slug FROM product WHERE id=?', (product_id,)).fetchone()
            price_raw = item.get('base_price')
            if price_raw in (None, '', 0):
                price_raw = item.get('price')
            try:
                price = int(round(float(price_raw or 0)))
            except (TypeError, ValueError):
                price = 0

            normalized_key = str(product_id)
            favorites[normalized_key] = {
                'key': normalized_key,
                'product_id': product_id,
                'slug': slug_row['slug'] if slug_row else '',
                'name': item.get('name', 'Mahsulot'),
                'variant': item.get('variant', ''),
                'image': item.get('image'),
                'price': price,
            }
        session.pop('cart', None)

    normalized = {}
    for old_key, item in favorites.items():
        if not isinstance(item, dict):
            continue
        product_id = _favorite_product_id(old_key, item)
        if not product_id:
            continue

        product = db.execute(
            'SELECT id,name,slug,image,price,old_price FROM product WHERE id=?',
            (product_id,)
        ).fetchone()
        if not product:
            continue

        key = str(product_id)
        price = float(product['price'] or 0)
        old_price = float(product['old_price']) if product['old_price'] not in (None, '') else None
        row = {
            'key': key,
            'product_id': product_id,
            'slug': product['slug'],
            'name': product['name'],
            'variant': item.get('variant', '') if isinstance(item.get('variant', ''), str) else '',
            'image': _get_primary_image(db, product_id, product['image']),
            'price': int(round(price)),
            'old_price': int(round(old_price)) if old_price and old_price > price else None,
        }
        if key in normalized:
            # Dedupe: old variant-based favorites collapse into single product favorite.
            if not normalized[key].get('variant') and row.get('variant'):
                normalized[key]['variant'] = row['variant']
        else:
            normalized[key] = row

    if normalized != favorites:
        session['favorites'] = normalized
        session.modified = True
    return normalized


# ── SEVIMLILAR ────────────────────────────────────────────────────────
@main.route('/sevimlilar')
def favorites():
    db = get_db()
    favorites_map = _ensure_favorites(db)
    items = list(favorites_map.values())

    for item in items:
        try:
            pid = int(item.get('product_id', 0))
        except (TypeError, ValueError):
            continue
        if pid <= 0:
            continue
        variants = db.execute(
            'SELECT * FROM product_variants WHERE product_id=? ORDER BY id',
            (pid,)
        ).fetchall()
        item['variants'] = [dict(v) for v in variants]
        selected_variant_id = None
        selected_label = (item.get('variant') or '').strip().lower()
        if selected_label and item['variants']:
            for v in item['variants']:
                if (v.get('label') or '').strip().lower() == selected_label:
                    selected_variant_id = v['id']
                    price = float(v['price'] or 0)
                    old_raw = v['old_price']
                    old_price = float(old_raw) if old_raw not in (None, '') else None
                    item['price'] = int(round(price))
                    item['old_price'] = int(round(old_price)) if old_price and old_price > price else None
                    break
        item['selected_variant_id'] = selected_variant_id

    favorite_ids = []
    for item in items:
        try:
            pid = int(item.get('product_id', 0))
        except (TypeError, ValueError):
            continue
        if pid > 0:
            favorite_ids.append(pid)
    popular_items = _popular_products_for_favorites(db, favorite_ids, 6)
    if not popular_items and favorite_ids:
        popular_items = _popular_products_for_favorites(db, [], 6)
    return render_template('favorites.html', items=items, popular_items=popular_items)


@main.route('/sevimlilar/qoshish', methods=['POST'])
def favorites_add():
    data = request.get_json(silent=True) or {}
    try:
        product_id = int(data.get('product_id', 0))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Mahsulot xato'}), 400

    if product_id <= 0:
        return jsonify({'success': False, 'error': 'Mahsulot xato'}), 400

    db = get_db()
    product = db.execute(
        'SELECT id,name,slug,image,price,old_price,is_active FROM product WHERE id=?',
        (product_id,)
    ).fetchone()
    if not product or not product['is_active']:
        return jsonify({'success': False, 'error': 'Mahsulot topilmadi'}), 404

    variant_id = data.get('variant_id')
    variant_label = ''
    key = str(product_id)
    price = float(product['price'] or 0)
    if variant_id not in (None, '', 'null'):
        try:
            variant_id = int(variant_id)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'Variant xato'}), 400
        variant = db.execute(
            'SELECT id,label FROM product_variants WHERE id=? AND product_id=?',
            (variant_id, product_id)
        ).fetchone()
        if not variant:
            return jsonify({'success': False, 'error': 'Variant topilmadi'}), 404
        variant_label = variant['label']

    image_path = _get_primary_image(db, product_id, product['image'])
    favorites_map = _ensure_favorites(db)
    already_exists = key in favorites_map

    if not already_exists:
        favorites_map[key] = {
            'key': key,
            'product_id': product_id,
            'slug': product['slug'],
            'name': product['name'],
            'variant': variant_label,
            'image': image_path,
            'price': int(round(price)),
            'old_price': int(round(float(product['old_price']))) if product['old_price'] and float(product['old_price']) > price else None,
        }
        db.execute(
            'UPDATE product SET cart_add_count = COALESCE(cart_add_count, 0) + 1 WHERE id=?',
            (product_id,)
        )
        db.commit()
        session['favorites'] = favorites_map
        session.modified = True
    elif variant_label and not favorites_map[key].get('variant'):
        favorites_map[key]['variant'] = variant_label
        session['favorites'] = favorites_map
        session.modified = True

    return jsonify({
        'success': True,
        'key': key,
        'exists': already_exists,
        'favorites_count': len(favorites_map),
    })


@main.route('/sevimlilar/olib-tashlash', methods=['POST'])
def favorites_remove():
    data = request.get_json(silent=True) or {}
    key = str(data.get('key', '')).strip()
    db = get_db()
    favorites_map = _ensure_favorites(db)
    if key:
        favorites_map.pop(key, None)
    session['favorites'] = favorites_map
    session.modified = True
    return jsonify({'success': True, 'favorites_count': len(favorites_map)})
