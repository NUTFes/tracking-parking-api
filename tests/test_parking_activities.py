from tests.conftest import fake_google_id_token

GENERAL_USER_EMAIL = "24.k.tanaka.nutfes@gmail.com"


def _general_headers(email: str = GENERAL_USER_EMAIL) -> dict:
    return {"Authorization": f"Bearer {fake_google_id_token(email)}"}


def _register_lot(client, admin_headers, capacity=10):
    return client.post(
        "/api/v1/parking-lots", json={"name": "Test Lot", "capacity": capacity}, headers=admin_headers
    ).json()


def test_reset_requires_admin(client, admin_headers):
    lot = _register_lot(client, admin_headers)
    response = client.post(f"/api/v1/parking-lots/{lot['id']}/reset", json={"count": 5})
    assert response.status_code == 401


def test_reset_sets_exact_count_and_logs_activity(client, admin_headers):
    lot = _register_lot(client, admin_headers)

    response = client.post(
        f"/api/v1/parking-lots/{lot['id']}/reset",
        json={"count": 7, "note": "実車確認による補正"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["current_count"] == 7

    activities = client.get(f"/api/v1/parking-lots/{lot['id']}/activities", headers=admin_headers).json()
    assert len(activities) == 1
    assert activities[0]["activity_type"] == "reset"
    assert activities[0]["delta"] == 7
    assert activities[0]["count_after"] == 7
    assert activities[0]["actor_label"] == "25.m.kitano"
    assert activities[0]["note"] == "実車確認による補正"


def test_reset_system_count_and_logs_activity(client, admin_headers):
    lot = _register_lot(client, admin_headers)

    response = client.post(
        f"/api/v1/parking-lots/{lot['id']}/reset",
        json={"count": 4, "target": "system", "note": "デバイスずれ補正"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["system_count"] == 4
    assert body["current_count"] == 0

    activities = client.get(f"/api/v1/parking-lots/{lot['id']}/activities", headers=admin_headers).json()
    assert len(activities) == 1
    assert activities[0]["activity_type"] == "system_reset"
    assert activities[0]["delta"] == 4
    assert activities[0]["count_after"] == 4


def test_reset_all_requires_admin(client, admin_headers):
    _register_lot(client, admin_headers)
    response = client.post("/api/v1/parking-lots/reset-all", json={"target": "current"})
    assert response.status_code == 401


def test_reset_all_zeroes_every_lot(client, admin_headers):
    lot1 = _register_lot(client, admin_headers)
    lot2 = client.post(
        "/api/v1/parking-lots", json={"name": "Test Lot 2", "capacity": 20}, headers=admin_headers
    ).json()
    client.post(f"/api/v1/parking-lots/{lot1['id']}/reset", json={"count": 3}, headers=admin_headers)
    client.post(f"/api/v1/parking-lots/{lot2['id']}/reset", json={"count": 9}, headers=admin_headers)

    response = client.post("/api/v1/parking-lots/reset-all", json={"target": "current"}, headers=admin_headers)
    assert response.status_code == 200
    lots = {lot["id"]: lot for lot in response.json()}
    assert lots[lot1["id"]]["current_count"] == 0
    assert lots[lot2["id"]]["current_count"] == 0

    activities = client.get(f"/api/v1/parking-lots/{lot1['id']}/activities", headers=admin_headers).json()
    assert activities[0]["activity_type"] == "reset"
    assert activities[0]["delta"] == -3
    assert activities[0]["count_after"] == 0


def test_adjust_requires_valid_google_token(client, admin_headers):
    lot = _register_lot(client, admin_headers)
    response = client.post(f"/api/v1/parking-lots/{lot['id']}/adjust", json={"delta": 1})
    assert response.status_code == 401


def test_adjust_rejects_malformed_email(client, admin_headers):
    lot = _register_lot(client, admin_headers)
    headers = {"Authorization": f"Bearer {fake_google_id_token('not-nutfes@gmail.com')}"}
    response = client.post(f"/api/v1/parking-lots/{lot['id']}/adjust", json={"delta": 1}, headers=headers)
    assert response.status_code == 401


def test_adjust_does_not_require_admin_allowlist(client, admin_headers):
    """A general user (any correctly-formatted NUTFes account) can adjust
    without ever being added to admin_users — only the email format matters."""
    lot = _register_lot(client, admin_headers)
    response = client.post(
        f"/api/v1/parking-lots/{lot['id']}/adjust", json={"delta": 3}, headers=_general_headers()
    )
    assert response.status_code == 200
    assert response.json()["current_count"] == 3


def test_adjust_increases_and_decreases_count(client, admin_headers):
    lot = _register_lot(client, admin_headers)
    client.post(f"/api/v1/parking-lots/{lot['id']}/adjust", json={"delta": 5}, headers=_general_headers())

    response = client.post(
        f"/api/v1/parking-lots/{lot['id']}/adjust", json={"delta": -2, "note": "出庫の記録漏れ"}, headers=_general_headers()
    )
    assert response.status_code == 200
    assert response.json()["current_count"] == 3

    activities = client.get(f"/api/v1/parking-lots/{lot['id']}/activities", headers=admin_headers).json()
    assert len(activities) == 2
    assert activities[0]["activity_type"] == "manual_adjustment"
    assert activities[0]["delta"] == -2
    assert activities[0]["actor_label"] == "24.k.tanaka"
    assert activities[0]["note"] == "出庫の記録漏れ"


def test_adjust_clamps_at_zero(client, admin_headers):
    lot = _register_lot(client, admin_headers)
    response = client.post(
        f"/api/v1/parking-lots/{lot['id']}/adjust", json={"delta": -5}, headers=_general_headers()
    )
    assert response.status_code == 200
    assert response.json()["current_count"] == 0

    activities = client.get(f"/api/v1/parking-lots/{lot['id']}/activities", headers=admin_headers).json()
    assert activities[0]["delta"] == 0  # clamped: 0 -> 0, not 0 -> -5


def test_activities_requires_admin(client, admin_headers):
    lot = _register_lot(client, admin_headers)
    response = client.get(f"/api/v1/parking-lots/{lot['id']}/activities")
    assert response.status_code == 401


def test_device_event_appears_in_activities_with_device_code_as_actor(client, admin_headers):
    lot = _register_lot(client, admin_headers)
    device = client.post(
        "/api/v1/devices",
        json={"device_code": "trapa-dev1", "parking_lot_id": lot["id"]},
        headers=admin_headers,
    ).json()

    client.post(
        "/api/v1/events",
        json={"event_type": "entry", "detected_at": "2026-08-15T10:00:00"},
        headers={"X-API-Key": device["api_key"]},
    )

    activities = client.get(f"/api/v1/parking-lots/{lot['id']}/activities", headers=admin_headers).json()
    assert len(activities) == 1
    assert activities[0]["activity_type"] == "entry"
    assert activities[0]["delta"] == 1
    assert activities[0]["actor_label"] == "trapa-dev1"


def test_system_count_and_current_count_are_independent(client, admin_headers):
    lot = _register_lot(client, admin_headers)
    assert lot["has_device"] is False

    device = client.post(
        "/api/v1/devices",
        json={"device_code": "trapa-dev1", "parking_lot_id": lot["id"]},
        headers=admin_headers,
    ).json()

    lot_with_device = client.get(f"/api/v1/parking-lots/{lot['id']}").json()
    assert lot_with_device["has_device"] is True

    # A device event only moves system_count.
    client.post(
        "/api/v1/events",
        json={"event_type": "entry", "detected_at": "2026-08-15T10:00:00"},
        headers={"X-API-Key": device["api_key"]},
    )
    after_event = client.get(f"/api/v1/parking-lots/{lot['id']}").json()
    assert after_event["system_count"] == 1
    assert after_event["current_count"] == 0

    # A manual adjustment only moves current_count.
    client.post(
        f"/api/v1/parking-lots/{lot['id']}/adjust", json={"delta": 4}, headers=_general_headers()
    )
    after_adjust = client.get(f"/api/v1/parking-lots/{lot['id']}").json()
    assert after_adjust["current_count"] == 4
    assert after_adjust["system_count"] == 1
