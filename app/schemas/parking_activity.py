from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ParkingActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parking_lot_id: int
    activity_type: str = Field(description="entry / exit / manual_adjustment / reset / system_reset")
    delta: int = Field(description="この活動による増減（entry/exit/system_resetはsystem_count、それ以外はcurrent_count）")
    count_after: int = Field(description="この活動が反映された後の値（対象カラムはactivity_typeにより異なる）")
    actor_label: str = Field(
        description="発生元。デバイス起因ならdevice_code、人起因ならGoogleアカウントの識別ラベル（例: 25.m.kitano）"
    )
    note: str | None = Field(description="手動調整・リセット時の理由メモ（任意）")
    created_at: datetime
