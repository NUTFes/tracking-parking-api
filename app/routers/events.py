from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.deps import get_current_device
from app.models.device import Device
from app.schemas.event import EventCreate, EventOut
from app.usecases.event_usecase import EventUsecase, get_event_usecase, process_queued_event

router = APIRouter(tags=["events"])


@router.post(
    "/events",
    response_model=EventOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="入出庫イベント登録（非同期処理）",
)
def create_event(
    payload: EventCreate,
    background_tasks: BackgroundTasks,
    device: Device = Depends(get_current_device),
    usecase: EventUsecase = Depends(get_event_usecase),
):
    """認証済みデバイスの入出庫イベントを記録する。イベント自体はこのリクエスト内で
    即座に永続化される（レスポンスの`status`は"pending"）が、駐車場の現在台数
    （system_count）への反映はバックグラウンドのキュー処理に回すため、レスポンス
    返却時点ではまだ反映されていないことがある。`request_id`はデバイス側が生成する
    冪等キーで、同じ値で再送しても重複登録されず（既存のイベントがそのまま返る）、
    その場合はバックグラウンド処理も再度スケジュールされない。"""
    event, is_new = usecase.enqueue_event(
        device=device,
        event_type=payload.event_type,
        vehicle_track_id=payload.vehicle_track_id,
        detected_at=payload.detected_at,
        request_id=str(payload.request_id),
    )
    if is_new:
        background_tasks.add_task(process_queued_event, event.id)
    return event
