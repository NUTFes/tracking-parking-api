from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "mysql+pymysql://trapa:trapa_password@db:3306/tracking_parking"
    device_offline_threshold_seconds: int = 120
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    # Admin authentication (services/admin-web). Access tokens are short-lived JWTs
    # kept in memory by the frontend; refresh tokens are opaque, DB-backed, and
    # delivered only via an HttpOnly cookie.
    jwt_secret: str = "change-me-in-production"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14
    refresh_token_cookie_name: str = "trapa_admin_rt"
    # Cookie "Secure" flag requires HTTPS — keep False for local http://localhost
    # dev and set True once the admin console is served over HTTPS.
    cookie_secure: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
