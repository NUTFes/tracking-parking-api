from fastapi import APIRouter, Depends, status

from app.deps import get_current_admin_user
from app.models.admin_user import AdminUser
from app.models.device import Device
from app.schemas.command import CommandCreate, CommandOut
from app.schemas.device import DeviceCreate, DeviceCreateOut, DeviceOut, DeviceUpdate
from app.usecases.device_usecase import DeviceUsecase, get_device_usecase

router = APIRouter(prefix="/devices", tags=["devices"])


def _to_out(device: Device, usecase: DeviceUsecase) -> DeviceOut:
    return DeviceOut(
        id=device.id,
        device_code=device.device_code,
        name=device.name,
        parking_lot_id=device.parking_lot_id,
        last_status=device.last_status,
        last_seen_at=device.last_seen_at,
        online=usecase.is_online(device),
        created_at=device.created_at,
    )


@router.post("", response_model=DeviceCreateOut, status_code=status.HTTP_201_CREATED, summary="デバイス登録")
def register_device(
    payload: DeviceCreate,
    usecase: DeviceUsecase = Depends(get_device_usecase),
    _admin: AdminUser = Depends(get_current_admin_user),
):
    """新しいエッジデバイスを登録し、平文のAPIキーを一度だけ返す。サーバーには
    SHA-256ハッシュのみ保存されるため、後から再取得することはできない。"""
    device, api_key = usecase.register_device(
        device_code=payload.device_code, name=payload.name, parking_lot_id=payload.parking_lot_id
    )
    return DeviceCreateOut(
        id=device.id,
        device_code=device.device_code,
        name=device.name,
        parking_lot_id=device.parking_lot_id,
        api_key=api_key,
    )


@router.get("", response_model=list[DeviceOut], summary="デバイス一覧取得")
def list_devices(
    usecase: DeviceUsecase = Depends(get_device_usecase),
    _admin: AdminUser = Depends(get_current_admin_user),
):
    """登録済みデバイスの一覧と、最終通信時刻から判定したオンライン状態を返す。"""
    return [_to_out(d, usecase) for d in usecase.list_devices()]


@router.get("/{device_id}", response_model=DeviceOut, summary="デバイス詳細取得")
def get_device(
    device_id: int,
    usecase: DeviceUsecase = Depends(get_device_usecase),
    _admin: AdminUser = Depends(get_current_admin_user),
):
    """指定したデバイスの詳細とオンライン状態を返す。"""
    return _to_out(usecase.get_device(device_id), usecase)


@router.patch("/{device_id}", response_model=DeviceOut, summary="デバイス情報の更新")
def update_device(
    device_id: int,
    payload: DeviceUpdate,
    usecase: DeviceUsecase = Depends(get_device_usecase),
    _admin: AdminUser = Depends(get_current_admin_user),
):
    """デバイスコード・表示名・紐づく駐車場を更新する。指定したフィールドのみ更新される。
    APIキー自体はここでは変更されない。"""
    device = usecase.update_device(
        device_id, device_code=payload.device_code, name=payload.name, parking_lot_id=payload.parking_lot_id
    )
    return _to_out(device, usecase)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT, summary="デバイス削除")
def delete_device(
    device_id: int,
    usecase: DeviceUsecase = Depends(get_device_usecase),
    _admin: AdminUser = Depends(get_current_admin_user),
):
    """デバイスを削除する。紐づく入出庫イベント・コマンド履歴も合わせて削除される。"""
    usecase.delete_device(device_id)


@router.post(
    "/{device_id}/commands",
    response_model=CommandOut,
    status_code=status.HTTP_201_CREATED,
    summary="コマンドをキューに登録",
)
def queue_command(
    device_id: int,
    payload: CommandCreate,
    usecase: DeviceUsecase = Depends(get_device_usecase),
    _admin: AdminUser = Depends(get_current_admin_user),
):
    """デバイスへのコマンド（再起動・集計開始・集計停止）をキューに積む。デバイスは
    次回の /heartbeat 呼び出し時にこれを受け取る。サーバーからデバイスへの直接
    プッシュは行わない。"""
    return usecase.queue_command(device_id, command_type=payload.command_type, requested_by=payload.requested_by)


@router.get("/{device_id}/commands", response_model=list[CommandOut], summary="コマンド履歴取得")
def list_commands(
    device_id: int,
    usecase: DeviceUsecase = Depends(get_device_usecase),
    _admin: AdminUser = Depends(get_current_admin_user),
):
    """指定したデバイスに対して発行したコマンドの履歴を新しい順に返す。"""
    return usecase.list_commands(device_id)
