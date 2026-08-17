from fastapi import APIRouter, Depends, status

from app.deps import get_current_admin_user
from app.models.admin_user import AdminUser
from app.schemas.admin_user import AdminUserCreate, AdminUserOut
from app.usecases.admin_user_usecase import AdminUserUsecase, get_admin_user_usecase

router = APIRouter(prefix="/admin-users", tags=["admin-users"])


@router.get("", response_model=list[AdminUserOut], summary="許可ユーザー一覧取得")
def list_admin_users(
    usecase: AdminUserUsecase = Depends(get_admin_user_usecase),
    _admin: AdminUser = Depends(get_current_admin_user),
):
    """管理コンソール（Admin）へのログインを許可されているGoogleアカウントの一覧を返す。"""
    return usecase.list_users()


@router.post("", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED, summary="許可ユーザーの登録")
def create_admin_user(
    payload: AdminUserCreate,
    usecase: AdminUserUsecase = Depends(get_admin_user_usecase),
    _admin: AdminUser = Depends(get_current_admin_user),
):
    """新しいGoogleアカウントを管理コンソールの許可リストに追加する。"""
    return usecase.create_user(email=payload.email)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="許可ユーザーの削除")
def delete_admin_user(
    user_id: int,
    usecase: AdminUserUsecase = Depends(get_admin_user_usecase),
    _admin: AdminUser = Depends(get_current_admin_user),
):
    """許可リストからGoogleアカウントを削除する。許可ユーザーが1人だけの場合は削除できない。"""
    usecase.delete_user(user_id)
