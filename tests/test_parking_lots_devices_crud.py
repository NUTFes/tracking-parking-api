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
    response = client.post("/api/v1/parking-lots", json={"name": "No Capacity"}, headers=admin_headers)
    assert response.status_code == 422


def test_update_parking_lot(client, admin_headers):
    lot, _device = _register_lot_and_device(client, admin_headers)
    response = client.patch(
        f"/api/v1/parking-lots/{lot['id']}", json={"name": "Renamed Lot", "capacity": 20}, headers=admin_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed Lot"
    assert body["capacity"] == 20


def test_update_parking_lot_partial(client, admin_headers):
    lot, _device = _register_lot_and_device(client, admin_headers)
    response = client.patch(f"/api/v1/parking-lots/{lot['id']}", json={"capacity": 99}, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == lot["name"]
    assert body["capacity"] == 99


def test_delete_parking_lot_blocked_while_devices_exist(client, admin_headers):
    lot, _device = _register_lot_and_device(client, admin_headers)
    response = client.delete(f"/api/v1/parking-lots/{lot['id']}", headers=admin_headers)
    assert response.status_code == 409


def test_delete_parking_lot_succeeds_once_empty(client, admin_headers):
    lot, device = _register_lot_and_device(client, admin_headers)
    assert client.delete(f"/api/v1/devices/{device['id']}", headers=admin_headers).status_code == 204
    response = client.delete(f"/api/v1/parking-lots/{lot['id']}", headers=admin_headers)
    assert response.status_code == 204
    assert client.get(f"/api/v1/parking-lots/{lot['id']}").status_code == 404


def test_update_device(client, admin_headers):
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


def test_update_device_rejects_unknown_parking_lot(client, admin_headers):
    _lot, device = _register_lot_and_device(client, admin_headers)
    response = client.patch(
        f"/api/v1/devices/{device['id']}", json={"parking_lot_id": 999999}, headers=admin_headers
    )
    assert response.status_code == 404


def test_delete_device_cascades_events_and_commands(client, admin_headers):
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
    lot, device = _register_lot_and_device(client, admin_headers)
    assert client.patch(f"/api/v1/parking-lots/{lot['id']}", json={"name": "x"}).status_code == 401
    assert client.delete(f"/api/v1/parking-lots/{lot['id']}").status_code == 401
    assert client.patch(f"/api/v1/devices/{device['id']}", json={"name": "x"}).status_code == 401
    assert client.delete(f"/api/v1/devices/{device['id']}").status_code == 401
