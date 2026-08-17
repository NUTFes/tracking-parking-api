from tests.conftest import fake_google_id_token

ANOTHER_ADMIN_EMAIL = "24.k.tanaka.nutfes@gmail.com"


def test_list_admin_users_requires_admin(client, admin_headers):
    """許可ユーザー一覧の取得には管理者認証が必要で、未認証だと401になることを確認する"""
    response = client.get("/api/v1/admin-users")
    assert response.status_code == 401


def test_list_admin_users_returns_seeded_admin(client, admin_headers, admin_user):
    """ログイン中の管理者自身が許可ユーザー一覧に含まれることを確認する"""
    response = client.get("/api/v1/admin-users", headers=admin_headers)
    assert response.status_code == 200
    emails = [u["email"] for u in response.json()]
    assert admin_user.email in emails


def test_create_admin_user_requires_admin(client, admin_headers):
    """許可ユーザーの登録には管理者認証が必要で、未認証だと401になることを確認する"""
    response = client.post("/api/v1/admin-users", json={"email": ANOTHER_ADMIN_EMAIL})
    assert response.status_code == 401


def test_create_admin_user_registers_new_allowed_account(client, admin_headers):
    """新しいGoogleアカウントを許可リストに登録でき、そのアカウントで実際にログインできる
    ようになることを確認する（登録操作がAdminログインの許可リストと連動していることの検証）"""
    response = client.post("/api/v1/admin-users", json={"email": ANOTHER_ADMIN_EMAIL}, headers=admin_headers)
    assert response.status_code == 201
    assert response.json()["email"] == ANOTHER_ADMIN_EMAIL

    login = client.post("/api/v1/auth/google", json={"id_token": fake_google_id_token(ANOTHER_ADMIN_EMAIL)})
    assert login.status_code == 200


def test_create_admin_user_normalizes_email_case_and_whitespace(client, admin_headers):
    """登録時にメールアドレスの前後空白除去・小文字化が行われ、正規化された値が
    保存されることを確認する"""
    response = client.post(
        "/api/v1/admin-users", json={"email": f"  {ANOTHER_ADMIN_EMAIL.upper()}  "}, headers=admin_headers
    )
    assert response.status_code == 201
    assert response.json()["email"] == ANOTHER_ADMIN_EMAIL


def test_create_admin_user_rejects_non_nutfes_format(client, admin_headers):
    """実行委員のメール形式（NN.x.lastname.nutfes@gmail.com）に合致しないアドレスは
    登録できず、422になることを確認する"""
    response = client.post("/api/v1/admin-users", json={"email": "not-nutfes@gmail.com"}, headers=admin_headers)
    assert response.status_code == 422


def test_create_admin_user_rejects_duplicate_email(client, admin_headers):
    """既に許可リストへ登録済みのメールアドレスを重複登録しようとすると409になることを確認する"""
    client.post("/api/v1/admin-users", json={"email": ANOTHER_ADMIN_EMAIL}, headers=admin_headers)
    response = client.post("/api/v1/admin-users", json={"email": ANOTHER_ADMIN_EMAIL}, headers=admin_headers)
    assert response.status_code == 409


def test_delete_admin_user_requires_admin(client, admin_headers, admin_user):
    """許可ユーザーの削除には管理者認証が必要で、未認証だと401になることを確認する"""
    response = client.delete(f"/api/v1/admin-users/{admin_user.id}")
    assert response.status_code == 401


def test_delete_admin_user_removes_from_allowlist(client, admin_headers):
    """許可リストからアカウントを削除すると、それ以降はそのアカウントでログインできなく
    なることを確認する"""
    created = client.post(
        "/api/v1/admin-users", json={"email": ANOTHER_ADMIN_EMAIL}, headers=admin_headers
    ).json()

    response = client.delete(f"/api/v1/admin-users/{created['id']}", headers=admin_headers)
    assert response.status_code == 204

    login = client.post("/api/v1/auth/google", json={"id_token": fake_google_id_token(ANOTHER_ADMIN_EMAIL)})
    assert login.status_code == 401


def test_delete_admin_user_who_has_logged_in_still_succeeds(client, admin_headers):
    """一度でもログインしてリフレッシュトークンを発行済みのユーザーでも、削除できる
    （紐づくadmin_refresh_tokensがON DELETE CASCADEで一緒に消え、外部キー制約違反に
    ならない）ことを確認する"""
    created = client.post(
        "/api/v1/admin-users", json={"email": ANOTHER_ADMIN_EMAIL}, headers=admin_headers
    ).json()
    login = client.post("/api/v1/auth/google", json={"id_token": fake_google_id_token(ANOTHER_ADMIN_EMAIL)})
    assert login.status_code == 200
    assert "trapa_admin_rt" in login.cookies

    response = client.delete(f"/api/v1/admin-users/{created['id']}", headers=admin_headers)
    assert response.status_code == 204


def test_delete_admin_user_unknown_id_returns_404(client, admin_headers):
    """存在しないIDを指定して削除しようとすると404になることを確認する"""
    response = client.delete("/api/v1/admin-users/999999", headers=admin_headers)
    assert response.status_code == 404


def test_cannot_delete_the_last_remaining_admin_user(client, admin_headers, admin_user):
    """許可ユーザーが1人しかいない状態でその最後の1人を削除しようとすると409になり、
    管理コンソールへの入り口が失われないよう保護されることを確認する"""
    response = client.delete(f"/api/v1/admin-users/{admin_user.id}", headers=admin_headers)
    assert response.status_code == 409
