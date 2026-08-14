from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.health import HealthOut
from app.utils import now_local

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut, summary="ヘルスチェック")
def health_check(db: Session = Depends(get_db)):
    """APIサーバーとDB接続の稼働状態を確認する。"""
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    return HealthOut(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
        timestamp=now_local(),
    )
