from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "mysql+pymysql://trapa:trapa_password@db:3306/tracking_parking"
    device_offline_threshold_seconds: int = 120
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    # SQLAlchemy connection pool. Previously left at the library's defaults
    # (pool_size=5, max_overflow=10 => 15 connections max) with no explicit
    # config — services/load-test surfaced this as the likely ceiling behind
    # an intermittent connection reset under ~30 req/s of concurrent traffic
    # (single uvicorn worker, so this pool is the only place backpressure can
    # build up). Doubled here and made tunable via env vars without a code
    # change; pool_timeout kept at SQLAlchemy's own default (30s).
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    # Google Sign-In (Identity Services). Both admin-web (with an allow-list,
    # see admin_users) and web (any correctly-formatted NUTFes account, see
    # app/google_auth.py) verify ID tokens against this OAuth client ID.
    google_client_id: str = "your-client-id.apps.googleusercontent.com"

    # DANGER — never set true outside the E2E docker-compose overlay
    # (services/e2e/docker-compose.e2e.yml). When true, app.google_auth
    # skips real signature verification against Google and just decodes the
    # token payload as-is, so Playwright can sign in with a self-crafted
    # token (real Google auth can't be scripted end-to-end). Not present in
    # .env.example / the default docker-compose.yml on purpose.
    google_auth_test_mode: bool = False

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
