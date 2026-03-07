import os
import sqlite3
from datetime import datetime
from flask import Flask, g, session, url_for

DATABASE = os.path.join(os.path.dirname(__file__), '..', 'herb.db')
CONTACT_SETTINGS_DEFAULTS = {
    'contact_phone_raw': '+998901234567',
    'contact_phone_display': '',
    'contact_telegram_url': '',
    'contact_telegram_label': '',
    'contact_instagram_url': '',
    'contact_instagram_label': '',
    'contact_location_url': '',
    'contact_location_label': '',
}

def get_db():
    if 'db' not in g:
        database_path = os.getenv('HERB_DB_PATH', DATABASE)
        os.makedirs(os.path.dirname(os.path.abspath(database_path)), exist_ok=True)
        g.db = sqlite3.connect(database_path, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db(app):
    with app.app_context():
        db = get_db()
        db.executescript("""
            CREATE TABLE IF NOT EXISTS admin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS category (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                icon TEXT DEFAULT '🌿',
                type TEXT DEFAULT 'ziravod',
                description TEXT,
                sort_order INTEGER DEFAULT 0,
                parent_id INTEGER,
                is_type INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS product (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                category_id INTEGER,
                description TEXT,
                origin TEXT,
                benefits TEXT,
                usage_tips TEXT,
                price REAL NOT NULL DEFAULT 0,
                old_price REAL,
                image TEXT,
                is_featured INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                is_organic INTEGER DEFAULT 0,
                stock INTEGER DEFAULT 100,
                unit_type TEXT DEFAULT 'dona',
                min_amount REAL DEFAULT 1,
                view_count INTEGER DEFAULT 0,
                cart_add_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (category_id) REFERENCES category(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS product_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                label TEXT NOT NULL,
                price REAL NOT NULL,
                old_price REAL,
                promo_end_date TEXT,
                promo_start_at TEXT,
                promo_end_at TEXT,
                scheduled_price REAL,
                stock INTEGER DEFAULT 100,
                min_amount REAL DEFAULT 1,
                FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS product_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                is_primary INTEGER DEFAULT 0,
                order_index INTEGER DEFAULT 0,
                FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                description TEXT,
                start_date TEXT,
                end_date TEXT,
                sort_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS product_collections (
                product_id INTEGER NOT NULL,
                collection_id INTEGER NOT NULL,
                PRIMARY KEY (product_id, collection_id),
                FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE,
                FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS banners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                subtitle TEXT,
                image_path TEXT NOT NULL,
                collection_id INTEGER,
                button_text TEXT,
                button_link TEXT,
                sort_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                address TEXT,
                note TEXT,
                status TEXT DEFAULT 'yangi',
                total REAL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER,
                product_name TEXT,
                variant_label TEXT,
                price REAL,
                qty INTEGER DEFAULT 1,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS site_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );
        """)
        # Backward-compatible migrations for older DB files
        product_cols = {r[1] for r in db.execute('PRAGMA table_info(product)').fetchall()}
        if 'unit_type' not in product_cols:
            db.execute("ALTER TABLE product ADD COLUMN unit_type TEXT DEFAULT 'dona'")
        if 'min_amount' not in product_cols:
            db.execute("ALTER TABLE product ADD COLUMN min_amount REAL DEFAULT 1")
        if 'view_count' not in product_cols:
            db.execute("ALTER TABLE product ADD COLUMN view_count INTEGER DEFAULT 0")
        if 'cart_add_count' not in product_cols:
            db.execute("ALTER TABLE product ADD COLUMN cart_add_count INTEGER DEFAULT 0")

        category_cols = {r[1] for r in db.execute('PRAGMA table_info(category)').fetchall()}
        if 'parent_id' not in category_cols:
            db.execute('ALTER TABLE category ADD COLUMN parent_id INTEGER')
        if 'is_type' not in category_cols:
            db.execute('ALTER TABLE category ADD COLUMN is_type INTEGER DEFAULT 0')

        db.execute('UPDATE category SET is_type=COALESCE(is_type, 0)')

        root_defaults = {
            'ziravod': ('Ziravorlar', '🌶️'),
            'urug': ("Urug'lar", '🌱'),
            'boshqa': ('Boshqa', '📦'),
        }
        legacy_types = [
            (r[0] or '').strip() for r in db.execute(
                "SELECT DISTINCT type FROM category WHERE type IS NOT NULL AND trim(type)<>''"
            ).fetchall()
        ]
        for type_slug in legacy_types:
            if not type_slug:
                continue
            root = db.execute(
                'SELECT id FROM category '
                'WHERE COALESCE(is_type,0)=1 AND parent_id IS NULL AND type=? '
                'LIMIT 1',
                (type_slug,)
            ).fetchone()
            if root:
                root_id = root['id']
            else:
                name, icon = root_defaults.get(
                    type_slug,
                    (type_slug.replace('-', ' ').title(), '🧭')
                )
                base_slug = f'tur-{type_slug}'
                slug = base_slug
                i = 2
                while db.execute('SELECT 1 FROM category WHERE slug=?', (slug,)).fetchone():
                    slug = f'{base_slug}-{i}'
                    i += 1
                cur = db.execute(
                    'INSERT INTO category (name,slug,icon,type,description,sort_order,parent_id,is_type) '
                    'VALUES (?,?,?,?,?,?,?,1)',
                    (name, slug, icon, type_slug, '', -100, None)
                )
                root_id = cur.lastrowid

            db.execute(
                'UPDATE category SET parent_id=? '
                'WHERE COALESCE(is_type,0)=0 '
                'AND (parent_id IS NULL OR parent_id="") '
                'AND type=?',
                (root_id, type_slug)
            )

        variant_cols = {r[1] for r in db.execute('PRAGMA table_info(product_variants)').fetchall()}
        if 'old_price' not in variant_cols:
            db.execute('ALTER TABLE product_variants ADD COLUMN old_price REAL')
        if 'promo_end_date' not in variant_cols:
            db.execute('ALTER TABLE product_variants ADD COLUMN promo_end_date TEXT')
        if 'promo_start_at' not in variant_cols:
            db.execute('ALTER TABLE product_variants ADD COLUMN promo_start_at TEXT')
        if 'promo_end_at' not in variant_cols:
            db.execute('ALTER TABLE product_variants ADD COLUMN promo_end_at TEXT')
        if 'scheduled_price' not in variant_cols:
            db.execute('ALTER TABLE product_variants ADD COLUMN scheduled_price REAL')
        if 'stock' not in variant_cols:
            db.execute('ALTER TABLE product_variants ADD COLUMN stock INTEGER DEFAULT 100')
        if 'min_amount' not in variant_cols:
            db.execute('ALTER TABLE product_variants ADD COLUMN min_amount REAL DEFAULT 1')
        db.execute(
            "UPDATE product_variants SET promo_end_at=promo_end_date "
            "WHERE (promo_end_at IS NULL OR promo_end_at='') "
            "AND promo_end_date IS NOT NULL AND promo_end_date<>''"
        )

        banner_cols = {r[1] for r in db.execute('PRAGMA table_info(banners)').fetchall()}
        if banner_cols:
            if 'collection_id' not in banner_cols:
                db.execute('ALTER TABLE banners ADD COLUMN collection_id INTEGER')
            if 'button_text' not in banner_cols:
                db.execute('ALTER TABLE banners ADD COLUMN button_text TEXT')
            if 'button_link' not in banner_cols:
                db.execute('ALTER TABLE banners ADD COLUMN button_link TEXT')
            if 'sort_order' not in banner_cols:
                db.execute('ALTER TABLE banners ADD COLUMN sort_order INTEGER DEFAULT 0')
            if 'is_active' not in banner_cols:
                db.execute('ALTER TABLE banners ADD COLUMN is_active INTEGER DEFAULT 1')
            if 'subtitle' not in banner_cols:
                db.execute('ALTER TABLE banners ADD COLUMN subtitle TEXT')

        collection_cols = {r[1] for r in db.execute('PRAGMA table_info(collections)').fetchall()}
        if collection_cols:
            if 'description' not in collection_cols:
                db.execute('ALTER TABLE collections ADD COLUMN description TEXT')
            if 'start_date' not in collection_cols:
                db.execute('ALTER TABLE collections ADD COLUMN start_date TEXT')
            if 'end_date' not in collection_cols:
                db.execute('ALTER TABLE collections ADD COLUMN end_date TEXT')
            if 'sort_order' not in collection_cols:
                db.execute('ALTER TABLE collections ADD COLUMN sort_order INTEGER DEFAULT 0')
            if 'is_active' not in collection_cols:
                db.execute('ALTER TABLE collections ADD COLUMN is_active INTEGER DEFAULT 1')

        # Fill new variant fields from product-level values for existing records
        db.execute(
            'UPDATE product_variants SET old_price = ('
            'SELECT p.old_price FROM product p WHERE p.id = product_variants.product_id'
            ') WHERE old_price IS NULL'
        )
        db.execute(
            'UPDATE product_variants SET stock = COALESCE(stock, ('
            'SELECT p.stock FROM product p WHERE p.id = product_variants.product_id'
            '), 100)'
        )
        db.execute(
            'UPDATE product_variants SET min_amount = COALESCE(min_amount, ('
            'SELECT p.min_amount FROM product p WHERE p.id = product_variants.product_id'
            '), 1)'
        )
        # Keep product.image aligned with primary gallery image
        db.execute(
            'UPDATE product SET image = ('
            'SELECT pi.image_path FROM product_images pi '
            'WHERE pi.product_id = product.id '
            'ORDER BY pi.is_primary DESC, pi.order_index, pi.id LIMIT 1'
            ') WHERE EXISTS (SELECT 1 FROM product_images pi WHERE pi.product_id = product.id)'
        )
        for key, value in CONTACT_SETTINGS_DEFAULTS.items():
            db.execute('INSERT OR IGNORE INTO site_settings (key, value) VALUES (?, ?)', (key, value))
        db.commit()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv('SECRET_KEY', 'herbmarket-secret-2024')
    app.config['UPLOAD_FOLDER'] = os.getenv(
        'UPLOAD_FOLDER',
        os.path.join(os.path.dirname(__file__), 'static', 'img', 'products'),
    )
    app.config['BANNER_UPLOAD_FOLDER'] = os.getenv(
        'BANNER_UPLOAD_FOLDER',
        os.path.join(os.path.dirname(__file__), 'static', 'img', 'banners'),
    )
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['BANNER_UPLOAD_FOLDER'], exist_ok=True)
    app.teardown_appcontext(close_db)
    init_db(app)

    with app.app_context():
        db = get_db()
        if not db.execute('SELECT 1 FROM admin WHERE username=?', ('admin',)).fetchone():
            from werkzeug.security import generate_password_hash
            db.execute('INSERT INTO admin (username,password_hash) VALUES (?,?)',
                       ('admin', generate_password_hash('admin')))
            # Demo kategoriyalar
            cats = [
                ('Ziravorlar', 'ziravorlar', '🌶️', 'ziravod', 'Tabiiy quritilgan ziravorlar'),
                ('Dorivorlar', 'dorivorlar', '🌿', 'dorivod', 'Shifobaxsh o\'tlar va dorivor o\'simliklar'),
                ('Urug\'lar', 'uruglar', '🌱', 'urug', 'Ekiladigan va iste\'mol urug\'lari'),
                ('Choylar', 'choylar', '🍵', 'choy', 'Shifobaxsh o\'simlik choylari'),
                ('Moylar', 'moylar', '🫙', 'moy', 'Tabiiy o\'simlik moylari va ekstraktlari'),
            ]
            for c in cats:
                try:
                    db.execute('INSERT INTO category (name,slug,icon,type,description) VALUES (?,?,?,?,?)', c)
                except: pass
            db.commit()

    @app.before_request
    def set_session():
        g.theme = session.get('theme', 'light')
        db = get_db()
        rows = db.execute(
            'SELECT id,price,old_price,promo_start_at,promo_end_at,promo_end_date,scheduled_price '
            'FROM product_variants '
            'WHERE promo_start_at IS NOT NULL OR promo_end_at IS NOT NULL '
            'OR promo_end_date IS NOT NULL OR scheduled_price IS NOT NULL'
        ).fetchall()
        now = datetime.now()

        def parse_dt(value):
            if not value:
                return None
            raw = str(value).strip()
            if not raw:
                return None
            raw = raw.replace(' ', 'T')
            try:
                return datetime.fromisoformat(raw)
            except Exception:
                return None

        changed = False
        for r in rows:
            price = r['price']
            old_price = r['old_price']
            scheduled_price = r['scheduled_price']
            promo_start_at = (r['promo_start_at'] or '').strip() if r['promo_start_at'] else None
            promo_end_at = (r['promo_end_at'] or '').strip() if r['promo_end_at'] else None
            legacy_end = (r['promo_end_date'] or '').strip() if r['promo_end_date'] else None
            row_changed = False

            if not promo_end_at and legacy_end:
                promo_end_at = legacy_end
                row_changed = True

            start_dt = parse_dt(promo_start_at)
            end_dt = parse_dt(promo_end_at)

            # 1) Tugagan aksiya: narxni oddiy holatga qaytaramiz.
            if end_dt and now > end_dt:
                if old_price is not None:
                    price = old_price
                    old_price = None
                scheduled_price = None
                promo_start_at = None
                promo_end_at = None
                row_changed = True
            # 2) Rejalashtirilgan aksiya boshlanishi.
            elif scheduled_price is not None:
                start_ok = (start_dt is None) or (now >= start_dt)
                end_ok = (end_dt is None) or (now <= end_dt)
                if start_ok and end_ok:
                    old_price = price
                    price = scheduled_price
                    scheduled_price = None
                    row_changed = True

            if row_changed:
                db.execute(
                    'UPDATE product_variants SET price=?, old_price=?, promo_start_at=?, promo_end_at=?, '
                    'scheduled_price=?, promo_end_date=NULL WHERE id=?',
                    (price, old_price, promo_start_at, promo_end_at, scheduled_price, r['id'])
                )
                changed = True

        if changed:
            db.execute(
                'UPDATE product SET '
                'price=COALESCE((SELECT v.price FROM product_variants v WHERE v.product_id=product.id ORDER BY v.id LIMIT 1), price), '
                'old_price=(SELECT v.old_price FROM product_variants v WHERE v.product_id=product.id ORDER BY v.id LIMIT 1) '
                'WHERE EXISTS (SELECT 1 FROM product_variants vv WHERE vv.product_id=product.id)'
            )
            db.commit()

    @app.context_processor
    def inject_globals():
        db = get_db()
        categories = db.execute(
            'SELECT * FROM category '
            'WHERE COALESCE(is_type,0)=0 '
            'ORDER BY sort_order, name'
        ).fetchall()
        has_product_categories = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='product_categories'"
        ).fetchone() is not None

        def top_footer_categories(type_slug, limit=5):
            if has_product_categories:
                return db.execute(
                    'SELECT c.id,c.name,c.slug,c.icon,COALESCE(SUM(COALESCE(src.view_count,0)),0) as total_views '
                    'FROM category c '
                    'LEFT JOIN ('
                    '  SELECT p.id as product_id,p.view_count,pc.category_id '
                    '  FROM product p JOIN product_categories pc ON pc.product_id=p.id '
                    '  WHERE p.is_active=1 '
                    '  UNION '
                    '  SELECT p.id as product_id,p.view_count,p.category_id '
                    '  FROM product p '
                    '  WHERE p.is_active=1 AND p.category_id IS NOT NULL'
                    ') src ON src.category_id=c.id '
                    'WHERE c.type=? AND COALESCE(c.is_type,0)=0 '
                    'GROUP BY c.id '
                    'ORDER BY total_views DESC, c.sort_order, c.name '
                    'LIMIT ?',
                    (type_slug, limit)
                ).fetchall()
            return db.execute(
                'SELECT c.id,c.name,c.slug,c.icon,COALESCE(SUM(COALESCE(p.view_count,0)),0) as total_views '
                'FROM category c '
                'LEFT JOIN product p ON p.category_id=c.id AND p.is_active=1 '
                'WHERE c.type=? AND COALESCE(c.is_type,0)=0 '
                'GROUP BY c.id '
                'ORDER BY total_views DESC, c.sort_order, c.name '
                'LIMIT ?',
                (type_slug, limit)
            ).fetchall()

        footer_top_ziravod = top_footer_categories('ziravod', 5)
        footer_top_urug = top_footer_categories('urug', 5)
        contact_settings = dict(CONTACT_SETTINGS_DEFAULTS)
        for row in db.execute('SELECT key, value FROM site_settings').fetchall():
            if row['key'] in contact_settings:
                contact_settings[row['key']] = row['value'] if row['value'] is not None else ''
        favorites = session.get('favorites', {})
        if not isinstance(favorites, dict):
            favorites = {}
        legacy_cart = session.get('cart', {})
        if not isinstance(legacy_cart, dict):
            legacy_cart = {}
        source = favorites if favorites else legacy_cart
        favorite_keys = []
        seen = set()
        for key, item in source.items():
            raw = None
            if isinstance(item, dict):
                raw = item.get('product_id')
            if raw in (None, ''):
                raw = str(key).split('_v', 1)[0]
            try:
                pid = int(raw)
            except (TypeError, ValueError):
                continue
            if pid <= 0:
                continue
            k = str(pid)
            if k in seen:
                continue
            seen.add(k)
            favorite_keys.append(k)
        favorites_count = len(favorite_keys)

        def asset_url(filename):
            asset_path = os.path.join(app.static_folder, filename)
            try:
                version = int(os.path.getmtime(asset_path))
            except OSError:
                return url_for('static', filename=filename)
            return url_for('static', filename=filename, v=version)

        return {
            'asset_url': asset_url,
            'categories': categories,
            'favorites_count': favorites_count,
            'favorite_keys': favorite_keys,
            'cart_count': favorites_count,
            'theme': g.get('theme', 'light'),
            'contact_settings': contact_settings,
            'footer_top_ziravod': footer_top_ziravod,
            'footer_top_urug': footer_top_urug,
        }

    from app.routes.main import main
    from app.routes.admin import admin as admin_bp
    app.register_blueprint(main)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    return app
