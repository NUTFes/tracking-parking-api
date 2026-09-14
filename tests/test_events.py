import uuid
from datetime import timedelta

from app.models.event import ParkingEvent
from app.repositories.parking_lot_repository import ParkingLotRepository
from app.usecases.event_usecase import EventUsecase, sweep_stale_queued_events
from app.utils import now_local
from tests.conftest import TestingSessionLocal


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


def _uuid() -> str:
    return str(uuid.uuid4())


def test_create_event_requires_api_key(client, admin_headers):
    """X-API-Keyヘッダーなしでイベントを登録しようとすると401になることを確認する"""
    _lot, _device = _register_lot_and_device(client, admin_headers)
    response = client.post(
        "/api/v1/events",
        json={"request_id": _uuid(), "event_type": "entry", "detected_at": "2026-08-14T10:00:00"},
    )
    assert response.status_code == 401


def test_create_event_rejects_invalid_api_key(client, admin_headers):
    """存在しないAPIキーでイベントを登録しようとすると401になることを確認する"""
    _lot, _device = _register_lot_and_device(client, admin_headers)
    response = client.post(
        "/api/v1/events",
        json={"request_id": _uuid(), "event_type": "entry", "detected_at": "2026-08-14T10:00:00"},
        headers={"X-API-Key": "not-a-real-key"},
    )
    assert response.status_code == 401


def test_entry_and_exit_update_occupancy(client, admin_headers):
    """入庫・出庫イベントの登録に応じて駐車場のsystem_countが増減し、人力集計のcurrent_countは
    変化しないことを確認する。POSTのレスポンス自体はキュー投入直後の状態（status="pending"）
    を返すが、TestClientの呼び出しの中でバックグラウンド処理まで完了するため、レスポンスが
    返った後の別リクエスト（GET）ではsystem_countへの反映を確認できる。"""
    lot, device = _register_lot_and_device(client, admin_headers)
    headers = {"X-API-Key": device["api_key"]}

    entry = client.post(
        "/api/v1/events",
        json={
            "request_id": _uuid(),
            "event_type": "entry",
            "detected_at": "2026-08-14T10:00:00",
            "vehicle_track_id": "42",
        },
        headers=headers,
    )
    assert entry.status_code == 202
    assert entry.json()["device_id"] == device["id"]
    # The response body is serialized before the background task (which
    # flips status to "processed") runs, so it always reflects the
    # just-inserted "pending" state — see EventUsecase.enqueue_event.
    assert entry.json()["status"] == "pending"

    lot_after_entry = client.get(f"/api/v1/parking-lots/{lot['id']}").json()
    assert lot_after_entry["system_count"] == 1
    # Device events are tracked separately from the manual (current_count) figure.
    assert lot_after_entry["current_count"] == 0

    exit_ = client.post(
        "/api/v1/events",
        json={
            "request_id": _uuid(),
            "event_type": "exit",
            "detected_at": "2026-08-14T11:00:00",
            "vehicle_track_id": "42",
        },
        headers=headers,
    )
    assert exit_.status_code == 202

    lot_after_exit = client.get(f"/api/v1/parking-lots/{lot['id']}").json()
    assert lot_after_exit["system_count"] == 0


def test_occupancy_does_not_go_negative(client, admin_headers):
    """system_countが0の状態で出庫イベントを登録しても、マイナスにならず0で止まることを確認する"""
    lot, device = _register_lot_and_device(client, admin_headers)
    headers = {"X-API-Key": device["api_key"]}

    client.post(
        "/api/v1/events",
        json={"request_id": _uuid(), "event_type": "exit", "detected_at": "2026-08-14T10:00:00"},
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
        json={"request_id": _uuid(), "event_type": "entry", "detected_at": "2026-08-14T01:00:00+00:00"},
        headers=headers,
    )
    assert response.status_code == 202
    # UTC 01:00 -> JST (UTC+9) 10:00, then serialized back out with a +09:00 offset.
    assert response.json()["detected_at"] == "2026-08-14T10:00:00+09:00"


def test_create_event_is_idempotent_by_request_id(client, admin_headers):
    """同じrequest_idで再送しても、イベントは重複登録されず（system_countも1回しか
    増減せず）、最初に登録した同じイベントがそのまま返ることを確認する
    （応答がタイムアウトした際のデバイス側リトライを想定）"""
    lot, device = _register_lot_and_device(client, admin_headers)
    headers = {"X-API-Key": device["api_key"]}
    request_id = _uuid()
    payload = {"request_id": request_id, "event_type": "entry", "detected_at": "2026-08-14T10:00:00"}

    first = client.post("/api/v1/events", json=payload, headers=headers)
    second = client.post("/api/v1/events", json=payload, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]

    lot_after = client.get(f"/api/v1/parking-lots/{lot['id']}").json()
    assert lot_after["system_count"] == 1


def test_list_parking_lot_events(client, admin_headers):
    """登録したイベントが、その駐車場のイベント一覧に反映されることを確認する"""
    lot, device = _register_lot_and_device(client, admin_headers)
    headers = {"X-API-Key": device["api_key"]}
    client.post(
        "/api/v1/events",
        json={"request_id": _uuid(), "event_type": "entry", "detected_at": "2026-08-14T10:00:00"},
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
            json={"request_id": _uuid(), "event_type": "entry", "detected_at": detected_at},
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
    駐車場側の集計更新だけがスキップされて、バックグラウンド処理後にステータスが
    "processed"になることを確認する（通常はAPIの409ガードにより起こり得ないが、コード上の
    防御的分岐を個別に検証する）"""
    lot, device = _register_lot_and_device(client, admin_headers)
    headers = {"X-API-Key": device["api_key"]}

    monkeypatch.setattr(ParkingLotRepository, "get_for_update", lambda self, lot_id: None)

    response = client.post(
        "/api/v1/events",
        json={"request_id": _uuid(), "event_type": "entry", "detected_at": "2026-08-14T10:00:00"},
        headers=headers,
    )
    assert response.status_code == 202

    events = client.get(f"/api/v1/parking-lots/{lot['id']}/events", headers=admin_headers).json()
    assert events[0]["status"] == "processed"


def test_list_parking_lot_events_requires_admin(client, admin_headers):
    """駐車場のイベント履歴取得には管理者認証が必要で、未認証だと401になることを確認する"""
    lot, _device = _register_lot_and_device(client, admin_headers)
    response = client.get(f"/api/v1/parking-lots/{lot['id']}/events")
    assert response.status_code == 401


def _insert_orphaned_event(device_id: int, *, status: str, seconds_ago: int) -> int:
    """Inserts a parking_events row directly, bypassing POST /events entirely
    — simulates an event whose BackgroundTask never ran (e.g. the API
    process was killed between enqueue_event's commit and the task actually
    executing) or previously failed. TestClient always finishes a real
    request's BackgroundTask before returning (see
    test_entry_and_exit_update_occupancy), so this is the only way to get a
    genuinely stuck "pending"/"failed" row in a test."""
    db = TestingSessionLocal()
    try:
        stamp = now_local() - timedelta(seconds=seconds_ago)
        event = ParkingEvent(
            device_id=device_id,
            event_type="entry",
            request_id=_uuid(),
            status=status,
            detected_at=stamp,
            received_at=stamp,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event.id
    finally:
        db.close()


def test_sweep_reprocesses_a_stale_pending_event(client, admin_headers):
    """A "pending" event whose BackgroundTask never ran (simulating a crash)
    gets picked up and applied to the lot's system_count once it's older
    than event_queue_stale_seconds — see EventUsecase.sweep_stale_events."""
    lot, device = _register_lot_and_device(client, admin_headers)
    _insert_orphaned_event(device["id"], status="pending", seconds_ago=120)

    assert sweep_stale_queued_events() == 1

    lot_after = client.get(f"/api/v1/parking-lots/{lot['id']}").json()
    assert lot_after["system_count"] == 1


def test_sweep_retries_a_stale_failed_event(client, admin_headers):
    """A "failed" event (processing raised previously) is retried — and
    successfully applied — by the sweep instead of being left stuck forever."""
    lot, device = _register_lot_and_device(client, admin_headers)
    _insert_orphaned_event(device["id"], status="failed", seconds_ago=120)

    assert sweep_stale_queued_events() == 1

    lot_after = client.get(f"/api/v1/parking-lots/{lot['id']}").json()
    assert lot_after["system_count"] == 1


def test_sweep_leaves_a_recent_pending_event_alone(client, admin_headers):
    """An event still within event_queue_stale_seconds is left untouched —
    otherwise the sweep could race a BackgroundTask that's genuinely still
    in flight."""
    lot, device = _register_lot_and_device(client, admin_headers)
    _insert_orphaned_event(device["id"], status="pending", seconds_ago=1)

    assert sweep_stale_queued_events() == 0

    lot_after = client.get(f"/api/v1/parking-lots/{lot['id']}").json()
    assert lot_after["system_count"] == 0


def test_process_event_marks_failed_on_exception_instead_of_raising(client, admin_headers, monkeypatch):
    """If applying the event raises, process_event rolls back, logs, and
    marks the event "failed" rather than leaving it "pending" forever or
    propagating the exception (which would otherwise abort a whole sweep
    batch after the first failure)."""
    _lot, device = _register_lot_and_device(client, admin_headers)
    event_id = _insert_orphaned_event(device["id"], status="pending", seconds_ago=0)

    def _boom(self, lot_id):
        raise RuntimeError("boom")

    monkeypatch.setattr(ParkingLotRepository, "get_for_update", _boom)

    db = TestingSessionLocal()
    try:
        EventUsecase(db).process_event(event_id)
        event = db.get(ParkingEvent, event_id)
        assert event.status == "failed"
    finally:
        db.close()
