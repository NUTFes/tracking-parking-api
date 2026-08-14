from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceCreate(BaseModel):
    device_code: str = Field(description="デバイスの一意な識別コード（例: trapa-dev1）")
    name: str | None = Field(default=None, description="表示用のデバイス名（任意）")
    parking_lot_id: int = Field(description="このデバイスが紐づく駐車場のID")


class DeviceUpdate(BaseModel):
    device_code: str | None = Field(default=None, description="デバイスの一意な識別コード（例: trapa-dev1）")
    name: str | None = Field(default=None, description="表示用のデバイス名")
    parking_lot_id: int | None = Field(default=None, description="このデバイスが紐づく駐車場のID")


class DeviceCreateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_code: str
    name: str | None
    parking_lot_id: int
    api_key: str = Field(
        description="デバイス認証用APIキー（平文）。このレスポンスでのみ取得可能で、以降は再取得できない"
    )


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_code: str
    name: str | None
    parking_lot_id: int
    last_status: str | None = Field(description="直近のハートビートで報告された状態")
    last_seen_at: datetime | None = Field(description="最終通信日時（ハートビートまたはイベント受信）")
    online: bool = Field(description="最終通信からの経過時間がしきい値以内であればtrue")
    created_at: datetime
