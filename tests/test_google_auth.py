import base64
import json

import pytest

from app import google_auth as google_auth_module
from app.config import settings
from app.exceptions import UnauthorizedError
from app.google_auth import label_from_email, verify_google_id_token

# `verify_google_id_token`/`label_from_email` are imported directly by name
# above, capturing the real function objects at module-import time. This
# matters because tests/conftest.py's autouse fixture replaces
# app.google_auth.verify_google_id_token with a hand-written fake for every
# test in the suite (so the rest of the suite doesn't depend on Google's
# servers) — without this direct-reference trick, calls here would exercise
# the fake instead of the real verification logic and this file would test
# nothing.


def _patch_google_verify(monkeypatch, *, payload=None, raises=None):
    """google-auth SDKの低レベル呼び出し（verify_oauth2_token）だけを差し替えるヘルパー。
    verify_google_id_token自体は本物のまま、Googleサーバーとの通信部分だけを模擬する。"""

    def _fake_verify_oauth2_token(raw_token, request, client_id):
        if raises is not None:
            raise raises
        return payload

    monkeypatch.setattr(google_auth_module.google_id_token, "verify_oauth2_token", _fake_verify_oauth2_token)


def test_verify_google_id_token_accepts_valid_nutfes_account(monkeypatch):
    """検証済み・NUTFes形式のGoogleアカウントであれば、小文字化したメールアドレスを返すことを確認する"""
    _patch_google_verify(monkeypatch, payload={"email": "25.M.Kitano.nutfes@gmail.com", "email_verified": True})
    assert verify_google_id_token("dummy-token") == "25.m.kitano.nutfes@gmail.com"


def test_verify_google_id_token_rejects_unverified_email(monkeypatch):
    """Google側でメールアドレスが未検証（email_verified=False）の場合は拒否されることを確認する"""
    _patch_google_verify(
        monkeypatch, payload={"email": "25.m.kitano.nutfes@gmail.com", "email_verified": False}
    )
    with pytest.raises(UnauthorizedError):
        verify_google_id_token("dummy-token")


def test_verify_google_id_token_rejects_missing_email(monkeypatch):
    """トークンのペイロードにメールアドレス自体が含まれない場合は拒否されることを確認する"""
    _patch_google_verify(monkeypatch, payload={"email_verified": True})
    with pytest.raises(UnauthorizedError):
        verify_google_id_token("dummy-token")


def test_verify_google_id_token_rejects_non_nutfes_format(monkeypatch):
    """検証済みではあるが実行委員のメール形式（NN.x.lastname.nutfes@gmail.com）に合致しない
    アカウントは拒否されることを確認する"""
    _patch_google_verify(monkeypatch, payload={"email": "someone@gmail.com", "email_verified": True})
    with pytest.raises(UnauthorizedError):
        verify_google_id_token("dummy-token")


def test_verify_google_id_token_rejects_invalid_token(monkeypatch):
    """Google側の署名検証自体が失敗する（不正・改ざん・期限切れの）トークンは拒否されることを確認する"""
    _patch_google_verify(monkeypatch, raises=ValueError("Token expired"))
    with pytest.raises(UnauthorizedError):
        verify_google_id_token("dummy-token")


def _make_unverified_token(payload: dict) -> str:
    """Builds a JWT-shaped (but unsigned/garbage-signature) token — exactly
    what Playwright's GSI mock sends in test mode, since it can't produce a
    real Google-signed token."""
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"header.{payload_b64}.signature"


def test_verify_google_id_token_in_test_mode_bypasses_real_verification(monkeypatch):
    """google_auth_test_mode=Trueの場合、Googleへの実署名検証を一切呼ばずに
    トークンのペイロードをそのまま信頼することを確認する（E2E用のバイパス経路）"""
    monkeypatch.setattr(settings, "google_auth_test_mode", True)

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("real Google verification must not be called in test mode")

    monkeypatch.setattr(google_auth_module.google_id_token, "verify_oauth2_token", _fail_if_called)

    token = _make_unverified_token({"email": "25.M.Kitano.nutfes@gmail.com", "email_verified": True})
    assert verify_google_id_token(token) == "25.m.kitano.nutfes@gmail.com"


def test_verify_google_id_token_in_test_mode_still_enforces_nutfes_format(monkeypatch):
    """テストモードでも、NUTFes形式チェックなど後続のバリデーションはバイパスされないことを確認する"""
    monkeypatch.setattr(settings, "google_auth_test_mode", True)

    token = _make_unverified_token({"email": "someone@gmail.com", "email_verified": True})
    with pytest.raises(UnauthorizedError):
        verify_google_id_token(token)


def test_verify_google_id_token_in_test_mode_rejects_malformed_token(monkeypatch):
    """テストモードでも、JWTの形をしていない文字列は拒否されることを確認する"""
    monkeypatch.setattr(settings, "google_auth_test_mode", True)

    with pytest.raises(UnauthorizedError):
        verify_google_id_token("not-a-jwt-shaped-string")


def test_label_from_email_extracts_label():
    """NUTFes形式のメールアドレスから「学年.頭文字.姓」のラベル部分を取り出せることを確認する"""
    assert label_from_email("25.m.kitano.nutfes@gmail.com") == "25.m.kitano"


def test_label_from_email_rejects_non_nutfes_format():
    """NUTFes形式に合致しないメールアドレスを渡すとValueErrorになることを確認する
    （呼び出し側が事前チェックを怠った場合に備えた防御的分岐）"""
    with pytest.raises(ValueError):
        label_from_email("not-nutfes@gmail.com")
