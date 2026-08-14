from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ParkingActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parking_lot_id: int
    activity_type: str = Field(description="entry / exit / manual_adjustment / reset")
    delta: int = Field(description="この活動によるcurrent_countの増減")
    count_after: int = Field(description="この活動が反映された後のcurrent_count")
    actor_label: str = Field(
        description="発生元。デバイス起因ならdevice_code、人起因ならGoogleアカウントの識別ラベル（例: 25.m.kitano）"
    )
    note: str | None = Field(description="手動調整・リセット時の理由メモ（任意）")
    created_at: datetime
