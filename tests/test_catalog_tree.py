import re


def _branch_classes(html, branch_id):
    pattern = rf'id="{re.escape(branch_id)}" class="([^"]+)"'
    match = re.search(pattern, html)
    assert match, f"Branch not found in HTML: {branch_id}"
    return match.group(1)


def test_home_and_catalog_pages_load(client):
    home = client.get("/")
    assert home.status_code == 200

    catalog = client.get("/katalog")
    assert catalog.status_code == 200

    html = catalog.get_data(as_text=True)
    assert "setupCatalogAccordion();" in html


def test_catalog_tree_default_closed_state(client):
    response = client.get("/katalog")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "catalog-tree-branch-inner" in html
    assert re.search(
        r'data-target="desktop-branch-1"\s+aria-expanded="false"',
        html,
    )

    root_classes = _branch_classes(html, "desktop-branch-1")
    assert "is-collapsed" in root_classes


def test_deep_category_opens_all_ancestors(client):
    response = client.get("/katalog?kategoriya=subosimlik")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    for branch_id in (
        "desktop-branch-1",
        "desktop-branch-3",
        "desktop-branch-4",
        "desktop-branch-5",
    ):
        classes = _branch_classes(html, branch_id)
        assert "is-collapsed" not in classes

    assert re.search(
        r'data-target="desktop-branch-5"\s+aria-expanded="true"',
        html,
    )
    assert "class=\"catalog-tree-link level-4 active\"" in html
