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
- **デバイスの再起動・集計開始/停止**: Admin が `POST /api/v1/devices/{id}/commands` で
  コマンド（`restart` / `start_counting` / `stop_counting`）をキューに積む。エッジデバイスは
  次の `heartbeat` 呼び出しのレスポンスでコマンドを受け取り、実行後に
  `POST /api/v1/commands/{id}/ack` で結果を報告する。サーバーからデバイスへの直接プッシュは
  行わない。

この設計により、追加のインフラ（VPN・SSH トンネル等）なしに API サーバーと DB だけで
双方向のデバイス管理が成立する（リアルタイム性はハートビート間隔に依存する）。

### エッジデバイスが呼び出すエンドポイント

エッジデバイスが自発的に呼ぶのは以下の3つのみ（いずれも `X-API-Key` によるデバイス認証、
`deps.py` の `get_current_device` 経由）。

| メソッド | パス | 用途 |
|---|---|---|
| `POST` | `/api/v1/events` | 入出庫イベント登録（`entry`/`exit`）。検出のたびに呼ぶ |
| `POST` | `/api/v1/heartbeat` | 生存確認。定期的に呼び、レスポンスでキュー済みコマンド（再起動・集計開始/停止）を受け取る |
| `POST` | `/api/v1/commands/{command_id}/ack` | heartbeatで受け取ったコマンドの実行結果報告 |

実装は `routers/events.py` と `routers/heartbeat.py`。

なお `POST /api/v1/devices`（デバイス登録、APIキー発行）はデバイス自身ではなく管理者が
`admin-web` 経由で一度だけ呼ぶもので、`X-API-Key` ではなく管理者ログイン（Bearerトークン）が必要。

## デバイス認証

エッジデバイスは `X-API-Key` ヘッダーでリクエストする。API キーはデバイス登録時
（`POST /api/v1/devices`）に一度だけ平文で返却され、サーバーには SHA-256 ハッシュのみ
保存される。デバイス自身は自分の DB 上の ID を知る必要はなく、API キーだけで
自分自身の登録済みリソースにアクセスできる。

## Admin認証（Google SSO + 許可リスト）

管理者アカウントはパスワードを持たない。ログインはGoogle Identity Services（Sign In With
Google）で取得したIDトークンを `POST /api/v1/auth/google` に送り、サーバーが以下の2段階で
検証する（`app/google_auth.py`）:

1. **Googleとしての検証**: 署名・audience（`GOOGLE_CLIENT_ID`）・有効期限をGoogleに問い合わせて確認し、
   `email_verified` なメールアドレスを取り出す。
2. **実行委員のメール形式検証**: `NN.x.姓.nutfes@gmail.com`（数字2桁.アルファベット1文字.
   アルファベット文字列.nutfes@gmail.com、例: `25.m.kitano.nutfes@gmail.com`）に一致しない
   メールアドレスは、Googleとしては正当でもここで拒否する。

検証を通過したメールアドレスが `admin_users`（許可リスト、[管理者アカウントの許可リスト管理](#管理者アカウントの許可リスト管理)参照）に
存在しなければ401。存在すれば、そこから先は従来どおりアクセストークン（AT）+ リフレッシュ
トークン（RT）方式でセッションを発行する:

- **AT**: 短命（既定15分）なJWT。`Authorization: Bearer <AT>` で送る。フロントエンド
  （`admin-web`）はメモリ上にのみ保持し、永続化しない。
- **RT**: 長命（既定14日）なランダムトークン。サーバーはそのSHA-256ハッシュのみをDB
  （`admin_refresh_tokens`）に保存する。フロントエンドからはJSで一切参照できない
  **HTTP Only Cookie**（`/api/v1/auth` パスのみに送信、`SameSite=Lax`）としてのみ
  やり取りする。使用するたびにローテーション（使い捨て）し、ログアウトや期限切れで
  失効する。
- `POST /api/v1/auth/refresh` はCookieのRTを検証し、新しいATと（ローテーションした）RTを返す。
  RTが無効/失効していれば401を返す（Googleへの再検証は発生しない — ATの有効期限が切れる
  たびに毎回Googleサインインし直す必要はない）。

保護範囲: `POST /parking-lots`、`POST /parking-lots/{id}/reset`、`POST /parking-lots/reset-all`、
`GET /parking-lots/{id}/events`、
`GET /parking-lots/{id}/activities`、`devices` 配下の全エンドポイント（一覧・登録・コマンド発行/履歴）が
管理者ログインを必須とする。`GET /parking-lots`（一覧・詳細）と `GET /health` は Web（公開ビューア）が
使うため認証不要のまま。デバイス ↔ API は従来どおり `X-API-Key` による別系統の認証。

クライアント側（Google Sign-Inボタン、ATのメモリ保持、ページロード時のサイレントログイン、401時の
自動リトライ）の実装は `admin-web` リポジトリの README を参照。

### 管理者アカウントの許可リスト管理

セルフサインアップの画面は意図的に用意していない（Admin自体は許可された人だけが使えるべき
ため）。許可リストへの追加・削除はCLIから行う:

```bash
# ローカル venv から
PYTHONPATH=. .venv/bin/python scripts/manage_admin_allowlist.py add 25.m.kitano.nutfes@gmail.com
PYTHONPATH=. .venv/bin/python scripts/manage_admin_allowlist.py remove 25.m.kitano.nutfes@gmail.com

# 起動中の docker compose に対して（tracking-parking-center側から）
docker compose exec api python scripts/manage_admin_allowlist.py add 25.m.kitano.nutfes@gmail.com
```

実行委員の命名規則（`NN.x.姓.nutfes@gmail.com`）に一致しないメールアドレスはこのスクリプト自体が
拒否する（ログイン時の検証と同じ正規表現、`app/google_auth.py` の `NUTFES_EMAIL_PATTERN`）。

### 一般ユーザー認証（web向け、許可リストなし）

公開ビューア（`web`）の駐車台数手動増減（`POST /parking-lots/{id}/adjust`）は、Admin許可リストとは
別の軽量な認証を使う（`deps.get_current_general_user_label`）:

- 実行委員のメール形式（上記と同じ正規表現）に一致するGoogleアカウントであれば誰でも利用できる
  （許可リストによる個別承認は不要）。
- サーバー側でのセッション発行は行わない（AT/RTを issue しない）。フロントエンドはGoogleの
  IDトークンをそのまま `Authorization: Bearer <IDトークン>` として毎回のリクエストに載せ、
  サーバーは毎回Googleに再検証する（ステートレス）。Adminのような長期セッションを持つ必要が
  ないシンプルな操作のための設計。

### 本番運用時の注意

- `.env` の `GOOGLE_CLIENT_ID` は実際のGoogle Cloud ConsoleのOAuthクライアントIDに変更する
  （既定値はプレースホルダーで、これが設定されていないとトークン検証がすべて失敗する）。
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

## current_count と system_count の分離

`parking_lots` は台数を2列で持つ。カメラ等のデバイス検出は取りこぼし・誤検出が起こりうるため、
現地スタッフの目視カウントを「公式」な値として独立させ、どちらか一方が他方を無条件に
上書きしないようにしている。

| カラム | 更新するもの | 更新するエンドポイント |
|---|---|---|
| `current_count` | 人力カウント。容量比較・満車判定など「公式」な値として使われる | `POST /parking-lots/{id}/reset`（`target=current`、Admin）、`POST /parking-lots/{id}/adjust`（一般ユーザー） |
| `system_count` | デバイスの入出庫イベント集計。参考情報 | `POST /events`（デバイス発）、`POST /parking-lots/{id}/reset`（`target=system`、Admin） |

| 操作 | エンドポイント | 認証 | 用途 |
|---|---|---|---|
| リセット | `POST /parking-lots/{id}/reset` | Admin | `target`（`current`/`system`）で指定した方を、実車確認や機器ズレの補正のため指定台数に直接設定する |
| 一括リセット | `POST /parking-lots/reset-all` | Admin | `target`で指定した方（`current`/`system`）を全駐車場まとめて0にリセットする（イベント開始時の初期化など） |
| 手動増減 | `POST /parking-lots/{id}/adjust` | 一般ユーザー | `current_count`を1台単位などで増減させる |
| 入出庫イベント | `POST /events`（デバイス発） | デバイス | `system_count`を増減させる通常の検出フロー |

いずれも `parking_activities` に記録され、時系列分析や「誰が変更したか」の監査に使える
（`GET /parking-lots/{id}/activities`、Admin専用）。リセット・手動増減の `actor_label` には、
検証済みGoogleアカウントから抽出したラベル（例: `25.m.kitano`）が入る。

`ParkingLotOut` の `has_device`（`devices`とのリレーションから算出する計算プロパティ）で、
その駐車場にデバイスが紐づいているかを判定できる。`manager` の画面では、`has_device` が
`true` の駐車場のみ `current_count` の下に `system_count` を小さく併記する。

## データモデル

| テーブル | 役割 |
|---|---|
| `parking_lots` | 駐車場。`current_count`（人力）と`system_count`（デバイス）を独立して保持 |
| `devices` | エッジデバイス。API キーのハッシュ、最終通信時刻、最終ステータスを保持 |
| `parking_events` | 個々の入出庫イベント（`entry` / `exit`） |
| `device_commands` | デバイスへのコマンドキュー（`pending` → `delivered` → `completed`/`failed`） |
| `parking_activities` | `current_count`/`system_count`変更の統合ログ（入出庫・手動増減・リセット、誰が/何が変更したか） |
| `admin_users` | Admin許可リスト（Googleアカウントのメールアドレスのみ、パスワードなし） |
| `admin_refresh_tokens` | Adminセッションのリフレッシュトークン |

ER図・カラム定義・状態遷移などの詳細は [`docs/db-schema.md`](docs/db-schema.md) を参照。

## License

MIT License. 詳細は [LICENSE](LICENSE) を参照。
