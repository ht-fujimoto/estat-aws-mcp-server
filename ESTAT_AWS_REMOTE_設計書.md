# estat-aws-remote MCP サーバー 設計書

## 📋 目次

1. [システム概要](#システム概要)
2. [アーキテクチャ](#アーキテクチャ)
3. [コンポーネント構成](#コンポーネント構成)
4. [ツール仕様](#ツール仕様)
5. [データフロー](#データフロー)
6. [エラーハンドリング](#エラーハンドリング)
7. [パフォーマンス最適化](#パフォーマンス最適化)
8. [セキュリティ](#セキュリティ)

---

## システム概要

### プロジェクト名
**estat-aws-remote** - e-Stat統計データ取得・分析MCPサーバー

### 目的
日本政府の統計データポータル「e-Stat」のデータを、自然言語で検索・取得・分析できるMCP（Model Context Protocol）サーバーを提供する。

### 主要機能
- 自然言語による統計データ検索
- キーワード自動変換・サジェスト機能
- 大規模データの自動分割取得
- CSV/Parquet形式への変換
- AWS S3への永続化保存
- Athenaによる統計分析

### 技術スタック
- **言語**: Python 3.9+
- **フレームワーク**: FastAPI (HTTP API)
- **クラウド**: AWS (S3, Athena, ECS Fargate)
- **データ形式**: JSON, CSV, Parquet, Iceberg
- **プロトコル**: MCP (Model Context Protocol)

---

## アーキテクチャ

### システム構成図

```
┌─────────────────────────────────────────────────────────────┐
│                         Kiro Client                          │
│                    (MCP Protocol Client)                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ MCP over HTTPS
                           │ (streamable-http transport)
                           │
┌──────────────────────────┴──────────────────────────────┐
│              AWS Application Load Balancer               │
│     https://estat-mcp.snowmole.co.jp/mcp                │
│  - SSL/TLS Termination (ACM Certificate)                │
│  - Health Check                                          │
│  - Load Balancing                                        │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────┐
│           AWS ECS Fargate (Container)                    │
│  - Auto Scaling                                          │
│  - Task Definition                                       │
│  - Service Discovery                                     │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────┐
│         server_mcp_streamable.py                         │
│         (MCP Streamable HTTP Server)                     │
│  - aiohttp Web Server                                    │
│  - JSON-RPC 2.0 Handler                                  │
│  - SSE Stream Support                                    │
│  - MCP Protocol Implementation                           │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────┐
│         mcp_servers/estat_aws/server.py                  │
│              (EStatAWSServer Class)                      │
│  - 11 Tools Implementation                               │
│  - e-Stat API Integration                                │
│  - AWS Services Integration                              │
└──────────────────────────┬──────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼────────┐ ┌──────▼──────┐ ┌────────▼────────┐
│   e-Stat API   │ │   AWS S3    │ │  AWS Athena     │
│  (JSON REST)   │ │ (Data Lake) │ │ (SQL Analysis)  │
└────────────────┘ └─────────────┘ └─────────────────┘
```

### レイヤー構造

1. **クライアント層**: Kiro (MCP Client with streamable-http support)
2. **ロードバランサー層**: AWS ALB (HTTPS termination)
3. **コンテナ層**: AWS ECS Fargate (Auto-scaling)
4. **MCPサーバー層**: server_mcp_streamable.py (aiohttp)
5. **ビジネスロジック層**: EStatAWSServer
6. **データ層**: e-Stat API, AWS S3, AWS Athena, AWS Glue

---

## コンポーネント構成

### 1. Kiro Client (MCPクライアント)

**役割**: MCP streamable-httpプロトコルでサーバーと通信

**設定** (.kiro/settings/mcp.json):
```json
{
  "estat-aws-remote": {
    "transport": "streamable-http",
    "url": "https://estat-mcp.snowmole.co.jp/mcp",
    "disabled": false,
    "autoApprove": [
      "search_estat_data",
      "apply_keyword_suggestions",
      "fetch_dataset_auto",
      "fetch_large_dataset_complete",
      "fetch_dataset_filtered",
      "transform_to_parquet",
      "load_to_iceberg",
      "analyze_with_athena",
      "save_dataset_as_csv",
      "download_csv_from_s3",
      "get_csv_download_url"
    ]
  }
}
```

**通信フロー**:
```
1. GET /mcp (SSE接続確立)
   ↓
2. POST /mcp (JSON-RPC initialize)
   ↓
3. POST /mcp (JSON-RPC tools/list)
   ↓
4. POST /mcp (JSON-RPC tools/call)
   ↓
5. DELETE /mcp (セッション終了)
```

### 2. AWS Application Load Balancer

**役割**: HTTPS終端、負荷分散、ヘルスチェック

**設定**:
- **URL**: https://estat-mcp.snowmole.co.jp
- **SSL証明書**: AWS Certificate Manager (ACM)
- **ターゲットグループ**: ECS Fargate タスク
- **ヘルスチェック**: GET /health

**機能**:
- SSL/TLS終端
- HTTP/2サポート
- WebSocket/SSEサポート
- 自動スケーリング連携

### 3. AWS ECS Fargate

**役割**: コンテナ実行環境

**タスク定義**:
```json
{
  "family": "estat-mcp-server",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "estat-mcp",
      "image": "123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/estat-mcp:latest",
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "ESTAT_APP_ID", "value": "..."},
        {"name": "S3_BUCKET", "value": "estat-data-lake"},
        {"name": "AWS_REGION", "value": "ap-northeast-1"},
        {"name": "PORT", "value": "8080"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/estat-mcp",
          "awslogs-region": "ap-northeast-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

**サービス設定**:
- **デプロイタイプ**: Rolling update
- **最小ヘルシータスク**: 100%
- **最大タスク**: 200%
- **Auto Scaling**: CPU使用率 > 70%で自動スケール

### 4. server_mcp_streamable.py (MCPサーバー)

**役割**: MCP streamable-httpプロトコルの実装

**主要機能**:


#### HTTP エンドポイント

**GET /mcp** - SSEストリーム確立
```python
async def handle_sse_stream(request):
    response = web.StreamResponse()
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    
    await response.prepare(request)
    
    # 初期化メッセージ送信
    initialization_message = "event: connection\ndata: {\"status\": \"ready\"}\n\n"
    await response.write(initialization_message.encode('utf-8'))
    
    # 接続維持
    while True:
        await asyncio.sleep(1)
        if response.transport.is_closing():
            break
    
    return response
```

**POST /mcp** - JSON-RPCメッセージ処理
```python
async def handle_jsonrpc_message(data):
    method = data.get('method')
    params = data.get('params', {})
    request_id = data.get('id')
    
    if method == 'initialize':
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "estat-aws", "version": "1.0.0"}
            }
        }
    
    elif method == 'tools/list':
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": [...]}
        }
    
    elif method == 'tools/call':
        tool_name = params.get('name')
        arguments = params.get('arguments', {})
        
        # ツール実行
        tool_handler = TOOLS[tool_name]["handler"]
        result = await tool_handler(**arguments)
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {"type": "text", "text": json.dumps(result)}
                ]
            }
        }
```

**DELETE /mcp** - セッション終了
```python
async def handle_mcp_endpoint(request):
    if request.method == 'DELETE':
        session_id = request.headers.get('Mcp-Session-Id')
        # セッションクリーンアップ
        return web.Response(status=200, text="Session terminated")
```

#### ツールマッピング

```python
TOOLS = {
    "search_estat_data": {
        "handler": lambda **kwargs: estat_server.search_estat_data(**kwargs),
        "description": "自然言語でe-Statデータを検索",
        "parameters": {
            "query": {"type": "string", "required": True},
            "max_results": {"type": "integer", "default": 5},
            "auto_suggest": {"type": "boolean", "default": True},
            "scoring_method": {"type": "string", "default": "enhanced"}
        }
    },
    # ... 全11ツール
}
```

### 5. EStatAWSServer (ビジネスロジック)

**クラス**: `EStatAWSServer`

**初期化処理**:
```python
def __init__(self):
    self.app_id = ESTAT_APP_ID
    self.base_url = "https://api.e-stat.go.jp/rest/3.0/app/json"
    
    # HTTPセッション（コネクションプーリング）
    self.session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=3
    )
    self.session.mount('https://', adapter)
    
    # AWSクライアント
    self.s3_client = boto3.client('s3', region_name=AWS_REGION)
    self.athena_client = boto3.client('athena', region_name=AWS_REGION)
```

**環境変数**:
- `ESTAT_APP_ID`: e-Stat APIキー
- `S3_BUCKET`: データ保存先S3バケット (estat-data-lake)
- `AWS_REGION`: AWSリージョン (ap-northeast-1)
- `LOG_LEVEL`: ログレベル (INFO/DEBUG/ERROR)
- `PORT`: HTTPサーバーポート (8080)

### 3. ユーティリティモジュール

#### 3.1 エラーハンドリング (`utils/error_handler.py`)

**カスタム例外**:

- `EStatError`: e-Stat API関連エラー
- `AWSError`: AWSサービス関連エラー
- `DataTransformError`: データ変換エラー

**機能**:
- エラーレスポンスの統一フォーマット化
- 機密情報（APIキー、AWSクレデンシャル）の自動マスキング
- エラーコードの自動分類

#### 3.2 リトライロジック (`utils/retry.py`)

**デコレータ**: `@retry_with_backoff`

**パラメータ**:
- `max_retries`: 最大リトライ回数 (デフォルト: 3)
- `base_delay`: 基本遅延時間 (デフォルト: 1.0秒)
- `max_delay`: 最大遅延時間 (デフォルト: 60秒)
- `exponential_base`: 指数バックオフの基数 (デフォルト: 2.0)

**リトライ対象エラー**:
- タイムアウト
- ネットワークエラー
- レート制限 (429, 503, 504)

#### 3.3 ロギング (`utils/logger.py`)

**機能**:
- 構造化ログ出力
- ツール呼び出しのトレース
- 実行時間の計測

#### 3.4 レスポンスフォーマッター (`utils/response_formatter.py`)

**機能**:
- 成功/エラーレスポンスの統一フォーマット
- タイムスタンプの自動付与
- データセット情報の整形

### 4. キーワード辞書 (`keyword_dictionary.py`)

**目的**: 一般用語を統計用語に自動変換

**辞書サイズ**: 100以上の用語マッピング

**カテゴリ**:
- 所得・収入・経済関連
- 年齢・世代関連
- 人口・世帯関連
- 地域・地理関連
- 就業・労働関連
- 家族・世帯関連
- 婚姻・家族形成関連
- 健康・医療・死亡関連
- 事故・安全関連
- 教育関連
- 住宅・建設関連
- 消費・支出関連
- 産業・経済活動関連

**データ構造**:
```python
KEYWORD_SUGGESTIONS = {
    "収入": {
        "suggested": "所得",
        "reason": "公式統計では「所得」が一般的に使用されます",
        "alternatives": ["賃金", "給与"]
    },
    # ...
}
```

---

## ツール仕様

### ツール一覧

| No | ツール名 | 機能概要 | 主要パラメータ |
|----|---------|---------|--------------|
| 1 | search_estat_data | 自然言語検索 | query, max_results, auto_suggest |
| 2 | apply_keyword_suggestions | キーワード変換適用 | original_query, accepted_keywords |
| 3 | fetch_dataset_auto | データ自動取得 | dataset_id, save_to_s3 |
| 4 | fetch_large_dataset_complete | 大規模データ完全取得 | dataset_id, max_records, chunk_size |
| 5 | fetch_dataset_filtered | 条件絞り込み取得 | dataset_id, filters |
| 6 | save_dataset_as_csv | CSV形式保存 | dataset_id, s3_json_path |
| 7 | get_csv_download_url | ダウンロードURL生成 | s3_path, expires_in |
| 8 | download_csv_from_s3 | CSVダウンロード | s3_path, local_path |
| 9 | transform_to_parquet | Parquet変換 | s3_json_path, data_type |
| 10 | load_to_iceberg | Icebergテーブル投入 | table_name, s3_parquet_path |
| 11 | analyze_with_athena | 統計分析実行 | table_name, analysis_type |

### ツール詳細仕様

#### 1. search_estat_data

**目的**: 自然言語クエリでe-Statデータを検索

**処理フロー**:

```
1. キーワードサジェスト確認
   ↓ (サジェストあり)
2. サジェスト提案を返却
   ↓ (サジェストなし/適用後)
3. e-Stat API呼び出し (getStatsList)
   ↓
4. 基本スコアリング (全結果)
   ↓
5. Top 20選択
   ↓
6. メタデータ並列取得 (Top 20)
   ↓
7. 強化スコアリング (メタデータ含む)
   ↓
8. Top N返却
```

**スコアリングアルゴリズム**:

基本スコア (0.0 ~ 1.0):
- タイトルマッチ: 25%
- 統計名・分類マッチ: 15%
- 説明文マッチ: 10%
- 更新日の新しさ: 15%
- 政府組織の信頼性: 10%
- データの完全性: 5%

強化スコア (基本スコア80% + 追加20%):
- カテゴリマッチ: 15%
- データ規模の適切性: 5%

**パラメータ**:
```python
query: str              # 検索クエリ
max_results: int = 5    # 返却する最大件数
auto_suggest: bool = True  # キーワードサジェスト有効化
scoring_method: str = "enhanced"  # スコアリング方法
```

**レスポンス例**:
```json
{
  "success": true,
  "query": "北海道 人口",
  "total_found": 150,
  "results": [
    {
      "rank": 1,
      "dataset_id": "0003458339",
      "title": "人口推計（令和2年国勢調査基準）",
      "score": 0.892,
      "total_records": 47000,
      "total_records_formatted": "47,000件",
      "requires_filtering": false,
      "categories": {
        "area": {
          "name": "地域",
          "count": 47,
          "sample": ["北海道", "青森県", "岩手県", ...]
        }
      }
    }
  ]
}
```

#### 2. apply_keyword_suggestions

**目的**: ユーザーが承認したキーワード変換を適用

**処理フロー**:
```
1. 元のクエリを単語分割
   ↓
2. 承認された変換を適用
   ↓
3. 新しいクエリを生成
```

**パラメータ**:
```python
original_query: str           # 元のクエリ
accepted_keywords: Dict[str, str]  # 承認された変換 {"収入": "所得"}
```

#### 3. fetch_dataset_auto

**目的**: データサイズに応じて最適な取得方法を自動選択

**処理フロー**:
```
1. メタデータ取得 (limit=1)
   ↓
2. 総レコード数確認
   ↓
3. サイズ判定
   ├─ ≤ 100,000件 → 単一リクエスト取得
   └─ > 100,000件 → 分割取得 (fetch_large_dataset_complete)
```

**定数**:
```python
LARGE_DATASET_THRESHOLD = 100000  # 10万件
```

#### 4. fetch_large_dataset_complete

**目的**: 大規模データの分割取得（最初のチャンクのみ）

**制限事項**:
- MCPタイムアウト制限により、最初のチャンクのみ取得
- 完全取得にはスタンドアロンPythonスクリプトを推奨

**パラメータ**:
```python
dataset_id: str
max_records: int = 1000000    # 最大100万件
chunk_size: int = 100000      # 1チャンク10万件
save_to_s3: bool = True
convert_to_japanese: bool = True
```

#### 5. fetch_dataset_filtered

**目的**: カテゴリ指定での絞り込み取得

**処理フロー**:
```
1. メタデータ取得
   ↓
2. フィルタ検証
   ├─ 日本語名 → コードに変換
   ├─ コード → そのまま使用
   └─ 部分マッチ → 候補提案
   ↓
3. データ取得 (フィルタ適用)
   ↓
4. S3保存
```

**フィルタ例**:
```python
filters = {
    "area": "13000",      # 東京都
    "cat01": "A1101",     # カテゴリ1
    "time": "2020"        # 2020年
}
```

#### 6. save_dataset_as_csv

**目的**: JSONデータをCSV形式に変換してS3保存

**特徴**:
- BOM付きUTF-8エンコーディング（Excel互換）
- pandas DataFrameを使用
- S3保存失敗時はローカル保存にフォールバック

**パラメータ**:
```python
dataset_id: str
s3_json_path: Optional[str] = None
local_json_path: Optional[str] = None
output_filename: Optional[str] = None
```

#### 7. get_csv_download_url

**目的**: S3 CSVファイルの署名付きダウンロードURL生成

**特徴**:
- 有効期限付きURL (デフォルト: 1時間)
- ファイル名指定可能
- ファイルサイズ情報付与

**パラメータ**:
```python
s3_path: str                    # s3://bucket/key 形式
expires_in: int = 3600          # 有効期限（秒）
filename: Optional[str] = None  # ダウンロード時のファイル名
```

#### 8. download_csv_from_s3

**目的**: S3からCSVファイルをダウンロード

**モード**:
- `return_content=False`: ローカルファイルに保存
- `return_content=True`: CSV内容を直接返却（リモートサーバー向け）

#### 9. transform_to_parquet

**目的**: JSONデータをParquet形式に変換

**利点**:
- データサイズ削減 (50-80%)
- 高速クエリ処理
- カラムナーストレージ

**データ型別スキーマ**:
- `population`: year, region_code, region_name, category
- `economy`: year, quarter, region_code, indicator
- `education`: year, region_code, school_type, metric
- `generic`: year, region_code, category

#### 10. load_to_iceberg

**目的**: ParquetデータをAthena Icebergテーブルに投入

**処理フロー**:
```
1. データベース存在確認/作成
   ↓
2. Icebergテーブル作成
   ↓
3. 外部テーブル作成 (Parquetソース)
   ↓
4. データ投入 (INSERT INTO)
   ↓
5. レコード数確認
   ↓
6. 外部テーブル削除
```

**Icebergテーブル設定**:
```sql
CREATE TABLE IF NOT EXISTS estat_db.{table_name} (
    stats_data_id STRING,
    year INT,
    region_code STRING,
    category STRING,
    value DOUBLE,
    unit STRING,
    updated_at TIMESTAMP
)
LOCATION 's3://{bucket}/iceberg-tables/{table_name}/'
TBLPROPERTIES (
    'table_type'='ICEBERG',
    'format'='parquet'
)
```

#### 11. analyze_with_athena

**目的**: Athenaで統計分析を実行

**分析タイプ**:

**basic**:
- レコード数
- 基本統計 (平均、最小、最大、合計)
- 年別集計

**advanced**:
- 地域別集計 (Top 10)
- カテゴリ別集計 (Top 10)
- 時系列トレンド

**custom**:
- カスタムSQLクエリ実行

---

## データフロー

### 典型的な使用パターン

#### パターン1: データ検索→CSV取得

```
User Query
    ↓
Kiro Client (MCP)
    ↓ HTTPS POST /mcp (tools/call: search_estat_data)
AWS ALB
    ↓
ECS Fargate (server_mcp_streamable.py)
    ↓
EStatAWSServer.search_estat_data()
    ↓ (dataset_id取得)
Kiro Client (MCP)
    ↓ HTTPS POST /mcp (tools/call: fetch_dataset_auto)
EStatAWSServer.fetch_dataset_auto()
    ↓ (S3にJSON保存)
Kiro Client (MCP)
    ↓ HTTPS POST /mcp (tools/call: save_dataset_as_csv)
EStatAWSServer.save_dataset_as_csv()
    ↓ (S3にCSV保存)
Kiro Client (MCP)
    ↓ HTTPS POST /mcp (tools/call: get_csv_download_url)
EStatAWSServer.get_csv_download_url()
    ↓ (署名付きURL生成)
User Download (Browser/curl)
```

#### パターン2: 大規模データ分析

```
User Query
    ↓
Kiro Client (MCP)
    ↓ HTTPS POST /mcp (tools/call: search_estat_data)
EStatAWSServer.search_estat_data()
    ↓
Kiro Client (MCP)
    ↓ HTTPS POST /mcp (tools/call: fetch_dataset_filtered)
EStatAWSServer.fetch_dataset_filtered(絞り込み)
    ↓ (S3にJSON保存)
Kiro Client (MCP)
    ↓ HTTPS POST /mcp (tools/call: transform_to_parquet)
EStatAWSServer.transform_to_parquet()
    ↓ (S3にParquet保存)
Kiro Client (MCP)
    ↓ HTTPS POST /mcp (tools/call: load_to_iceberg)
EStatAWSServer.load_to_iceberg()
    ↓ (Athenaテーブル作成)
Kiro Client (MCP)
    ↓ HTTPS POST /mcp (tools/call: analyze_with_athena)
EStatAWSServer.analyze_with_athena()
    ↓
Analysis Results
```

### MCP通信フロー詳細

#### 1. セッション確立

```
Client → Server: GET /mcp
  Headers:
    Accept: text/event-stream
    
Server → Client: 200 OK
  Headers:
    Content-Type: text/event-stream
    Cache-Control: no-cache
    Connection: keep-alive
  Body:
    event: connection
    data: {"status": "ready", "timestamp": "2026-01-15T14:30:00Z"}
```

#### 2. 初期化

```
Client → Server: POST /mcp
  Body:
    {
      "jsonrpc": "2.0",
      "id": 1,
      "method": "initialize",
      "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "kiro", "version": "1.0.0"}
      }
    }

Server → Client: 200 OK
  Body:
    {
      "jsonrpc": "2.0",
      "id": 1,
      "result": {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "estat-aws", "version": "1.0.0"}
      }
    }
```

#### 3. ツール一覧取得

```
Client → Server: POST /mcp
  Body:
    {
      "jsonrpc": "2.0",
      "id": 2,
      "method": "tools/list",
      "params": {}
    }

Server → Client: 200 OK
  Body:
    {
      "jsonrpc": "2.0",
      "id": 2,
      "result": {
        "tools": [
          {
            "name": "search_estat_data",
            "description": "自然言語でe-Statデータを検索",
            "inputSchema": {
              "type": "object",
              "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer"}
              },
              "required": ["query"]
            }
          },
          ...
        ]
      }
    }
```

#### 4. ツール実行

```
Client → Server: POST /mcp
  Body:
    {
      "jsonrpc": "2.0",
      "id": 3,
      "method": "tools/call",
      "params": {
        "name": "search_estat_data",
        "arguments": {
          "query": "北海道 人口",
          "max_results": 5
        }
      }
    }

Server → Client: 200 OK
  Body:
    {
      "jsonrpc": "2.0",
      "id": 3,
      "result": {
        "content": [
          {
            "type": "text",
            "text": "{\"success\": true, \"results\": [...]}"
          }
        ]
      }
    }
```

#### 5. セッション終了

```
Client → Server: DELETE /mcp
  Headers:
    Mcp-Session-Id: abc123

Server → Client: 200 OK
  Body: "Session terminated"
```

### S3バケット構造

```
s3://estat-data-lake/
├── raw/
│   └── data/
│       ├── {dataset_id}_{timestamp}.json
│       └── {dataset_id}_filtered_{timestamp}.json
├── csv/
│   └── {dataset_id}_{timestamp}.csv
├── processed/
│   └── {dataset_id}_{timestamp}.parquet
├── iceberg-tables/
│   └── {table_name}/
│       └── (Icebergメタデータ)
└── athena-results/
    └── (Athenaクエリ結果)
```

---

## エラーハンドリング

### エラー分類

| エラーコード | 説明 | 対応 |
|------------|------|------|
| ESTAT_API_ERROR | e-Stat API関連エラー | リトライ、パラメータ確認 |
| AWS_SERVICE_ERROR | AWSサービスエラー | 認証情報確認、リトライ |
| DATA_TRANSFORM_ERROR | データ変換エラー | データ形式確認 |
| INVALID_PARAMETER | パラメータ不正 | パラメータ修正 |
| TIMEOUT_ERROR | タイムアウト | チャンクサイズ削減 |
| INTERNAL_ERROR | 内部エラー | ログ確認 |

### リトライ戦略

**指数バックオフ**:
```
遅延時間 = min(base_delay × (2 ^ attempt), max_delay)

例:
- 1回目: 1秒
- 2回目: 2秒
- 3回目: 4秒
- 4回目: 8秒
```

**リトライ対象**:
- ネットワークエラー
- タイムアウト
- レート制限 (429, 503, 504)

---

## パフォーマンス最適化

### 1. コネクションプーリング

```python
adapter = requests.adapters.HTTPAdapter(
    pool_connections=10,  # プールサイズ
    pool_maxsize=20,      # 最大接続数
    max_retries=3         # リトライ回数
)
```

### 2. 並列処理

**メタデータ取得の並列化**:
```python
tasks = [self._get_metadata_quick(dataset_id) for dataset_id in top_20]
metadata_list = await asyncio.gather(*tasks, return_exceptions=True)
```

### 3. キャッシング

**LRUキャッシュ**:
```python
@lru_cache(maxsize=128)
def _get_cached_metadata(dataset_id: str):
    # メタデータをキャッシュ
    pass
```

### 4. データ圧縮

- JSON → Parquet: 50-80%削減
- カラムナーストレージによる高速クエリ

---

## セキュリティ

### 1. 機密情報の保護

**自動マスキング**:
- APIキー (32文字の英数字)
- AWSアクセスキー (AKIA...)
- AWSシークレットキー (40文字)

### 2. 認証・認可

**AWS IAM**:
- S3バケットアクセス権限
- Athenaクエリ実行権限
- ECS Fargateタスクロール
- Glue Data Catalogアクセス権限

**ECS Task Role**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::estat-data-lake",
        "arn:aws:s3:::estat-data-lake/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase",
        "glue:GetTable",
        "glue:CreateDatabase",
        "glue:CreateTable"
      ],
      "Resource": "*"
    }
  ]
}
```

### 3. ネットワークセキュリティ

**ALB (Application Load Balancer)**:
- **HTTPS強制**: HTTP → HTTPS リダイレクト
- **SSL/TLS**: TLS 1.2以上
- **ACM証明書**: AWS Certificate Manager管理
- **セキュリティグループ**: 
  - Inbound: 443 (HTTPS) from 0.0.0.0/0
  - Outbound: All traffic

**ECS Fargate**:
- **VPC**: プライベートサブネット
- **セキュリティグループ**:
  - Inbound: 8080 from ALB security group
  - Outbound: 443 (HTTPS) to e-Stat API, AWS services
- **NAT Gateway**: インターネットアクセス用

### 4. データ保護

**S3暗号化**:
- サーバーサイド暗号化 (SSE-S3)
- バケットポリシーによるアクセス制御
- バージョニング有効化

**署名付きURL**:
- 有効期限付き (デフォルト: 1時間)
- ダウンロード専用
- 一時的なアクセス権限

### 5. 通信セキュリティ

**HTTPS通信**:
```
Kiro Client
    ↓ TLS 1.2+
AWS ALB (SSL Termination)
    ↓ HTTP (VPC内)
ECS Fargate
```

**MCP over HTTPS**:
- JSON-RPC 2.0 over HTTPS
- SSE (Server-Sent Events) over HTTPS
- WebSocket-like persistent connection

---

## 運用・監視

### ログ出力

**構造化ログ**:
```python
logger.info("Tool called", extra={
    "tool_name": "search_estat_data",
    "query": query,
    "execution_time": 1.23
})
```

**CloudWatch Logs**:
- ログストリーム: `/ecs/estat-mcp`
- ログ保持期間: 30日
- ログレベル: INFO (本番), DEBUG (開発)

**ログ例**:
```
[2026-01-15T14:30:00] Starting e-Stat AWS MCP Server (Streamable HTTP)
[2026-01-15T14:30:00] Host: 0.0.0.0:8080
[2026-01-15T14:30:01] e-Stat AWS Server initialized successfully
[2026-01-15T14:30:05] MCP Request: POST from 10.0.1.50
[2026-01-15T14:30:05] JSONRPC Request: method=tools/call, id=3
[2026-01-15T14:30:05] Executing tool: search_estat_data
[2026-01-15T14:30:07] Tool execution completed successfully: search_estat_data
```

### メトリクス

**CloudWatch Metrics**:
- **ECS Metrics**:
  - CPUUtilization
  - MemoryUtilization
  - TaskCount
  - RunningTaskCount

- **ALB Metrics**:
  - RequestCount
  - TargetResponseTime
  - HTTPCode_Target_2XX_Count
  - HTTPCode_Target_5XX_Count
  - HealthyHostCount
  - UnHealthyHostCount

- **カスタムメトリクス**:
  - ツール呼び出し回数
  - ツール実行時間
  - エラー率
  - データ取得量

### アラート

**CloudWatch Alarms**:

1. **高CPU使用率**
   - 条件: CPUUtilization > 70% for 5 minutes
   - アクション: Auto Scaling + SNS通知

2. **高メモリ使用率**
   - 条件: MemoryUtilization > 80% for 5 minutes
   - アクション: SNS通知

3. **エラー率上昇**
   - 条件: HTTPCode_Target_5XX_Count > 10 for 1 minute
   - アクション: SNS通知

4. **ヘルスチェック失敗**
   - 条件: UnHealthyHostCount > 0 for 2 minutes
   - アクション: Auto Scaling + SNS通知

5. **レスポンス時間遅延**
   - 条件: TargetResponseTime > 5 seconds for 3 minutes
   - アクション: SNS通知

### Auto Scaling

**スケーリングポリシー**:

```json
{
  "TargetTrackingScalingPolicyConfiguration": {
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
    },
    "ScaleInCooldown": 300,
    "ScaleOutCooldown": 60
  }
}
```

**スケーリング設定**:
- **最小タスク数**: 1
- **最大タスク数**: 10
- **希望タスク数**: 2
- **スケールアウト**: CPU > 70% → +1タスク
- **スケールイン**: CPU < 50% → -1タスク

### デプロイメント

**Blue/Green Deployment**:
```
1. 新しいタスク定義を作成
   ↓
2. 新しいタスクを起動（Green）
   ↓
3. ヘルスチェック確認
   ↓
4. ALBトラフィックを徐々に移行
   ↓
5. 旧タスクを停止（Blue）
```

**ロールバック**:
- 自動: ヘルスチェック失敗時
- 手動: AWS Console / CLI

### バックアップ

**S3データ**:
- バージョニング有効
- ライフサイクルポリシー:
  - 30日後: Standard-IA
  - 90日後: Glacier
  - 365日後: 削除

**Glue Data Catalog**:
- 自動バックアップ（AWS管理）
- テーブル定義のエクスポート

---

## 今後の拡張

### 機能拡張

1. **キャッシュ層の追加**
   - Redis/Elasticacheによる検索結果キャッシュ
   - メタデータキャッシュ
   - TTL: 1時間

2. **バッチ処理**
   - 定期的なデータ更新
   - 自動インデックス作成
   - AWS Lambda + EventBridge

3. **可視化機能**
   - グラフ生成 (matplotlib/plotly)
   - ダッシュボード (QuickSight連携)
   - レポート自動生成

4. **多言語対応**
   - 英語インターフェース
   - 国際統計データ対応
   - i18n実装

5. **認証・認可強化**
   - API Key認証
   - OAuth 2.0対応
   - ユーザー別クォータ管理

### パフォーマンス改善

1. **分散処理**
   - AWS Lambda並列実行
   - Step Functions統合
   - SQS/SNSによる非同期処理

2. **ストリーミング処理**
   - 大規模データのストリーミング取得
   - リアルタイム分析
   - Kinesis Data Streams連携

3. **CDN導入**
   - CloudFront配信
   - 静的コンテンツキャッシュ
   - エッジロケーション活用

4. **データベース最適化**
   - Athena Federated Query
   - Redshift連携
   - パーティション最適化

### インフラ改善

1. **マルチリージョン対応**
   - グローバルアクセラレータ
   - リージョン間レプリケーション
   - 災害復旧 (DR)

2. **コスト最適化**
   - Savings Plans
   - Spot Instances活用
   - S3 Intelligent-Tiering

3. **セキュリティ強化**
   - WAF (Web Application Firewall)
   - Shield (DDoS Protection)
   - GuardDuty (脅威検出)

4. **監視強化**
   - X-Ray (分散トレーシング)
   - CloudWatch Insights
   - カスタムダッシュボード

---

## 付録

### A. MCP Streamable HTTP仕様

**プロトコル**: MCP (Model Context Protocol) 2024-11-05

**トランスポート**: streamable-http

**特徴**:
- JSON-RPC 2.0ベース
- SSE (Server-Sent Events)サポート
- 双方向通信
- セッション管理

**エンドポイント**:
- `GET /mcp`: SSEストリーム確立
- `POST /mcp`: JSON-RPCメッセージ送信
- `DELETE /mcp`: セッション終了

### B. AWS リソース一覧

| リソース | 名前 | 用途 |
|---------|------|------|
| ALB | estat-mcp-alb | HTTPS終端、負荷分散 |
| ECS Cluster | estat-mcp-cluster | コンテナ実行環境 |
| ECS Service | estat-mcp-service | タスク管理 |
| ECR Repository | estat-mcp | Dockerイメージ保存 |
| S3 Bucket | estat-data-lake | データ保存 |
| Athena Workgroup | estat-mcp-workgroup | クエリ実行 |
| Glue Database | estat_db | メタデータ管理 |
| CloudWatch Log Group | /ecs/estat-mcp | ログ保存 |
| ACM Certificate | *.snowmole.co.jp | SSL/TLS証明書 |
| Route 53 | estat-mcp.snowmole.co.jp | DNS |

### C. 環境変数一覧

| 変数名 | 説明 | デフォルト値 |
|--------|------|------------|
| ESTAT_APP_ID | e-Stat APIキー | (必須) |
| S3_BUCKET | S3バケット名 | estat-data-lake |
| AWS_REGION | AWSリージョン | ap-northeast-1 |
| PORT | HTTPサーバーポート | 8080 |
| TRANSPORT_HOST | バインドホスト | 0.0.0.0 |
| LOG_LEVEL | ログレベル | INFO |

### D. エラーコード一覧

| コード | 説明 | 対応 |
|--------|------|------|
| -32700 | Parse error | JSON形式確認 |
| -32600 | Invalid Request | リクエスト形式確認 |
| -32601 | Method not found | メソッド名確認 |
| -32602 | Invalid params | パラメータ確認 |
| -32603 | Internal error | サーバーログ確認 |
| ESTAT_API_ERROR | e-Stat API関連エラー | リトライ、パラメータ確認 |
| AWS_SERVICE_ERROR | AWSサービスエラー | 認証情報確認、リトライ |
| DATA_TRANSFORM_ERROR | データ変換エラー | データ形式確認 |
| INVALID_PARAMETER | パラメータ不正 | パラメータ修正 |
| TIMEOUT_ERROR | タイムアウト | チャンクサイズ削減 |

---

**作成日**: 2026年1月15日  
**バージョン**: v2.1.0  
**作成者**: Kiro AI Assistant  
**アーキテクチャ**: Kiro → HTTPS → AWS ALB → ECS Fargate → server_mcp_streamable.py → EStatAWSServer
