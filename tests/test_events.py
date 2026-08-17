from app.repositories.parking_lot_repository import ParkingLotRepository


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
    """X-API-Keyヘッダーなしでイベントを登録しようとすると401になることを確認する"""
    _lot, _device = _register_lot_and_device(client, admin_headers)
    response = client.post(
        "/api/v1/events",
        json={"event_type": "entry", "detected_at": "2026-08-14T10:00:00"},
    )
    assert response.status_code == 401


def test_create_event_rejects_invalid_api_key(client, admin_headers):
    """存在しないAPIキーでイベントを登録しようとすると401になることを確認する"""
    _lot, _device = _register_lot_and_device(client, admin_headers)
    response = client.post(
        "/api/v1/events",
        json={"event_type": "entry", "detected_at": "2026-08-14T10:00:00"},
        headers={"X-API-Key": "not-a-real-key"},
    )
    assert response.status_code == 401


def test_entry_and_exit_update_occupancy(client, admin_headers):
    """入庫・出庫イベントの登録に応じて駐車場のsystem_countが増減し、人力集計のcurrent_countは
    変化しないことを確認する"""
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
    assert lot_after_entry["system_count"] == 1
    # Device events are tracked separately from the manual (current_count) figure.
    assert lot_after_entry["current_count"] == 0

    exit_ = client.post(
        "/api/v1/events",
        json={"event_type": "exit", "detected_at": "2026-08-14T11:00:00", "vehicle_track_id": "42"},
        headers=headers,
    )
    assert exit_.status_code == 201

    lot_after_exit = client.get(f"/api/v1/parking-lots/{lot['id']}").json()
    assert lot_after_exit["system_count"] == 0


def test_occupancy_does_not_go_negative(client, admin_headers):
    """system_countが0の状態で出庫イベントを登録しても、マイナスにならず0で止まることを確認する"""
    lot, device = _register_lot_and_device(client, admin_headers)
    headers = {"X-API-Key": device["api_key"]}

    client.post(
        "/api/v1/events",
        json={"event_type": "exit", "detected_at": "2026-08-14T10:00:00"},
        headers=headers,
    )

    lot_after = client.get(f"/api/v1/parking-lots/{lot['id']}").json()
    assert lot_after["system_count"] == 0


def test_create_event_normalizes_timezone_aware_detected_at_to_local_time(client, admin_headers):
    """detected_atにUTCなどタイムゾーン付きの日時を送っても、日本時間（JST）のnaiveな値に
    正規化されて保存されることを確認する（デバイスは通常naiveなJST時刻を送る想定だが、
    タイムゾーン付きで送られてきた場合の変換分岐を個別に検証する）"""
    _lot, device = _register_lot_and_device(client, admin_headers)
    headers = {"X-API-Key": device["api_key"]}

    response = client.post(
        "/api/v1/events",
        json={"event_type": "entry", "detected_at": "2026-08-14T01:00:00+00:00"},
        headers=headers,
    )
    assert response.status_code == 201
    # UTC 01:00 -> JST (UTC+9) 10:00, then serialized back out with a +09:00 offset.
    assert response.json()["detected_at"] == "2026-08-14T10:00:00+09:00"


def test_list_parking_lot_events(client, admin_headers):
    """登録したイベントが、その駐車場のイベント一覧に反映されることを確認する"""
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


def test_list_parking_lot_events_filters_by_since_and_until(client, admin_headers):
    """since/untilクエリパラメータで、指定した検出日時の範囲だけにイベント一覧を絞り込めることを確認する"""
    lot, device = _register_lot_and_device(client, admin_headers)
    headers = {"X-API-Key": device["api_key"]}
    for detected_at in ("2026-08-14T09:00:00", "2026-08-14T10:00:00", "2026-08-14T11:00:00"):
        client.post(
            "/api/v1/events",
            json={"event_type": "entry", "detected_at": detected_at},
            headers=headers,
        )

    since_only = client.get(
        f"/api/v1/parking-lots/{lot['id']}/events",
        params={"since": "2026-08-14T10:00:00"},
        headers=admin_headers,
    ).json()
    assert {e["detected_at"][:19] for e in since_only} == {"2026-08-14T10:00:00", "2026-08-14T11:00:00"}

    until_only = client.get(
        f"/api/v1/parking-lots/{lot['id']}/events",
        params={"until": "2026-08-14T10:00:00"},
        headers=admin_headers,
    ).json()
    assert {e["detected_at"][:19] for e in until_only} == {"2026-08-14T09:00:00", "2026-08-14T10:00:00"}


def test_create_event_when_parking_lot_is_missing_still_records_the_event(client, admin_headers, monkeypatch):
    """デバイスに紐づく駐車場が（削除等により）見つからない場合でも、イベント自体は記録され、
    駐車場側の集計更新だけがスキップされることを確認する（通常はAPIの409ガードにより
    起こり得ないが、コード上の防御的分岐を個別に検証する）"""
    _lot, device = _register_lot_and_device(client, admin_headers)
    headers = {"X-API-Key": device["api_key"]}

    monkeypatch.setattr(ParkingLotRepository, "get_for_update", lambda self, lot_id: None)

    response = client.post(
        "/api/v1/events",
        json={"event_type": "entry", "detected_at": "2026-08-14T10:00:00"},
        headers=headers,
    )
    assert response.status_code == 201


def test_list_parking_lot_events_requires_admin(client, admin_headers):
    """駐車場のイベント履歴取得には管理者認証が必要で、未認証だと401になることを確認する"""
    lot, _device = _register_lot_and_device(client, admin_headers)
    response = client.get(f"/api/v1/parking-lots/{lot['id']}/events")
    assert response.status_code == 401
