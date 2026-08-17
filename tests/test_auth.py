from app.auth import create_access_token
from app.models.admin_user import AdminUser
from app.repositories.admin_user_repository import AdminUserRepository
from tests.conftest import ADMIN_EMAIL, fake_google_id_token


def test_login_success_returns_access_token_and_sets_refresh_cookie(client, admin_user):
    """許可リストに登録済みのGoogleアカウントでログインすると、アクセストークンが返り、
    リフレッシュトークンのHttpOnly Cookieがセットされることを確認する"""
    response = client.post("/api/v1/auth/google", json={"id_token": fake_google_id_token(ADMIN_EMAIL)})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert "trapa_admin_rt" in response.cookies


def test_login_rejects_email_not_in_allowlist(client):
    """メール形式は正しくても、管理者許可リスト（admin_users）に登録されていないアカウントは
    ログインできないことを確認する"""
    # Correctly formatted NUTFes account, but never added via manage_admin_allowlist.py
    response = client.post(
        "/api/v1/auth/google", json={"id_token": fake_google_id_token("25.m.suzuki.nutfes@gmail.com")}
    )
    assert response.status_code == 401


def test_login_rejects_malformed_email(client):
    """実行委員のメール形式（NN.x.lastname.nutfes@gmail.com）に合致しないGoogleアカウントは
    ログインできないことを確認する"""
    response = client.post(
        "/api/v1/auth/google", json={"id_token": fake_google_id_token("not-a-nutfes-address@gmail.com")}
    )
    assert response.status_code == 401


def test_login_rejects_invalid_token(client):
    """Google IDトークンとして検証できない不正な値ではログインできないことを確認する"""
    response = client.post("/api/v1/auth/google", json={"id_token": "garbage"})
    assert response.status_code == 401


def test_me_requires_valid_access_token(client, admin_headers):
    """/auth/meはアクセストークンなしでは401になり、有効なトークンがあればログイン中の
    ユーザー情報を返すことを確認する"""
    assert client.get("/api/v1/auth/me").status_code == 401

    response = client.get("/api/v1/auth/me", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["email"] == ADMIN_EMAIL


def test_me_rejects_malformed_access_token(client):
    """JWTとして復号できない不正な文字列をアクセストークンとして送ると401になることを確認する"""
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_me_rejects_token_for_nonexistent_user(client):
    """署名自体は正しいが、紐づくユーザーIDがDBに存在しないアクセストークンは401になることを確認する
    （許可リストから削除された後も古いトークンが残っているケースを想定）"""
    ghost_token = create_access_token(AdminUser(id=999999, email="ghost@example.com"))
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ghost_token}"})
    assert response.status_code == 401


def test_refresh_issues_new_access_token_and_rotates_cookie(client, admin_user):
    """リフレッシュトークンを使うと新しいアクセストークンが発行され、リフレッシュトークン自体も
    ローテーション（使い捨て）されることを確認する"""
    client.post("/api/v1/auth/google", json={"id_token": fake_google_id_token(ADMIN_EMAIL)})
    old_rt_cookie = client.cookies.get("trapa_admin_rt")

    refreshed = client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]
    new_rt_cookie = client.cookies.get("trapa_admin_rt")
    assert new_rt_cookie != old_rt_cookie

    # The new access token authenticates against a protected endpoint.
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"})
    assert me.status_code == 200


def test_refresh_without_cookie_fails(client):
    """リフレッシュトークンのCookieが無い状態で/auth/refreshを呼ぶと401になることを確認する"""
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


def test_refresh_rejects_reused_rotated_token(client, admin_user):
    """一度使用（ローテーション）されて無効化されたリフレッシュトークンを再利用しようとすると
    401になることを確認する"""
    client.post("/api/v1/auth/google", json={"id_token": fake_google_id_token(ADMIN_EMAIL)})
    old_raw_cookie = client.cookies.get("trapa_admin_rt")

    first_refresh = client.post("/api/v1/auth/refresh")
    assert first_refresh.status_code == 200

    # Replay the original (now-rotated-out) refresh token — must be rejected.
    client.cookies.set("trapa_admin_rt", old_raw_cookie)
    replay = client.post("/api/v1/auth/refresh")
    assert replay.status_code == 401


def test_refresh_fails_when_admin_user_no_longer_exists(client, admin_user, monkeypatch):
    """リフレッシュトークン自体は有効でも、紐づく管理者ユーザーが見つからない場合は401になることを
    確認する（トークンだけが残って本人が許可リストから消えたケースを想定した防御的分岐）"""
    client.post("/api/v1/auth/google", json={"id_token": fake_google_id_token(ADMIN_EMAIL)})

    monkeypatch.setattr(AdminUserRepository, "get", lambda self, user_id: None)

    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


def test_logout_revokes_refresh_token(client, admin_user):
    """ログアウトするとリフレッシュトークンがサーバー側で失効し、以後の/auth/refreshが
    失敗することを確認する"""
    client.post("/api/v1/auth/google", json={"id_token": fake_google_id_token(ADMIN_EMAIL)})

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 204

    refresh_after_logout = client.post("/api/v1/auth/refresh")
    assert refresh_after_logout.status_code == 401


def test_logout_without_prior_login_is_a_noop(client):
    """一度もログインしていない状態（リフレッシュトークンのCookieなし）でログアウトを呼んでも、
    早期returnにより204で正常終了することを確認する"""
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204


def test_logout_with_unknown_refresh_token_is_a_noop(client):
    """DBに存在しないリフレッシュトークンでログアウトを呼んでも、エラーにならず204で
    正常終了することを確認する（該当レコードなし・失効済みレコードの場合の分岐）"""
    client.cookies.set("trapa_admin_rt", "no-such-token")
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204
