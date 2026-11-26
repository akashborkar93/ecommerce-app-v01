from app.db.session import get_db
from app.main import app


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


def test_ready_ok(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


def test_ready_fails_when_database_unavailable(client):
    class BrokenSession:
        def execute(self, *_a, **_k):
            raise RuntimeError("secret-host:5432 connection refused")

    def broken_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_db
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json() == {"status": "not_ready"}
    assert "secret-host" not in r.text

    # Liveness is independent of the database.
    assert client.get("/health").status_code == 200


def test_openapi_and_docs(client):
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
