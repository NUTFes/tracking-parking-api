from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.deps import get_current_admin_user, get_current_general_user_label
from app.google_auth import label_from_email
from app.models.admin_user import AdminUser
from app.schemas.event import EventOut
from app.schemas.parking_activity import ParkingActivityOut
from app.schemas.parking_lot import (
    ParkingLotAdjustIn,
    ParkingLotCreate,
    ParkingLotOut,
    ParkingLotResetAllIn,
    ParkingLotResetIn,
    ParkingLotUpdate,
)
from app.usecases.parking_lot_usecase import ParkingLotUsecase, get_parking_lot_usecase

router = APIRouter(prefix="/parking-lots", tags=["parking-lots"])


@router.post("", response_model=ParkingLotOut, status_code=status.HTTP_201_CREATED, summary="駐車場登録")
def create_parking_lot(
    payload: ParkingLotCreate,
    usecase: ParkingLotUsecase = Depends(get_parking_lot_usecase),
    _admin: AdminUser = Depends(get_current_admin_user),
):
    """新しい駐車場を登録する。"""
    return usecase.create_parking_lot(name=payload.name, capacity=payload.capacity)


@router.get("", response_model=list[ParkingLotOut], summary="駐車場一覧取得")
def list_parking_lots(usecase: ParkingLotUsecase = Depends(get_parking_lot_usecase)):
    """登録済みの駐車場と、それぞれの現在の駐車台数を一覧で返す。"""
    return usecase.list_parking_lots()


@router.get("/activities", response_model=list[ParkingActivityOut], summary="全駐車場の活動ログ取得")
def list_all_parking_lot_activities(
    limit: int = Query(default=200, le=1000, description="取得件数の上限（最大1000）"),
    usecase: ParkingLotUsecase = Depends(get_parking_lot_usecase),
    _admin: AdminUser = Depends(get_current_admin_user),
):
    """全駐車場の活動ログ（入出庫・手動調整・リセット）を、駐車場を問わず新しい順にまとめて
    返す。Adminコンソールの一覧表示用。この静的パスは /{lot_id} より前に定義する必要がある
    （FastAPIはパスパラメータの型に関わらず登録順でマッチするため、後ろだと
    /{lot_id} 側が "activities" を lot_id として解釈しようとして422になる）。"""
    return usecase.list_all_activities(limit=limit)


@router.get(
    "/activities/export",
    summary="全駐車場の活動ログをCSVでダウンロード",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "UTF-8（BOM付き）のCSV"}},
)
def export_all_parking_lot_activities(
    start_date: date | None = Query(default=None, description="この日（JST）以降の活動に絞り込む（YYYY-MM-DD）"),
    end_date: date | None = Query(default=None, description="この日（JST）以前の活動に絞り込む（YYYY-MM-DD、当日を含む）"),
    usecase: ParkingLotUsecase = Depends(get_parking_lot_usecase),
    _admin: AdminUser = Depends(get_current_admin_user),
):
    """全駐車場の活動ログを古い順にCSVで返す。件数上限はなく、日付を省略した側は無制限。
    Excelで文字化けしないようBOM付きUTF-8で出力する。/activities と同じく /{lot_id} より前に
    定義する必要がある。"""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="開始日は終了日以前の日付を指定してください")
    body = usecase.export_activities_csv(start_date=start_date, end_date=end_date)
    filename = f"activities_{start_date or 'all'}_{end_date or 'all'}.csv"
    return Response(
        content="\ufeff" + body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{lot_id}", response_model=ParkingLotOut, summary="駐車場詳細取得")
def get_parking_lot(lot_id: int, usecase: ParkingLotUsecase = Depends(get_parking_lot_usecase)):
    """指定した駐車場の詳細（現在の駐車台数を含む）を返す。"""
    return usecase.get_parking_lot(lot_id)


@router.patch("/{lot_id}", response_model=ParkingLotOut, summary="駐車場情報の更新")
def update_parking_lot(
    lot_id: int,
    payload: ParkingLotUpdate,
    usecase: ParkingLotUsecase = Depends(get_parking_lot_usecase),
    _admin: AdminUser = Depends(get_current_admin_user),
):
    """駐車場名・収容台数・マップ上のピン位置を更新する。指定したフィールドのみ更新される。"""
    return usecase.update_parking_lot(
        lot_id,
        name=payload.name,
        capacity=payload.capacity,
        x_percent=payload.x_percent,
        y_percent=payload.y_percent,
    )


@router.delete("/{lot_id}", status_code=status.HTTP_204_NO_CONTENT, summary="駐車場削除")
def delete_parking_lot(
    lot_id: int,
    usecase: ParkingLotUsecase = Depends(get_parking_lot_usecase),
    _admin: AdminUser = Depends(get_current_admin_user),
):
    """駐車場を削除する。紐づくデバイスが存在する場合は409エラーになる（先にデバイスを削除・移動すること）。"""
    usecase.delete_parking_lot(lot_id)


@router.post("/{lot_id}/reset", response_model=ParkingLotOut, summary="駐車台数のリセット")
def reset_parking_lot(
    lot_id: int,
    payload: ParkingLotResetIn,
    admin: AdminUser = Depends(get_current_admin_user),
    usecase: ParkingLotUsecase = Depends(get_parking_lot_usecase),
):
    """人力集計（current）またはシステム集計（system）を指定した値に直接設定する。実車確認
    や機器ズレを補正するためのAdmin専用操作で、parking_activitiesに記録される
    （Adminコンソールからのみ実行可）。"""
    return usecase.reset_count(
        lot_id,
        count=payload.count,
        target=payload.target,
        actor_label=label_from_email(admin.email),
        note=payload.note,
    )


@router.post("/reset-all", response_model=list[ParkingLotOut], summary="全駐車場の台数を一括リセット")
def reset_all_parking_lots(
    payload: ParkingLotResetAllIn,
    admin: AdminUser = Depends(get_current_admin_user),
    usecase: ParkingLotUsecase = Depends(get_parking_lot_usecase),
):
    """全ての駐車場の人力集計またはシステム集計を一括で0にリセットする（イベント開始時の
    初期化などを想定したAdmin専用操作）。parking_activitiesに記録される。"""
    return usecase.reset_all_counts(target=payload.target, actor_label=label_from_email(admin.email), note=payload.note)


@router.post("/{lot_id}/adjust", response_model=ParkingLotOut, summary="駐車台数の手動増減")
def adjust_parking_lot(
    lot_id: int,
    payload: ParkingLotAdjustIn,
    actor_label: str = Depends(get_current_general_user_label),
    usecase: ParkingLotUsecase = Depends(get_parking_lot_usecase),
):
    """現在の駐車台数を指定した数だけ増減させる（0未満にはならない）。Googleアカウントの
    形式検証のみで利用できる一般ユーザー向けの操作（Adminログインは不要）で、
    parking_activitiesに記録される。"""
    return usecase.adjust_count(lot_id, delta=payload.delta, actor_label=actor_label, note=payload.note)


@router.get("/{lot_id}/events", response_model=list[EventOut], summary="駐車場の入出庫履歴取得")
def list_parking_lot_events(
    lot_id: int,
    since: datetime | None = Query(default=None, description="この日時以降に検出されたイベントに絞り込む"),
    until: datetime | None = Query(default=None, description="この日時以前に検出されたイベントに絞り込む"),
    limit: int = Query(default=100, le=1000, description="取得件数の上限（最大1000）"),
    usecase: ParkingLotUsecase = Depends(get_parking_lot_usecase),
    _admin: AdminUser = Depends(get_current_admin_user),
):
    """指定した駐車場に紐づく入出庫イベントを検出日時の新しい順に返す。"""
    return usecase.list_events(lot_id, since=since, until=until, limit=limit)


@router.get("/{lot_id}/activities", response_model=list[ParkingActivityOut], summary="駐車場の活動ログ取得")
def list_parking_lot_activities(
    lot_id: int,
    limit: int = Query(default=100, le=1000, description="取得件数の上限（最大1000）"),
    usecase: ParkingLotUsecase = Depends(get_parking_lot_usecase),
    _admin: AdminUser = Depends(get_current_admin_user),
):
    """指定した駐車場のcurrent_count変更履歴（入出庫・手動調整・リセット）を新しい順に返す。
    時系列分析・監査用の統合ログ。"""
    return usecase.list_activities(lot_id, limit=limit)
