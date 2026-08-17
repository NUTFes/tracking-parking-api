import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.routers import admin_users, auth, devices, events, health, heartbeat, parking_lots

logger = logging.getLogger("app")

OPENAPI_TAGS = [
    {"name": "health", "description": "サーバーおよびDB接続の稼働確認"},
    {"name": "events", "description": "エッジデバイスからの入出庫イベント登録"},
    {
        "name": "device",
        "description": "デバイスが自発的に呼び出すエンドポイント（ハートビート送信・コマンド実行結果の報告）",
    },
    {"name": "devices", "description": "デバイスの管理（登録・一覧・再起動などのコマンド発行、要管理者ログイン）"},
    {"name": "parking-lots", "description": "駐車場の現在の駐車状況と入出庫履歴"},
    {"name": "auth", "description": "管理コンソール（Admin）のログイン・トークン管理"},
    {"name": "admin-users", "description": "管理コンソールへのログインを許可するアカウント（許可リスト）の管理"},
]

app = FastAPI(
    title="Tracking-Parking API",
    description=(
        "駐車場入出庫トラッキングシステム「Tracking-Parking」のセンターAPI。"
        "エッジデバイスからの入出庫イベント登録、ヘルスチェック、"
        "デバイスへのコマンド（再起動など）配信をポーリング方式で提供する。"
    ),
    version="0.1.0",
    openapi_tags=OPENAPI_TAGS,
)


@app.exception_handler(NotFoundError)
async def handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.message})


@app.exception_handler(UnauthorizedError)
async def handle_unauthorized(request: Request, exc: UnauthorizedError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": exc.message})


@app.exception_handler(ConflictError)
async def handle_conflict(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": exc.message})


class UnhandledExceptionMiddleware(BaseHTTPMiddleware):
    """Last-resort catch for anything that isn't one of our DomainError
    subclasses above (e.g. a raw DB error) — logs it and returns a plain
    JSON 500 instead of letting it propagate as a truly unhandled exception.

    This matters for more than nice error messages: Starlette's default
    handling of a *truly* unhandled exception runs in ServerErrorMiddleware,
    which sits OUTSIDE CORSMiddleware in the stack — so that response never
    gets CORS headers, and a browser reports it as an opaque "Failed to
    fetch" instead of a readable error (this is exactly what happened when
    deleting an admin_user hit an unhandled IntegrityError). Catching the
    exception here, as ordinary middleware, keeps the response inside
    CORSMiddleware's reach — but only because this is registered *before*
    CORSMiddleware below (Starlette's add_middleware prepends, so the
    middleware added last ends up outermost; CORSMiddleware must stay
    outermost to still see this one's response)."""

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            logger.exception("Unhandled exception: %s %s", request.method, request.url.path)
            return JSONResponse(status_code=500, content={"detail": "予期しないエラーが発生しました"})


# Order matters: added before CORSMiddleware so CORSMiddleware ends up
# outermost and can still attach headers to the 500 responses this produces.
app.add_middleware(UnhandledExceptionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(heartbeat.router, prefix="/api/v1")
app.include_router(devices.router, prefix="/api/v1")
app.include_router(parking_lots.router, prefix="/api/v1")
app.include_router(admin_users.router, prefix="/api/v1")
