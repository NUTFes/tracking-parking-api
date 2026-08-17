from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.routers import admin_users, auth, devices, events, health, heartbeat, parking_lots

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
