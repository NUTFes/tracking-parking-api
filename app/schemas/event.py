from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import JSTDateTime


class EventCreate(BaseModel):
    request_id: UUID = Field(
        description="クライアント（デバイス）が生成する冪等キー。同じ値で再送しても重複登録されず、"
        "既存のイベントがそのまま返る（レスポンスがタイムアウトした際の再送などを想定）"
    )
    event_type: Literal["entry", "exit"] = Field(description="イベント種別（entry=入庫 / exit=出庫）")
    detected_at: datetime = Field(description="エッジデバイスが検出した日時（ローカル時刻）")
    vehicle_track_id: str | None = Field(
        default=None, description="エッジ側トラッカーの追跡ID（任意。同一車両の入出庫を紐づける際の参考情報）"
    )


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="サーバー側の連番ID（引き続き自動採番。request_idとは別物）")
    request_id: UUID = Field(description="リクエストの冪等キー（クライアント指定のUUID）")
    device_id: int = Field(description="このイベントを登録したデバイスのID")
    event_type: str = Field(description="イベント種別（entry=入庫 / exit=出庫）")
    status: str = Field(description="キュー処理状況（pending=処理待ち / processed=反映済み / failed=処理失敗）")
    vehicle_track_id: str | None
    detected_at: JSTDateTime = Field(description="エッジデバイスが検出した日時")
    received_at: JSTDateTime = Field(description="サーバーがイベントを受信した日時")
