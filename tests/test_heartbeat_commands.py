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


def test_heartbeat_updates_device_status_and_online_flag(client, admin_headers):
    _lot, device = _register_lot_and_device(client, admin_headers)
    headers = {"X-API-Key": device["api_key"]}

    response = client.post("/api/v1/heartbeat", json={"status": "ok"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["commands"] == []

    listed = client.get(f"/api/v1/devices/{device['id']}", headers=admin_headers).json()
    assert listed["last_status"] == "ok"
    assert listed["online"] is True


def test_device_is_offline_without_heartbeat(client, admin_headers):
    _lot, device = _register_lot_and_device(client, admin_headers)
    listed = client.get(f"/api/v1/devices/{device['id']}", headers=admin_headers).json()
    assert listed["online"] is False


def test_device_endpoints_require_admin_auth(client, admin_headers):
    _lot, device = _register_lot_and_device(client, admin_headers)
    assert client.get(f"/api/v1/devices/{device['id']}").status_code == 401
    assert client.get("/api/v1/devices").status_code == 401
    assert (
        client.post(f"/api/v1/devices/{device['id']}/commands", json={"command_type": "restart"}).status_code
        == 401
    )


def test_restart_command_is_delivered_via_heartbeat_and_acked(client, admin_headers):
    _lot, device = _register_lot_and_device(client, admin_headers)
    headers = {"X-API-Key": device["api_key"]}

    queued = client.post(
        f"/api/v1/devices/{device['id']}/commands",
        json={"command_type": "restart", "requested_by": "admin"},
        headers=admin_headers,
    )
    assert queued.status_code == 201
    command_id = queued.json()["id"]
    assert queued.json()["status"] == "pending"

    heartbeat = client.post("/api/v1/heartbeat", json={"status": "ok"}, headers=headers)
    commands = heartbeat.json()["commands"]
    assert len(commands) == 1
    assert commands[0]["id"] == command_id
    assert commands[0]["status"] == "delivered"

    # Same command must not be redelivered on the next poll.
    heartbeat_again = client.post("/api/v1/heartbeat", json={"status": "ok"}, headers=headers)
    assert heartbeat_again.json()["commands"] == []

    ack = client.post(
        f"/api/v1/commands/{command_id}/ack",
        json={"status": "completed", "result_message": "rebooted"},
        headers=headers,
    )
    assert ack.status_code == 200
    assert ack.json()["status"] == "completed"

    history = client.get(f"/api/v1/devices/{device['id']}/commands", headers=admin_headers).json()
    assert history[0]["status"] == "completed"


def test_start_and_stop_counting_commands_are_queueable(client, admin_headers):
    _lot, device = _register_lot_and_device(client, admin_headers)
    headers = {"X-API-Key": device["api_key"]}

    for command_type in ("start_counting", "stop_counting"):
        queued = client.post(
            f"/api/v1/devices/{device['id']}/commands",
            json={"command_type": command_type},
            headers=admin_headers,
        )
        assert queued.status_code == 201
        assert queued.json()["command_type"] == command_type

    heartbeat = client.post("/api/v1/heartbeat", json={"status": "ok"}, headers=headers)
    delivered_types = {c["command_type"] for c in heartbeat.json()["commands"]}
    assert delivered_types == {"start_counting", "stop_counting"}


def test_cannot_ack_another_devices_command(client, admin_headers):
    _lot, device_a = _register_lot_and_device(client, admin_headers, "dev-a")
    _lot2, device_b = _register_lot_and_device(client, admin_headers, "dev-b")

    queued = client.post(
        f"/api/v1/devices/{device_a['id']}/commands",
        json={"command_type": "restart"},
        headers=admin_headers,
    ).json()

    response = client.post(
        f"/api/v1/commands/{queued['id']}/ack",
        json={"status": "completed"},
        headers={"X-API-Key": device_b["api_key"]},
    )
    assert response.status_code == 404
