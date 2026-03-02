import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as app_module


def _seed_catalog_tree(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS product_categories (
            product_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            PRIMARY KEY (product_id, category_id),
            FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES category(id) ON DELETE CASCADE
        )
        """
    )

    db.executescript(
        """
        DELETE FROM product_categories;
        DELETE FROM product_images;
        DELETE FROM product_variants;
        DELETE FROM product;
        DELETE FROM category;
        """
    )

    categories = [
        (1, "Ziravorlar", "tur-ziravod", "🌶️", "ziravod", "Root type", 1, None, 1),
        (2, "Urug'lar", "tur-urug", "🌱", "urug", "Root type", 2, None, 1),
        (3, "Ziravor", "ziravor", "🌿", "ziravod", "", 1, 1, 0),
        (4, "Dorivor", "dorivor", "🌿", "ziravod", "", 2, 3, 0),
        (5, "Osimlik", "osimlik", "🌿", "ziravod", "", 3, 4, 0),
        (6, "Subosimlik", "subosimlik", "🌿", "ziravod", "", 4, 5, 0),
        (7, "Moylar", "moylar", "🫙", "ziravod", "", 5, 1, 0),
    ]
    db.executemany(
        """
        INSERT INTO category (
            id, name, slug, icon, type, description, sort_order, parent_id, is_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        categories,
    )

    db.execute(
        """
        INSERT INTO product (id, name, slug, category_id, description, price, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (1, "Test mahsulot", "test-mahsulot", 6, "Regression seed product", 10000, 1),
    )
    db.execute(
        "INSERT INTO product_categories (product_id, category_id) VALUES (?, ?)",
        (1, 6),
    )
    db.commit()


@pytest.fixture()
def app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DATABASE", str(db_path))

    flask_app = app_module.create_app()
    flask_app.config.update(TESTING=True)

    with flask_app.app_context():
        db = app_module.get_db()
        _seed_catalog_tree(db)

    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()
