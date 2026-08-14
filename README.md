# Tracking-Parking — API (tracking-parking-api)

FastAPI + MySQL 製のセンター側 REST API。エッジデバイスからの入出庫イベント・ハートビート受信、
デバイス/駐車場の管理、Admin コンソール向けの認証を担う。

[tracking-parking-center](https://github.com/NUTFes/tracking-parking-center) から
`services/api` としてcloneして使う想定（プロジェクト全体のセットアップ手順はそちらを参照）。

## レイヤー構成

`app/` は責務ごとに以下の層へ分離している。依存の向きは常に上から下の一方向
（routers → usecases → repositories → models）で、逆向きの参照はない。

```
routers/      HTTPの窓口。リクエスト/レスポンスの型変換とOpenAPIアノテーション（summary・
              docstring・Field description）だけを持つ薄い層。業務ロジックやSQLは書かない。
usecases/     業務ロジック。トランザクション境界（db.commit()）はここが持つ。FastAPIに
              依存しないので単体テストしやすい。異常系は例外（app/exceptions.py）で表現する。
repositories/ DBアクセスのみ。SQLAlchemyのクエリはこの層に閉じ込め、業務的な意味づけはしない。
models/       SQLAlchemyのORMモデル（テーブル定義そのもの）。
schemas/      Pydanticのリクエスト/レスポンスDTO（OpenAPIスキーマの元）。
```

- **例外の流れ**: usecase が `NotFoundError` / `UnauthorizedError`（`app/exceptions.py`）を送出し、
  `main.py` に登録したグローバル例外ハンドラが404/401のHTTPレスポンスに変換する。router 自身は
  try/exceptを書かない（`routers/auth.py` の `refresh` だけ、Cookie削除という副作用のために例外を
  一度捕まえて再送出している）。
- **認証まわりの例外**: `deps.py`（`get_current_device` / `get_current_admin_user`）はFastAPIの
  `Depends` として動く都合上、`HTTPException` を直接送出する。ここだけはフレームワーク非依存に
  こだわらず、リクエストの認証解決という性質上FastAPI前提のコードとして割り切っている。
- **ヘルスチェック**（`routers/health.py`）は `SELECT 1` を打つだけで特定のモデルに紐づかないため、
  repository/usecase層を経由せずrouterで直接実行している（層分けのための層分けをしない）。

## エッジデバイス連携の設計方針（ポーリング方式）

現場のエッジデバイスは NAT 配下にあり、サーバー側から直接アクセスできないことが多い。
そのため「サーバーヘルスチェック」以外の全ての通信はエッジデバイス発でシンプルな REST
API のみで完結させている。

- **入出庫登録**: エッジデバイスが `POST /api/v1/events` を都度呼び出す。
- **デバイスのヘルスチェック**: エッジデバイスが定期的に `POST /api/v1/heartbeat` を呼び、
  サーバーは最終通信時刻を記録する。一定時間（`DEVICE_OFFLINE_THRESHOLD_SECONDS`）通信が
  なければオフライン扱いになる。
- **デバイスの再起動**: Web / 管理者が `POST /api/v1/devices/{id}/commands` でコマンドを
  キューに積む。エッジデバイスは次の `heartbeat` 呼び出しのレスポンスでコマンドを受け取り、
  実行後に `POST /api/v1/commands/{id}/ack` で結果を報告する。サーバーからデバイスへの
  直接プッシュは行わない。

この設計により、追加のインフラ（VPN・SSH トンネル等）なしに API サーバーと DB だけで
双方向のデバイス管理が成立する（リアルタイム性はハートビート間隔に依存する）。

## デバイス認証

エッジデバイスは `X-API-Key` ヘッダーでリクエストする。API キーはデバイス登録時
（`POST /api/v1/devices`）に一度だけ平文で返却され、サーバーには SHA-256 ハッシュのみ
保存される。デバイス自身は自分の DB 上の ID を知る必要はなく、API キーだけで
自分自身の登録済みリソースにアクセスできる。

## Admin認証

`admin-web` のユーザー認証は アクセストークン（AT）+ リフレッシュトークン（RT）方式。

- **AT**: 短命（既定15分）なJWT。`Authorization: Bearer <AT>` で送る。フロントエンド
  （`admin-web`）はメモリ上にのみ保持し、永続化しない。
- **RT**: 長命（既定14日）なランダムトークン。サーバーはそのSHA-256ハッシュのみをDB
  （`admin_refresh_tokens`）に保存する。フロントエンドからはJSで一切参照できない
  **HTTP Only Cookie**（`/api/v1/auth` パスのみに送信、`SameSite=Lax`）としてのみ
  やり取りする。使用するたびにローテーション（使い捨て）し、ログアウトや期限切れで
  失効する。
- `POST /api/v1/auth/refresh` はCookieのRTを検証し、新しいATと（ローテーションした）RTを返す。
  RTが無効/失効していれば401を返す。

保護範囲: `POST /parking-lots`、`GET /parking-lots/{id}/events`、`devices` 配下の全エンドポイント
（一覧・登録・コマンド発行/履歴）が管理者ログインを必須とする。`GET /parking-lots`（一覧・詳細）と
`GET /health` は Web（公開ビューア）が使うため認証不要のまま。デバイス ↔ API は従来どおり
`X-API-Key` による別系統の認証。

クライアント側（AT のメモリ保持、ページロード時のサイレントログイン、401時の自動リトライ）の
実装は `admin-web` リポジトリの README を参照。

### 管理者アカウントの作成

セルフサインアップの画面は意図的に用意していない（Admin自体は登録済みユーザーだけが
使えるべきため）。初回のアカウントはCLIから作成する:

```bash
# ローカル venv から
PYTHONPATH=. .venv/bin/python scripts/create_admin_user.py <username>

# 起動中の docker compose に対して（tracking-parking-center側から）
docker compose exec api python scripts/create_admin_user.py <username>
```

パスワードは対話プロンプト（`getpass`）で入力する。同じユーザー名で再実行するとパスワードを
更新できる。

### 本番運用時の注意

- `.env` の `JWT_SECRET` は必ず固有のランダムな値に変更する（`openssl rand -hex 32`）。
  漏洩すると誰でも有効なアクセストークンを偽造できる。
- `admin-web` をHTTPS配下で公開する場合は `COOKIE_SECURE=true` にする（HTTP環境ではCookieが
  送信されなくなるため、ローカル開発時は `false` のままにする）。
- `admin-web` と `api` が異なるドメイン（=別サイト）で運用される場合、RTクッキーの
  `SameSite=Lax` では別サイト間のfetchに送られない。その場合は `SameSite=None; Secure`
  への変更が必要（`app/auth.py` の `set_refresh_cookie`）。
- リフレッシュトークンのローテーションは「使ったら失効」のみを実装しており、盗まれた
  トークンが正規ユーザーより先に使われた場合の再利用検知（トークンファミリー失効）は
  実装していない。

## API 仕様書（Swagger / OpenAPI）

OpenAPI仕様はコードのアノテーションから生成する。手書きのYAML/JSONは存在しない:

- 各エンドポイント（`routers/*.py`）の `summary=` 引数と関数のdocstringが、それぞれ
  OpenAPIの `summary` / `description` になる。
- 各Pydanticスキーマ（`schemas/*.py`）のフィールドに付けた `Field(description=...)` が、
  リクエスト/レスポンスの各項目の説明になる。
- `main.py` の `openapi_tags` がタグ（エンドポイントのグループ）の説明になる。

FastAPIがこれらのアノテーションを実行時に集めて `/docs`（Swagger UI）・`/redoc`・
`/openapi.json` を自動生成する。このリポジトリにはそれをコンパイルした静的スナップショットも
`docs/openapi.json` として置いてあり、ルーター・スキーマを変更したら以下で再生成する:

```bash
PYTHONPATH=. .venv/bin/python scripts/export_openapi.py
```

（中身は `app.openapi()` の呼び出し1つ — アノテーション付きのコードから実際に組み立てられた
スキーマをそのままファイルに書き出しているだけで、別途メンテナンスする仕様書ではない。）

## バックエンド開発

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt

# テスト（SQLite のインメモリ DB を使用、MySQL 不要）
.venv/bin/python -m pytest

# マイグレーション追加（開発中に MySQL を起動した状態で）
.venv/bin/alembic revision --autogenerate -m "add xxx"
.venv/bin/alembic upgrade head
```

## データモデル

| テーブル | 役割 |
|---|---|
| `parking_lots` | 駐車場。`current_count` は入出庫イベントごとに増減する現在の駐車台数 |
| `devices` | エッジデバイス。API キーのハッシュ、最終通信時刻、最終ステータスを保持 |
| `parking_events` | 個々の入出庫イベント（`entry` / `exit`） |
| `device_commands` | デバイスへのコマンドキュー（`pending` → `delivered` → `completed`/`failed`） |

ER図・カラム定義・状態遷移などの詳細は [`docs/db-schema.md`](docs/db-schema.md) を参照。

## License

MIT License. 詳細は [LICENSE](LICENSE) を参照。
