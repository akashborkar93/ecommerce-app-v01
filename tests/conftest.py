import os

# Settings must exist before app.main is imported. These are dummy test values only;
# the tests override the DB dependency and never connect to this host.
os.environ.setdefault("DATABASE_HOST", "test-db-unused")
os.environ.setdefault("DATABASE_NAME", "test")
os.environ.setdefault("DATABASE_USER", "test")
os.environ.setdefault("DATABASE_PASSWORD", "test")
os.environ.setdefault("LOG_LEVEL", "DEBUG")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import entities  # noqa: E402, F401


@pytest.fixture
def engine():
    # Set TEST_DATABASE_URL to run the same suite against a real PostgreSQL.
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        eng = create_engine(url)
    else:
        eng = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def client(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def customer(client):
    r = client.post("/customers", json={"name": "Ada", "email": "ada@example.com"})
    assert r.status_code == 201
    return r.json()


@pytest.fixture
def make_product(client):
    def _make(name="Widget", price="10.00", stock=5, category="Misc"):
        r = client.post(
            "/products",
            json={"name": name, "price": price, "stock": stock, "category": category},
        )
        assert r.status_code == 201, r.text
        return r.json()

    return _make
