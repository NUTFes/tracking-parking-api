from pydantic import BaseModel, Field

from app.schemas.common import JSTDateTime


class HealthOut(BaseModel):
    status: str = Field(description="サーバー全体の状態（ok / degraded）")
    database: str = Field(description="DB接続の状態（ok / error）")
    timestamp: JSTDateTime = Field(description="このヘルスチェックを実行した日時")
