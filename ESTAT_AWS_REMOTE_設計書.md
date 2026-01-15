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
                           │ MCP over HTTP
                           │
┌──────────────────────────┴──────────────────────────────┐
│              mcp_aws_wrapper.py                          │
│         (MCP Protocol → HTTP Bridge)                     │
│  - initialize, tools/list, tools/call                    │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP REST API
                           │
┌──────────────────────────┴──────────────────────────────┐
│           AWS ECS Fargate (ALB)                          │
│     estat-mcp-alb-633149734.ap-northeast-1.elb...       │
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

1. **クライアント層**: Kiro (MCP Client)
2. **プロトコル変換層**: mcp_aws_wrapper.py
3. **API層**: AWS ALB + ECS Fargate
4. **ビジネスロジック層**: EStatAWSServer
5. **データ層**: e-Stat API, AWS S3, AWS Athena

---

## コンポーネント構成

### 1. MCPラッパー (`mcp_aws_wrapper.py`)

**役割**: MCPプロトコルとHTTP APIの橋渡し

**主要機能**:

- `handle_initialize()`: MCP初期化リクエスト処理
- `handle_tools_list()`: ツール一覧取得
- `handle_tools_call()`: ツール実行リクエスト処理

**通信フロー**:
```python
# 標準入出力でMCPリクエストを受信
for line in sys.stdin:
    request = json.loads(line)
    # HTTP APIに変換して転送
    response = requests.post(f"{API_URL}/execute", json=request)
    # MCPレスポンスとして返却
    print(json.dumps(response))
```

**エンドポイント**:
- `GET /tools`: ツール一覧取得
- `POST /execute`: ツール実行

### 2. メインサーバー (`mcp_servers/estat_aws/server.py`)

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
    
    # AWSクライアント
    self.s3_client = boto3.client('s3', region_name=AWS_REGION)
    self.athena_client = boto3.client('athena', region_name=AWS_REGION)
```

**環境変数**:
- `ESTAT_APP_ID`: e-Stat APIキー
- `S3_BUCKET`: データ保存先S3バケット (estat-data-lake)
- `AWS_REGION`: AWSリージョン (ap-northeast-1)
- `LOG_LEVEL`: ログレベル (INFO/DEBUG/ERROR)

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
search_estat_data
    ↓ (dataset_id取得)
fetch_dataset_auto
    ↓ (S3にJSON保存)
save_dataset_as_csv
    ↓ (S3にCSV保存)
get_csv_download_url
    ↓ (署名付きURL生成)
User Download
```

#### パターン2: 大規模データ分析

```
User Query
    ↓
search_estat_data
    ↓
fetch_dataset_filtered (絞り込み)
    ↓ (S3にJSON保存)
transform_to_parquet
    ↓ (S3にParquet保存)
load_to_iceberg
    ↓ (Athenaテーブル作成)
analyze_with_athena
    ↓
Analysis Results
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

### 3. ネットワークセキュリティ

**ALB (Application Load Balancer)**:
- HTTPSエンドポイント
- セキュリティグループ
- VPC内通信

### 4. データ保護

**S3暗号化**:
- サーバーサイド暗号化 (SSE-S3)
- バケットポリシー

**署名付きURL**:
- 有効期限付き (デフォルト: 1時間)
- ダウンロード専用

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

### メトリクス

- ツール呼び出し回数
- 実行時間
- エラー率
- データ取得量

### アラート

- API制限到達
- S3容量不足
- Athenaクエリ失敗

---

## 今後の拡張

### 機能拡張

1. **キャッシュ層の追加**
   - Redis/Elasticacheによる検索結果キャッシュ
   - メタデータキャッシュ

2. **バッチ処理**
   - 定期的なデータ更新
   - 自動インデックス作成

3. **可視化機能**
   - グラフ生成
   - ダッシュボード

4. **多言語対応**
   - 英語インターフェース
   - 国際統計データ対応

### パフォーマンス改善

1. **分散処理**
   - AWS Lambda並列実行
   - Step Functions統合

2. **ストリーミング処理**
   - 大規模データのストリーミング取得
   - リアルタイム分析

---

**作成日**: 2026年1月15日  
**バージョン**: v2.1.0  
**作成者**: Kiro AI Assistant
