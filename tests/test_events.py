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


def test_create_event_requires_api_key(client, admin_headers):
    _lot, _device = _register_lot_and_device(client, admin_headers)
    response = client.post(
        "/api/v1/events",
        json={"event_type": "entry", "detected_at": "2026-08-14T10:00:00"},
    )
    assert response.status_code == 401


def test_create_event_rejects_invalid_api_key(client, admin_headers):
    _lot, _device = _register_lot_and_device(client, admin_headers)
    response = client.post(
        "/api/v1/events",
        json={"event_type": "entry", "detected_at": "2026-08-14T10:00:00"},
        headers={"X-API-Key": "not-a-real-key"},
    )
    assert response.status_code == 401


def test_entry_and_exit_update_occupancy(client, admin_headers):
    lot, device = _register_lot_and_device(client, admin_headers)
    headers = {"X-API-Key": device["api_key"]}

    entry = client.post(
        "/api/v1/events",
        json={"event_type": "entry", "detected_at": "2026-08-14T10:00:00", "vehicle_track_id": "42"},
        headers=headers,
    )
    assert entry.status_code == 201
    assert entry.json()["device_id"] == device["id"]

    lot_after_entry = client.get(f"/api/v1/parking-lots/{lot['id']}").json()
    assert lot_after_entry["current_count"] == 1

    exit_ = client.post(
        "/api/v1/events",
        json={"event_type": "exit", "detected_at": "2026-08-14T11:00:00", "vehicle_track_id": "42"},
        headers=headers,
    )
    assert exit_.status_code == 201

    lot_after_exit = client.get(f"/api/v1/parking-lots/{lot['id']}").json()
    assert lot_after_exit["current_count"] == 0


def test_occupancy_does_not_go_negative(client, admin_headers):
    lot, device = _register_lot_and_device(client, admin_headers)
    headers = {"X-API-Key": device["api_key"]}

    client.post(
        "/api/v1/events",
        json={"event_type": "exit", "detected_at": "2026-08-14T10:00:00"},
        headers=headers,
    )

    lot_after = client.get(f"/api/v1/parking-lots/{lot['id']}").json()
    assert lot_after["current_count"] == 0


def test_list_parking_lot_events(client, admin_headers):
    lot, device = _register_lot_and_device(client, admin_headers)
    headers = {"X-API-Key": device["api_key"]}
    client.post(
        "/api/v1/events",
        json={"event_type": "entry", "detected_at": "2026-08-14T10:00:00"},
        headers=headers,
    )

    events = client.get(f"/api/v1/parking-lots/{lot['id']}/events", headers=admin_headers).json()
    assert len(events) == 1
    assert events[0]["event_type"] == "entry"


def test_list_parking_lot_events_requires_admin(client, admin_headers):
    lot, _device = _register_lot_and_device(client, admin_headers)
    response = client.get(f"/api/v1/parking-lots/{lot['id']}/events")
    assert response.status_code == 401
