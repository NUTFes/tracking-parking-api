from tests.conftest import fake_google_id_token

GENERAL_USER_EMAIL = "24.k.tanaka.nutfes@gmail.com"


def _general_headers(email: str = GENERAL_USER_EMAIL) -> dict:
    return {"Authorization": f"Bearer {fake_google_id_token(email)}"}


def _register_lot(client, admin_headers, capacity=10):
    return client.post(
        "/api/v1/parking-lots", json={"name": "Test Lot", "capacity": capacity}, headers=admin_headers
    ).json()


def test_reset_requires_admin(client, admin_headers):
    """駐車台数のリセットには管理者認証が必要で、未認証だと401になることを確認する"""
    lot = _register_lot(client, admin_headers)
    response = client.post(f"/api/v1/parking-lots/{lot['id']}/reset", json={"count": 5})
    assert response.status_code == 401


def test_reset_unknown_lot_returns_404(client, admin_headers):
    """存在しない駐車場IDを指定してリセットしようとすると404になることを確認する"""
    response = client.post("/api/v1/parking-lots/999999/reset", json={"count": 5}, headers=admin_headers)
    assert response.status_code == 404


def test_reset_sets_exact_count_and_logs_activity(client, admin_headers):
    """人力集計（current_count）を指定した台数にリセットでき、その操作がactivitiesに
    記録されることを確認する"""
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
    """システム集計（system_count）を指定した台数にリセットでき、その操作がsystem_resetとして
    activitiesに記録されることを確認する"""
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
    """全駐車場の一括リセットには管理者認証が必要で、未認証だと401になることを確認する"""
    _register_lot(client, admin_headers)
    response = client.post("/api/v1/parking-lots/reset-all", json={"target": "current"})
    assert response.status_code == 401


def test_reset_all_zeroes_every_lot(client, admin_headers):
    """全駐車場の人力集計（current_count）を一括で0にリセットでき、その操作がresetとして
    activitiesに記録されることを確認する"""
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


def test_reset_all_zeroes_system_count(client, admin_headers):
    """全駐車場のシステム集計（system_count）を一括で0にリセットでき、その操作がsystem_resetとして
    activitiesに記録されることを確認する（current_count側とは別の分岐）"""
    lot1 = _register_lot(client, admin_headers)
    lot2 = client.post(
        "/api/v1/parking-lots", json={"name": "Test Lot 2", "capacity": 20}, headers=admin_headers
    ).json()
    client.post(
        f"/api/v1/parking-lots/{lot1['id']}/reset", json={"count": 3, "target": "system"}, headers=admin_headers
    )
    client.post(
        f"/api/v1/parking-lots/{lot2['id']}/reset", json={"count": 9, "target": "system"}, headers=admin_headers
    )

    response = client.post("/api/v1/parking-lots/reset-all", json={"target": "system"}, headers=admin_headers)
    assert response.status_code == 200
    lots = {lot["id"]: lot for lot in response.json()}
    assert lots[lot1["id"]]["system_count"] == 0
    assert lots[lot2["id"]]["system_count"] == 0

    activities = client.get(f"/api/v1/parking-lots/{lot1['id']}/activities", headers=admin_headers).json()
    assert activities[0]["activity_type"] == "system_reset"
    assert activities[0]["delta"] == -3
    assert activities[0]["count_after"] == 0


def test_adjust_requires_valid_google_token(client, admin_headers):
    """駐車台数の手動増減にはGoogleログインが必要で、未認証だと401になることを確認する"""
    lot = _register_lot(client, admin_headers)
    response = client.post(f"/api/v1/parking-lots/{lot['id']}/adjust", json={"delta": 1})
    assert response.status_code == 401


def test_adjust_unknown_lot_returns_404(client, admin_headers):
    """存在しない駐車場IDを指定して台数調整しようとすると404になることを確認する"""
    response = client.post(
        "/api/v1/parking-lots/999999/adjust", json={"delta": 1}, headers=_general_headers()
    )
    assert response.status_code == 404


def test_adjust_rejects_malformed_email(client, admin_headers):
    """実行委員のメール形式に合致しないGoogleアカウントでは台数調整できないことを確認する"""
    lot = _register_lot(client, admin_headers)
    headers = {"Authorization": f"Bearer {fake_google_id_token('not-nutfes@gmail.com')}"}
    response = client.post(f"/api/v1/parking-lots/{lot['id']}/adjust", json={"delta": 1}, headers=headers)
    assert response.status_code == 401


def test_adjust_does_not_require_admin_allowlist(client, admin_headers):
    """一般ユーザー（正しい形式のNUTFesアカウントであれば誰でも）は管理者許可リストに
    登録されていなくても台数調整できることを確認する（メール形式のみがチェック対象）"""
    lot = _register_lot(client, admin_headers)
    response = client.post(
        f"/api/v1/parking-lots/{lot['id']}/adjust", json={"delta": 3}, headers=_general_headers()
    )
    assert response.status_code == 200
    assert response.json()["current_count"] == 3


def test_adjust_increases_and_decreases_count(client, admin_headers):
    """台数調整で人力集計（current_count）を増減でき、操作がmanual_adjustmentとして
    activitiesに記録されることを確認する"""
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
    """台数調整で0未満に減らそうとしても、current_countは0で止まり、activitiesにも
    実際に反映された増減（0）が記録されることを確認する"""
    lot = _register_lot(client, admin_headers)
    response = client.post(
        f"/api/v1/parking-lots/{lot['id']}/adjust", json={"delta": -5}, headers=_general_headers()
    )
    assert response.status_code == 200
    assert response.json()["current_count"] == 0

    activities = client.get(f"/api/v1/parking-lots/{lot['id']}/activities", headers=admin_headers).json()
    assert activities[0]["delta"] == 0  # clamped: 0 -> 0, not 0 -> -5


def test_activities_requires_admin(client, admin_headers):
    """特定駐車場の活動ログ取得には管理者認証が必要で、未認証だと401になることを確認する"""
    lot = _register_lot(client, admin_headers)
    response = client.get(f"/api/v1/parking-lots/{lot['id']}/activities")
    assert response.status_code == 401


def test_list_all_activities_requires_admin(client, admin_headers):
    """全駐車場の活動ログ取得には管理者認証が必要で、未認証だと401になることを確認する"""
    _register_lot(client, admin_headers)
    response = client.get("/api/v1/parking-lots/activities")
    assert response.status_code == 401


def test_list_all_activities_spans_every_lot_newest_first(client, admin_headers):
    """全駐車場の活動ログをまとめて新しい順に取得できることを確認する"""
    lot1 = _register_lot(client, admin_headers)
    lot2 = client.post(
        "/api/v1/parking-lots", json={"name": "Test Lot 2", "capacity": 20}, headers=admin_headers
    ).json()
    client.post(f"/api/v1/parking-lots/{lot1['id']}/reset", json={"count": 3}, headers=admin_headers)
    client.post(f"/api/v1/parking-lots/{lot2['id']}/reset", json={"count": 9}, headers=admin_headers)

    activities = client.get("/api/v1/parking-lots/activities", headers=admin_headers).json()
    assert len(activities) == 2
    assert activities[0]["parking_lot_id"] == lot2["id"]
    assert activities[1]["parking_lot_id"] == lot1["id"]


def test_device_event_appears_in_activities_with_device_code_as_actor(client, admin_headers):
    """デバイスが登録した入出庫イベントも活動ログに現れ、実行者（actor_label）が
    デバイスコードになることを確認する"""
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
    """デバイスによる自動検知（system_count）と人力による手動調整（current_count）が
    互いに独立して変化し、一方が他方を上書きしないことを確認する"""
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
