from fastapi import APIRouter, Depends

from app.deps import get_current_device
from app.models.device import Device
from app.schemas.command import CommandAck, CommandOut, HeartbeatIn, HeartbeatOut
from app.usecases.heartbeat_usecase import HeartbeatUsecase, get_heartbeat_usecase

router = APIRouter(tags=["device"])


@router.post("/heartbeat", response_model=HeartbeatOut, summary="ハートビート送信")
def heartbeat(
    payload: HeartbeatIn,
    device: Device = Depends(get_current_device),
    usecase: HeartbeatUsecase = Depends(get_heartbeat_usecase),
):
    """デバイスが定期的に呼び出す生存確認エンドポイント。ステータスを報告すると
    同時に、前回のポーリング以降にキューされたコマンド（再起動など）を受け取る。
    NAT配下などサーバーから直接到達できないデバイスに対して、サーバーが
    コマンドを届けられる唯一の経路。"""
    server_time, commands = usecase.record_heartbeat(device=device, status=payload.status)
    return HeartbeatOut(server_time=server_time, commands=commands)


@router.post("/commands/{command_id}/ack", response_model=CommandOut, summary="コマンド実行結果の報告")
def ack_command(
    command_id: int,
    payload: CommandAck,
    device: Device = Depends(get_current_device),
    usecase: HeartbeatUsecase = Depends(get_heartbeat_usecase),
):
    """デバイスが受け取ったコマンド（再起動など）の実行結果（成功/失敗）を報告する。"""
    return usecase.ack_command(
        device=device, command_id=command_id, status=payload.status, result_message=payload.result_message
    )
