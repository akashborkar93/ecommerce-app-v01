from decimal import Decimal


def _stock(client, product_id):
    return client.get(f"/products/{product_id}").json()["stock"]


def test_create_order_calculates_total_server_side(client, customer, make_product):
    a = make_product(name="A", price="10.50", stock=5)
    b = make_product(name="B", price="3.25", stock=10)
    r = client.post(
        "/orders",
        json={
            "customer_id": customer["id"],
            "items": [
                {"product_id": a["id"], "quantity": 2},
                {"product_id": b["id"], "quantity": 4},
            ],
            # A client-supplied total must be ignored.
            "total_amount": "0.01",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert Decimal(body["total_amount"]) == Decimal("34.00")
    assert body["status"] == "pending"
    assert len(body["items"]) == 2
    assert _stock(client, a["id"]) == 3
    assert _stock(client, b["id"]) == 6


def test_duplicate_lines_are_merged(client, customer, make_product):
    p = make_product(price="2.00", stock=5)
    r = client.post(
        "/orders",
        json={
            "customer_id": customer["id"],
            "items": [{"product_id": p["id"], "quantity": 2}, {"product_id": p["id"], "quantity": 1}],
        },
    )
    assert r.status_code == 201
    assert len(r.json()["items"]) == 1
    assert r.json()["items"][0]["quantity"] == 3
    assert _stock(client, p["id"]) == 2


def test_get_order(client, customer, make_product):
    p = make_product()
    created = client.post(
        "/orders",
        json={"customer_id": customer["id"], "items": [{"product_id": p["id"], "quantity": 1}]},
    ).json()
    r = client.get(f"/orders/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]
    assert r.json()["items"][0]["product_id"] == p["id"]


def test_get_order_not_found(client):
    r = client.get("/orders/9999")
    assert r.status_code == 404
    assert r.json()["error"]["message"] == "Order not found"


def test_list_orders(client, customer, make_product):
    p = make_product(stock=10)
    for _ in range(2):
        client.post(
            "/orders",
            json={"customer_id": customer["id"], "items": [{"product_id": p["id"], "quantity": 1}]},
        )
    r = client.get("/orders")
    assert r.status_code == 200
    assert len(r.json()) == 2
    assert len(client.get("/orders", params={"customer_id": customer["id"] + 1}).json()) == 0


def test_order_invalid_product(client, customer):
    r = client.post(
        "/orders",
        json={"customer_id": customer["id"], "items": [{"product_id": 9999, "quantity": 1}]},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_order"


def test_order_invalid_customer(client, make_product):
    p = make_product()
    r = client.post(
        "/orders",
        json={"customer_id": 9999, "items": [{"product_id": p["id"], "quantity": 1}]},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_order"


def test_order_insufficient_stock_is_atomic(client, customer, make_product):
    plenty = make_product(name="Plenty", stock=10)
    scarce = make_product(name="Scarce", stock=1)
    r = client.post(
        "/orders",
        json={
            "customer_id": customer["id"],
            "items": [
                {"product_id": plenty["id"], "quantity": 3},
                {"product_id": scarce["id"], "quantity": 2},
            ],
        },
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "insufficient_stock"
    # Nothing was decremented and no order was persisted.
    assert _stock(client, plenty["id"]) == 10
    assert _stock(client, scarce["id"]) == 1
    assert client.get("/orders").json() == []


def test_order_validation_errors(client, customer, make_product):
    p = make_product()
    for items in ([], [{"product_id": p["id"], "quantity": 0}]):
        r = client.post("/orders", json={"customer_id": customer["id"], "items": items})
        assert r.status_code == 422
