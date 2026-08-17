import pytest

import app.database as database_module
from app.database import get_db


class _FakeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_get_db_yields_a_session_and_closes_it_on_teardown(monkeypatch):
    """get_db()がセッションを1つyieldし、呼び出し側の処理が終わった後（finally節）で
    close()されることを確認する。他のテストはFastAPIのDIでこの関数自体を丸ごと
    差し替えているため、本番で使われる実体を直接検証する唯一のテスト。"""
    fake_session = _FakeSession()
    monkeypatch.setattr(database_module, "SessionLocal", lambda: fake_session)

    generator = get_db()
    db = next(generator)
    assert db is fake_session
    assert fake_session.closed is False

    with pytest.raises(StopIteration):
        next(generator)
    assert fake_session.closed is True
