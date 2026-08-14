import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import google_auth
from app.database import Base, get_db
from app.exceptions import UnauthorizedError
from app.main import app
from app.models.admin_user import AdminUser

ADMIN_EMAIL = "25.m.kitano.nutfes@gmail.com"

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    # SQLite ignores FK constraints (incl. ON DELETE CASCADE) unless this is set per-connection.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


def fake_google_id_token(email: str) -> str:
    """Stand-in for a real Google-signed ID token in tests — see
    _fake_verify_google_id_token below, which is the only thing that ever
    "verifies" it. Real Google verification is never exercised in tests."""
    return f"faketoken:{email}"


def _fake_verify_google_id_token(raw_token: str) -> str:
    if not raw_token.startswith("faketoken:"):
        raise UnauthorizedError("invalid Google ID token")
    email = raw_token.removeprefix("faketoken:")
    if not google_auth.NUTFES_EMAIL_PATTERN.match(email):
        raise UnauthorizedError("メールアドレスの形式が実行委員の規則に合致しません")
    return email


@pytest.fixture(autouse=True)
def _reset_db(monkeypatch):
    monkeypatch.setattr(google_auth, "verify_google_id_token", _fake_verify_google_id_token)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_user():
    db = TestingSessionLocal()
    try:
        user = AdminUser(email=ADMIN_EMAIL)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


@pytest.fixture
def admin_token(client, admin_user):
    response = client.post("/api/v1/auth/google", json={"id_token": fake_google_id_token(ADMIN_EMAIL)})
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
