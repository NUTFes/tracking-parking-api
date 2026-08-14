from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ParkingLotCreate(BaseModel):
    name: str = Field(description="駐車場名")
    capacity: int = Field(description="収容台数")


class ParkingLotUpdate(BaseModel):
    name: str | None = Field(default=None, description="駐車場名")
    capacity: int | None = Field(default=None, description="収容台数")


class ParkingLotResetIn(BaseModel):
    count: int = Field(ge=0, description="リセット後の駐車台数")
    note: str | None = Field(default=None, description="リセット理由（任意）")


class ParkingLotAdjustIn(BaseModel):
    delta: int = Field(description="増減させる台数（正の値で増加、負の値で減少）")
    note: str | None = Field(default=None, description="調整理由（任意）")


class ParkingLotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    capacity: int
    current_count: int = Field(description="現在の駐車台数。入出庫イベントごとに増減する")
    created_at: datetime
