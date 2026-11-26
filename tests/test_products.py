import pytest


def test_create_product(client):
    r = client.post(
        "/products",
        json={
            "name": "Smart Watch",
            "description": "Tracks things",
            "price": "199.99",
            "stock": 10,
            "category": "Electronics",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["id"] > 0
    assert body["name"] == "Smart Watch"
    assert body["price"] == "199.99"
    assert body["created_at"] and body["updated_at"]


def test_list_products(client, make_product):
    make_product(name="A", category="Home")
    make_product(name="B", category="Tech")
    r = client.get("/products")
    assert r.status_code == 200
    assert [p["name"] for p in r.json()] == ["A", "B"]

    r = client.get("/products", params={"category": "Tech"})
    assert [p["name"] for p in r.json()] == ["B"]


def test_get_product(client, make_product):
    p = make_product(name="Laptop", price="999.00")
    r = client.get(f"/products/{p['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "Laptop"


def test_get_product_not_found(client):
    r = client.get("/products/9999")
    assert r.status_code == 404
    err = r.json()["error"]
    assert err["code"] == "not_found"
    assert err["message"] == "Product not found"


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"price": "0"},
        {"price": "-5"},
        {"price": "1.234"},
        {"stock": -1},
        {"category": ""},
    ],
)
def test_create_product_validation(client, overrides):
    payload = {"name": "X", "price": "5.00", "stock": 1, "category": "C", **overrides}
    r = client.post("/products", json=payload)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
