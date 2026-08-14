from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CommandCreate(BaseModel):
    command_type: Literal["restart", "start_counting", "stop_counting"] = Field(
        description="コマンド種別（restart=再起動 / start_counting=集計開始 / stop_counting=集計停止）"
    )
    requested_by: str | None = Field(default=None, description="コマンドを発行した主体（管理者名など、任意）")


class CommandAck(BaseModel):
    status: Literal["completed", "failed"] = Field(description="コマンドの実行結果")
    result_message: str | None = Field(default=None, description="実行結果の詳細メッセージ（任意）")


class CommandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int = Field(description="コマンドの宛先デバイスID")
    command_type: str = Field(description="コマンド種別")
    status: str = Field(description="コマンドの状態（pending=未配信 / delivered=配信済み / completed=完了 / failed=失敗）")
    requested_by: str | None
    result_message: str | None
    created_at: datetime = Field(description="コマンドがキューに登録された日時")
    delivered_at: datetime | None = Field(description="デバイスがハートビートで受け取った日時")
    completed_at: datetime | None = Field(description="デバイスが実行結果を報告した日時")


class HeartbeatIn(BaseModel):
    status: str = Field(default="ok", description="デバイスが自己申告する状態（例: ok, degraded）")


class HeartbeatOut(BaseModel):
    server_time: datetime = Field(description="サーバー側の受信日時")
    commands: list[CommandOut] = Field(description="このハートビートで配信された、実行待ちのコマンド一覧")
