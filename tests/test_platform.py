import json
import logging

from app.core.logging import JsonFormatter


def test_customer_duplicate_email_conflict(client, customer):
    r = client.post("/customers", json={"name": "Other", "email": "ADA@example.com"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


def test_customer_invalid_email(client):
    r = client.post("/customers", json={"name": "X", "email": "not-an-email"})
    assert r.status_code == 422


def test_list_customers(client, customer):
    r = client.get("/customers")
    assert r.status_code == 200
    assert [item["email"] for item in r.json()] == [customer["email"]]


def test_request_id_is_echoed_and_generated(client):
    r = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["x-request-id"] == "abc123"
    assert client.get("/health").headers["x-request-id"]


def test_error_response_includes_request_id(client):
    r = client.get("/products/9999", headers={"X-Request-ID": "trace-1"})
    assert r.json()["error"]["request_id"] == "trace-1"


def test_unexpected_error_returns_generic_500(client, caplog):
    from app.db.session import get_db
    from app.main import app

    class Exploding:
        def scalars(self, *_a, **_k):
            raise RuntimeError("password=hunter2 host=10.0.0.5")

    def exploding_db():
        yield Exploding()

    app.dependency_overrides[get_db] = exploding_db
    with caplog.at_level(logging.ERROR):
        r = client.get("/products")
    assert r.status_code == 500
    body = r.json()["error"]
    assert body["code"] == "internal_error"
    assert "hunter2" not in r.text and "10.0.0.5" not in r.text
    # The real error is logged internally.
    assert any("unhandled exception" in rec.getMessage() for rec in caplog.records)


def test_request_log_contains_expected_fields(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.get("/products", headers={"X-Request-ID": "log-1"})
    rec = next(r for r in caplog.records if r.name == "app.request")
    line = json.loads(JsonFormatter("svc").format(rec))
    assert line["service"] == "svc"
    assert line["method"] == "GET"
    assert line["path"] == "/products"
    assert line["status_code"] == 200
    assert "duration_ms" in line and "timestamp" in line and line["level"] == "INFO"
