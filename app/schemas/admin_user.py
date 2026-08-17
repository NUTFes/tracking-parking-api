from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.google_auth import NUTFES_EMAIL_PATTERN
from app.schemas.common import JSTDateTime


class AdminUserCreate(BaseModel):
    email: str = Field(description="管理コンソールへのログインを許可するGoogleアカウントのメールアドレス")

    @field_validator("email")
    @classmethod
    def _validate_nutfes_format(cls, value: str) -> str:
        """Normalizes (strip + lowercase) and enforces the same NUTFes
        executive-committee format the login flow itself checks
        (app.google_auth.verify_google_id_token) — rejecting an obviously
        wrong address here, at registration time, instead of only ever
        finding out when that person tries to log in."""
        normalized = value.strip().lower()
        if not NUTFES_EMAIL_PATTERN.match(normalized):
            raise ValueError("メールアドレスの形式が実行委員の規則（NN.x.lastname.nutfes@gmail.com）に合致しません")
        return normalized


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: JSTDateTime
