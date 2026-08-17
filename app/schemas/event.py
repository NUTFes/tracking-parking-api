from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import JSTDateTime


class EventCreate(BaseModel):
    event_type: Literal["entry", "exit"] = Field(description="イベント種別（entry=入庫 / exit=出庫）")
    detected_at: datetime = Field(description="エッジデバイスが検出した日時（ローカル時刻）")
    vehicle_track_id: str | None = Field(
        default=None, description="エッジ側トラッカーの追跡ID（任意。同一車両の入出庫を紐づける際の参考情報）"
    )


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int = Field(description="このイベントを登録したデバイスのID")
    event_type: str = Field(description="イベント種別（entry=入庫 / exit=出庫）")
    vehicle_track_id: str | None
    detected_at: JSTDateTime = Field(description="エッジデバイスが検出した日時")
    received_at: JSTDateTime = Field(description="サーバーがイベントを受信した日時")
