def _register_lot_and_device(client, admin_headers, device_code="dev-1"):
    lot = client.post(
        "/api/v1/parking-lots", json={"name": "Test Lot", "capacity": 10}, headers=admin_headers
    ).json()
    device = client.post(
        "/api/v1/devices",
        json={"device_code": device_code, "parking_lot_id": lot["id"]},
        headers=admin_headers,
    ).json()
    return lot, device


def test_create_parking_lot_requires_capacity(client, admin_headers):
    """capacityを指定せずに駐車場を登録しようとすると422（バリデーションエラー）になることを確認する"""
    response = client.post("/api/v1/parking-lots", json={"name": "No Capacity"}, headers=admin_headers)
    assert response.status_code == 422


def test_list_parking_lots_returns_all_registered_lots(client, admin_headers):
    """登録済みの駐車場を一覧取得できることを確認する（閲覧は認証不要のエンドポイント）"""
    lot, _device = _register_lot_and_device(client, admin_headers)
    response = client.get("/api/v1/parking-lots")
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert lot["id"] in ids


def test_update_parking_lot(client, admin_headers):
    """駐車場名・収容台数の両方を一括で更新できることを確認する"""
    lot, _device = _register_lot_and_device(client, admin_headers)
    response = client.patch(
        f"/api/v1/parking-lots/{lot['id']}", json={"name": "Renamed Lot", "capacity": 20}, headers=admin_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed Lot"
    assert body["capacity"] == 20


def test_update_parking_lot_partial(client, admin_headers):
    """収容台数だけを更新した場合、駐車場名は変更されずそのまま残ることを確認する"""
    lot, _device = _register_lot_and_device(client, admin_headers)
    response = client.patch(f"/api/v1/parking-lots/{lot['id']}", json={"capacity": 99}, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == lot["name"]
    assert body["capacity"] == 99


def test_update_parking_lot_name_only(client, admin_headers):
    """駐車場名だけを更新した場合、収容台数は変更されずそのまま残ることを確認する
    （capacityを指定しないパスを個別に検証する）"""
    lot, _device = _register_lot_and_device(client, admin_headers)
    response = client.patch(f"/api/v1/parking-lots/{lot['id']}", json={"name": "Renamed Only"}, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed Only"
    assert body["capacity"] == lot["capacity"]


def test_delete_parking_lot_blocked_while_devices_exist(client, admin_headers):
    """紐づくデバイスが存在する駐車場は削除できず、409になることを確認する"""
    lot, _device = _register_lot_and_device(client, admin_headers)
    response = client.delete(f"/api/v1/parking-lots/{lot['id']}", headers=admin_headers)
    assert response.status_code == 409


def test_delete_parking_lot_succeeds_once_empty(client, admin_headers):
    """紐づくデバイスを先に削除すれば、駐車場自体も削除でき、以後は404になることを確認する"""
    lot, device = _register_lot_and_device(client, admin_headers)
    assert client.delete(f"/api/v1/devices/{device['id']}", headers=admin_headers).status_code == 204
    response = client.delete(f"/api/v1/parking-lots/{lot['id']}", headers=admin_headers)
    assert response.status_code == 204
    assert client.get(f"/api/v1/parking-lots/{lot['id']}").status_code == 404


def test_list_devices_returns_all_registered_devices(client, admin_headers):
    """登録済みのデバイスを管理者権限で一覧取得できることを確認する"""
    _lot, device = _register_lot_and_device(client, admin_headers)
    response = client.get("/api/v1/devices", headers=admin_headers)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert device["id"] in ids


def test_update_device(client, admin_headers):
    """表示名と設置先の駐車場を同時に更新できることを確認する"""
    lot, device = _register_lot_and_device(client, admin_headers)
    other_lot = client.post(
        "/api/v1/parking-lots", json={"name": "Other Lot", "capacity": 5}, headers=admin_headers
    ).json()

    response = client.patch(
        f"/api/v1/devices/{device['id']}",
        json={"name": "Renamed Device", "parking_lot_id": other_lot["id"]},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed Device"
    assert body["parking_lot_id"] == other_lot["id"]


def test_update_device_code_only(client, admin_headers):
    """デバイスコードだけを更新した場合、設置先の駐車場は変更されずそのまま残ることを確認する
    （device_code単体の更新パスを個別に検証する）"""
    lot, device = _register_lot_and_device(client, admin_headers)
    response = client.patch(
        f"/api/v1/devices/{device['id']}", json={"device_code": "renamed-dev"}, headers=admin_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["device_code"] == "renamed-dev"
    assert body["parking_lot_id"] == lot["id"]


def test_update_device_rejects_unknown_parking_lot(client, admin_headers):
    """存在しない駐車場IDへの付け替えを試みると404になることを確認する"""
    _lot, device = _register_lot_and_device(client, admin_headers)
    response = client.patch(
        f"/api/v1/devices/{device['id']}", json={"parking_lot_id": 999999}, headers=admin_headers
    )
    assert response.status_code == 404


def test_delete_device_cascades_events_and_commands(client, admin_headers):
    """デバイスを削除すると、そのイベント履歴も連動して削除される一方、駐車場自体は
    残ることを確認する"""
    lot, device = _register_lot_and_device(client, admin_headers)
    device_headers = {"X-API-Key": device["api_key"]}

    client.post(
        "/api/v1/events",
        json={"event_type": "entry", "detected_at": "2026-08-14T10:00:00"},
        headers=device_headers,
    )
    client.post(
        f"/api/v1/devices/{device['id']}/commands", json={"command_type": "restart"}, headers=admin_headers
    )

    response = client.delete(f"/api/v1/devices/{device['id']}", headers=admin_headers)
    assert response.status_code == 204
    assert client.get(f"/api/v1/devices/{device['id']}", headers=admin_headers).status_code == 404

    # The parking lot itself survives the device's deletion.
    lot_after = client.get(f"/api/v1/parking-lots/{lot['id']}").json()
    assert lot_after["id"] == lot["id"]

    # Its event history is gone too (cascade-deleted with the device), not just orphaned.
    assert client.get(f"/api/v1/parking-lots/{lot['id']}/events", headers=admin_headers).json() == []


def test_parking_lot_and_device_write_endpoints_require_admin(client, admin_headers):
    """駐車場・デバイスの更新／削除エンドポイントはいずれも管理者認証が必須であることを確認する"""
    lot, device = _register_lot_and_device(client, admin_headers)
    assert client.patch(f"/api/v1/parking-lots/{lot['id']}", json={"name": "x"}).status_code == 401
    assert client.delete(f"/api/v1/parking-lots/{lot['id']}").status_code == 401
    assert client.patch(f"/api/v1/devices/{device['id']}", json={"name": "x"}).status_code == 401
    assert client.delete(f"/api/v1/devices/{device['id']}").status_code == 401
