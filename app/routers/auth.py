from fastapi import APIRouter, Depends, Request, Response, status

from app.auth import clear_refresh_cookie, set_refresh_cookie
from app.config import settings
from app.deps import get_current_admin_user
from app.exceptions import UnauthorizedError
from app.models.admin_user import AdminUser
from app.schemas.auth import LoginIn, TokenOut, UserOut
from app.usecases.auth_usecase import AuthUsecase, get_auth_usecase

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(access_token: str) -> TokenOut:
    return TokenOut(access_token=access_token, expires_in=settings.access_token_expire_minutes * 60)


@router.post("/login", response_model=TokenOut, summary="管理者ログイン")
def login(
    payload: LoginIn,
    response: Response,
    usecase: AuthUsecase = Depends(get_auth_usecase),
):
    """ユーザー名とパスワードを検証し、アクセストークンを返す。同時にリフレッシュ
    トークンをHTTP OnlyクッキーとしてセットするAdmin console向けのログイン。"""
    _user, access_token, refresh_token = usecase.login(username=payload.username, password=payload.password)
    set_refresh_cookie(response, refresh_token)
    return _token_response(access_token)


@router.post("/refresh", response_model=TokenOut, summary="アクセストークン更新")
def refresh(
    request: Request,
    response: Response,
    usecase: AuthUsecase = Depends(get_auth_usecase),
):
    """HTTP Onlyクッキーのリフレッシュトークンを検証し、新しいアクセストークンを
    発行する。同時にリフレッシュトークンをローテーション（使い捨て）する。"""
    raw_token = request.cookies.get(settings.refresh_token_cookie_name)
    try:
        _user, access_token, new_refresh_token = usecase.refresh(raw_refresh_token=raw_token)
    except UnauthorizedError:
        clear_refresh_cookie(response)
        raise

    set_refresh_cookie(response, new_refresh_token)
    return _token_response(access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="ログアウト")
def logout(
    request: Request,
    response: Response,
    usecase: AuthUsecase = Depends(get_auth_usecase),
):
    """リフレッシュトークンをサーバー側で失効させ、クッキーを削除する。"""
    raw_token = request.cookies.get(settings.refresh_token_cookie_name)
    usecase.logout(raw_refresh_token=raw_token)
    clear_refresh_cookie(response)


@router.get("/me", response_model=UserOut, summary="ログイン中のユーザー情報取得")
def me(user: AdminUser = Depends(get_current_admin_user)):
    return user
