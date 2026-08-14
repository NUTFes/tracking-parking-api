from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ParkingLotCreate(BaseModel):
    name: str = Field(description="駐車場名")
    capacity: int = Field(description="収容台数")


class ParkingLotUpdate(BaseModel):
    name: str | None = Field(default=None, description="駐車場名")
    capacity: int | None = Field(default=None, description="収容台数")


class ParkingLotResetIn(BaseModel):
    count: int = Field(ge=0, description="リセット後の駐車台数")
    target: Literal["current", "system"] = Field(
        default="current", description="リセット対象（current=人力集計 / system=システム集計）"
    )
    note: str | None = Field(default=None, description="リセット理由（任意）")


class ParkingLotResetAllIn(BaseModel):
    target: Literal["current", "system"] = Field(description="リセット対象（current=人力集計 / system=システム集計）")
    note: str | None = Field(default=None, description="リセット理由（任意）")


class ParkingLotAdjustIn(BaseModel):
    delta: int = Field(description="増減させる台数（正の値で増加、負の値で減少）")
    note: str | None = Field(default=None, description="調整理由（任意）")


class ParkingLotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    capacity: int
    current_count: int = Field(description="現在の駐車台数（人力カウント）。手動増減・リセットでのみ変化する")
    system_count: int = Field(description="デバイスが検出した入出庫イベントの集計値。current_countとは独立")
    has_device: bool = Field(description="このparking_lotに紐づくデバイスが1台以上あるか")
    created_at: datetime
