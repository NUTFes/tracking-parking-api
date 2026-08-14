from tests.conftest import ADMIN_EMAIL, fake_google_id_token


def test_login_success_returns_access_token_and_sets_refresh_cookie(client, admin_user):
    response = client.post("/api/v1/auth/google", json={"id_token": fake_google_id_token(ADMIN_EMAIL)})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert "trapa_admin_rt" in response.cookies


def test_login_rejects_email_not_in_allowlist(client):
    # Correctly formatted NUTFes account, but never added via manage_admin_allowlist.py
    response = client.post(
        "/api/v1/auth/google", json={"id_token": fake_google_id_token("25.m.suzuki.nutfes@gmail.com")}
    )
    assert response.status_code == 401


def test_login_rejects_malformed_email(client):
    response = client.post(
        "/api/v1/auth/google", json={"id_token": fake_google_id_token("not-a-nutfes-address@gmail.com")}
    )
    assert response.status_code == 401


def test_login_rejects_invalid_token(client):
    response = client.post("/api/v1/auth/google", json={"id_token": "garbage"})
    assert response.status_code == 401


def test_me_requires_valid_access_token(client, admin_headers):
    assert client.get("/api/v1/auth/me").status_code == 401

    response = client.get("/api/v1/auth/me", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["email"] == ADMIN_EMAIL


def test_refresh_issues_new_access_token_and_rotates_cookie(client, admin_user):
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
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


def test_refresh_rejects_reused_rotated_token(client, admin_user):
    client.post("/api/v1/auth/google", json={"id_token": fake_google_id_token(ADMIN_EMAIL)})
    old_raw_cookie = client.cookies.get("trapa_admin_rt")

    first_refresh = client.post("/api/v1/auth/refresh")
    assert first_refresh.status_code == 200

    # Replay the original (now-rotated-out) refresh token — must be rejected.
    client.cookies.set("trapa_admin_rt", old_raw_cookie)
    replay = client.post("/api/v1/auth/refresh")
    assert replay.status_code == 401


def test_logout_revokes_refresh_token(client, admin_user):
    client.post("/api/v1/auth/google", json={"id_token": fake_google_id_token(ADMIN_EMAIL)})

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 204

    refresh_after_logout = client.post("/api/v1/auth/refresh")
    assert refresh_after_logout.status_code == 401
