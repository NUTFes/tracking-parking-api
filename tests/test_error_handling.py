from app.usecases.parking_lot_usecase import ParkingLotUsecase


def test_unhandled_exception_returns_generic_500_with_cors_headers(client, monkeypatch):
    """DomainErrorのいずれにも当てはまらない想定外の例外（DBエラーなど）が起きても、
    生の例外内容やスタックトレースをそのまま返さず、安全な汎用メッセージのJSON 500に
    変換されることを確認する。あわせて、そのレスポンスにCORSヘッダーが付与され、
    ブラウザ側で内容を読める（＝「Failed to fetch」という不可解なエラーにならない）
    ことも確認する——ここがStarletteの既定動作では抜け落ちる部分（未処理例外は
    CORSMiddlewareの外側で処理されてしまう）で、今回のバグの直接の原因だった"""

    def _boom(self):
        raise RuntimeError("something went wrong deep inside")

    monkeypatch.setattr(ParkingLotUsecase, "list_parking_lots", _boom)

    response = client.get("/api/v1/parking-lots", headers={"Origin": "http://localhost:5173"})

    assert response.status_code == 500
    assert response.json() == {"detail": "予期しないエラーが発生しました"}
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_domain_errors_are_unaffected_by_the_catch_all_middleware(client):
    """既存のDomainError系（404/401/409）のハンドリングが、新しい汎用例外ミドルウェアの
    追加によって壊れていないことを確認する（既知のエラーはこれまで通り具体的な
    detailメッセージ付きで返る）"""
    response = client.get("/api/v1/parking-lots/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "parking lot not found"
