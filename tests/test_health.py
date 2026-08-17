from app.database import get_db
from app.main import app


def test_health_check(client):
    """DB接続を含めて全て正常な場合、全体ステータス・DBステータスともにokになることを確認する"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_health_check_reports_degraded_when_db_query_fails(client, monkeypatch):
    """DBへの疎通確認クエリ（SELECT 1）が例外を投げた場合、全体ステータスがdegraded・
    databaseがerrorになることを確認する"""

    def _broken_get_db():
        class _BrokenSession:
            def execute(self, *args, **kwargs):
                raise RuntimeError("db is down")

        yield _BrokenSession()

    # monkeypatch.setitem restores the previous override (conftest.py's
    # _override_get_db) automatically once this test finishes.
    monkeypatch.setitem(app.dependency_overrides, get_db, _broken_get_db)

    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "error"
