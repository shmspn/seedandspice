import app as app_module


def _seed_collection_and_banner(
    db,
    *,
    collection_id,
    slug,
    title,
    banner_start_date=None,
    banner_end_date=None,
    collection_start_date=None,
    collection_end_date=None,
):
    db.execute(
        """
        INSERT INTO collections (id, name, slug, start_date, end_date, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (
            collection_id,
            f"Collection {collection_id}",
            slug,
            collection_start_date,
            collection_end_date,
        ),
    )
    db.execute(
        """
        INSERT INTO product_collections (product_id, collection_id)
        VALUES (?, ?)
        """,
        (1, collection_id),
    )
    db.execute(
        """
        INSERT INTO banners (title, image_path, collection_id, start_date, end_date, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (title, "banner.webp", collection_id, banner_start_date, banner_end_date),
    )
    db.commit()


def test_home_hides_banner_for_expired_banner_window(app, client):
    with app.app_context():
        db = app_module.get_db()
        _seed_collection_and_banner(
            db,
            collection_id=10,
            slug="expired-banner",
            title="Expired Promo",
            banner_end_date="2000-01-01",
        )

    home = client.get("/")
    assert home.status_code == 200
    html = home.get_data(as_text=True)

    assert "Expired Promo" not in html
    assert "/katalog?collection=expired-banner" not in html


def test_home_keeps_banner_for_active_banner_window(app, client):
    with app.app_context():
        db = app_module.get_db()
        _seed_collection_and_banner(
            db,
            collection_id=11,
            slug="active-banner",
            title="Active Promo",
            banner_end_date="2999-12-31",
        )

    home = client.get("/")
    assert home.status_code == 200
    html = home.get_data(as_text=True)

    assert "Active Promo" in html
    assert "/katalog?collection=active-banner" in html


def test_catalog_ignores_collection_dates_and_shows_products(app, client):
    with app.app_context():
        db = app_module.get_db()
        _seed_collection_and_banner(
            db,
            collection_id=12,
            slug="date-agnostic-collection",
            title="Scheduled Promo",
            banner_end_date="2999-12-31",
            collection_start_date="1999-01-01",
            collection_end_date="2000-01-01",
        )

    catalog = client.get("/katalog?collection=date-agnostic-collection")
    assert catalog.status_code == 200
    assert "Test mahsulot" in catalog.get_data(as_text=True)
