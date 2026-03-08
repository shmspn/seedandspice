import app as app_module


def test_catalog_renders_card_gallery_for_multiple_images(app, client):
    with app.app_context():
        db = app_module.get_db()
        db.executemany(
            """
            INSERT INTO product_images (product_id, image_path, is_primary, order_index)
            VALUES (?, ?, ?, ?)
            """,
            [
                (1, "product-one.webp", 1, 0),
                (1, "product-two.webp", 0, 1),
            ],
        )
        db.commit()

    response = client.get("/katalog")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert 'data-pcard-gallery' in html
    assert 'product-one.webp' in html
    assert 'product-two.webp' in html
