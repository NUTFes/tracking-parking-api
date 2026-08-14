from fastapi import APIRouter, Depends

from app.deps import get_current_device
from app.models.device import Device
from app.schemas.event import EventCreate, EventOut
from app.usecases.event_usecase import EventUsecase, get_event_usecase

router = APIRouter(tags=["events"])


@router.post("/events", response_model=EventOut, status_code=201, summary="入出庫イベント登録")
def create_event(
    payload: EventCreate,
    device: Device = Depends(get_current_device),
    usecase: EventUsecase = Depends(get_event_usecase),
):
    """認証済みデバイスの入出庫イベントを記録し、同一トランザクション内で
    駐車場の現在台数（current_count）を更新する。"""
    return usecase.record_event(
        device=device,
        event_type=payload.event_type,
        vehicle_track_id=payload.vehicle_track_id,
        detected_at=payload.detected_at,
    )
