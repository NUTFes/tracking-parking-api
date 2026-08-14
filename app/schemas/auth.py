from pydantic import BaseModel, ConfigDict, Field


class GoogleLoginIn(BaseModel):
    id_token: str = Field(description="Google Identity Services（Sign In With Google）で取得したIDトークン")


class TokenOut(BaseModel):
    access_token: str = Field(description="短命なJWTアクセストークン。フロントエンドはメモリ上にのみ保持する")
    token_type: str = "bearer"
    expires_in: int = Field(description="アクセストークンの有効期限（秒）")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
