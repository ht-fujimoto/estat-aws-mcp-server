# 設計文書: estat-aws 全機能実装

## 概要

estat-awsは、AWS ECS Fargate上で動作するe-Stat MCPサーバーです。本設計では、estat-enhancedが持つ全10個のツール機能をクラウド環境に実装し、タイムアウト制限なしで高度なデータ分析機能を提供します。

### 設計目標

1. **機能完全性**: estat-enhancedの全機能を実装
2. **スケーラビリティ**: 複数の同時リクエストを処理
3. **信頼性**: エラーハンドリングと自動リトライ
4. **パフォーマンス**: 60秒以内に大部分の操作を完了
5. **保守性**: モジュール化された設計

## アーキテクチャ

### システム構成図

```
┌─────────────┐
│   Kiro      │
│   Client    │
└──────┬──────┘
       │ MCP Protocol
       │ (JSON-RPC 2.0)
       ↓
┌──────────────────────────────────────┐
│  mcp_aws_wrapper.py                  │
│  (MCPプロトコルブリッジ)              │
└──────┬───────────────────────────────┘
       │ HTTP/JSON
       ↓
┌──────────────────────────────────────┐
│  Application Load Balancer (ALB)     │
│  - タイムアウト: 制限なし             │
│  - ヘルスチェック: /health            │
└──────┬───────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────┐
│  ECS Fargate Task                    │
│  ┌────────────────────────────────┐  │
│  │  server_http.py                │  │
│  │  - HTTPサーバー                 │  │
│  │  - ルーティング                 │  │
│  │  - CORS対応                    │  │
│  └────────┬───────────────────────┘  │
│           │                          │
│  ┌────────▼───────────────────────┐  │
│  │  EStatMCPServer                │  │
│  │  - 10個のツール実装             │  │
│  │  - e-Stat API統合              │  │
│  │  - AWS統合                     │  │
│  └────────┬───────────────────────┘  │
└───────────┼──────────────────────────┘
            │
    ┌───────┼───────┐
    │       │       │
    ↓       ↓       ↓
┌────────┐ ┌────┐ ┌────────┐
│e-Stat  │ │ S3 │ │Athena  │
│  API   │ │    │ │        │
└────────┘ └────┘ └────────┘
```

### レイヤー構造

1. **プロトコル層** (mcp_aws_wrapper.py)
   - MCPプロトコルの処理
   - JSON-RPC 2.0メッセージング

2. **HTTP層** (server_http.py)
   - HTTPリクエスト/レスポンス処理
   - ルーティング
   - CORS対応

3. **ビジネスロジック層** (EStatMCPServer)
   - 10個のツール実装
   - データ変換
   - エラーハンドリング

4. **統合層**
   - e-Stat API統合
   - AWS S3統合
   - AWS Athena統合

## コンポーネントとインターフェース

### 1. EStatMCPServer クラス

メインのビジネスロジックを実装するクラス。

```python
class EStatMCPServer:
    """e-Stat MCPサーバーのメイン実装"""
    
    def __init__(self):
        self.app_id = ESTAT_APP_ID
        self.s3_client = boto3.client('s3')
        self.athena_client = boto3.client('athena')
        self.keyword_dict = self._load_keyword_dictionary()
    
    # ツール実装メソッド
    def search_estat_data(self, query, max_results, auto_suggest, scoring_method)
    def apply_keyword_suggestions(self, original_query, accepted_keywords)
    def fetch_dataset_auto(self, dataset_id, save_to_s3, convert_to_japanese)
    def fetch_large_dataset_complete(self, dataset_id, max_records, chunk_size, ...)
    def fetch_dataset_filtered(self, dataset_id, filters, ...)
    def transform_to_parquet(self, s3_json_path, data_type, output_prefix)
    def load_to_iceberg(self, table_name, s3_parquet_path, create_if_not_exists)
    def analyze_with_athena(self, table_name, analysis_type, custom_query)
    def save_dataset_as_csv(self, dataset_id, local_json_path, s3_json_path, ...)
    def download_csv_from_s3(self, s3_path, local_path)
```

### 2. キーワードサジェスト機能

134用語の統計用語辞書を使用したキーワード最適化。

```python
KEYWORD_DICTIONARY = {
    "人口": ["人口", "総人口", "常住人口"],
    "世帯": ["世帯", "一般世帯", "世帯数"],
    "収入": ["収入", "所得", "年収"],
    # ... 134用語
}

def suggest_keywords(self, query: str) -> Dict[str, List[str]]:
    """クエリから統計用語を抽出し、代替案を提案"""
    suggestions = {}
    for word in query.split():
        if word in self.keyword_dict:
            suggestions[word] = self.keyword_dict[word]
    return suggestions
```

### 3. スコアリングアルゴリズム

8要素の拡張スコアリングで関連性を評価。

```python
def calculate_relevance_score(self, dataset, query) -> float:
    """
    8要素のスコアリング:
    1. タイトルマッチ (30%)
    2. 説明文マッチ (20%)
    3. 統計分野マッチ (15%)
    4. 更新日の新しさ (10%)
    5. データ規模 (10%)
    6. 提供機関の信頼性 (5%)
    7. メタデータの完全性 (5%)
    8. 利用頻度 (5%)
    """
    score = 0.0
    score += self._title_match_score(dataset, query) * 0.30
    score += self._description_match_score(dataset, query) * 0.20
    score += self._field_match_score(dataset, query) * 0.15
    score += self._recency_score(dataset) * 0.10
    score += self._size_score(dataset) * 0.10
    score += self._org_trust_score(dataset) * 0.05
    score += self._metadata_completeness_score(dataset) * 0.05
    score += self._usage_frequency_score(dataset) * 0.05
    return score
```

### 4. チャンク取得機能

大規模データセットを分割して取得。

```python
def fetch_in_chunks(self, dataset_id, chunk_size=100000, max_records=1000000):
    """
    チャンク取得のフロー:
    1. データセットサイズを取得
    2. チャンク数を計算
    3. 各チャンクを並列取得
    4. 結果を結合
    5. S3に保存
    """
    total_size = self._get_dataset_size(dataset_id)
    num_chunks = min(total_size // chunk_size + 1, max_records // chunk_size)
    
    chunks = []
    for i in range(num_chunks):
        start = i * chunk_size
        chunk = self._fetch_chunk(dataset_id, start, chunk_size)
        chunks.append(chunk)
    
    combined = self._combine_chunks(chunks)
    return combined
```

### 5. AWS統合

S3、Athena、Glueとの統合。

```python
class AWSIntegration:
    """AWS サービス統合"""
    
    def save_to_s3(self, data, bucket, key):
        """S3にデータを保存"""
        self.s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(data, ensure_ascii=False)
        )
    
    def convert_to_parquet(self, json_path, parquet_path):
        """JSONをParquetに変換"""
        df = pd.read_json(json_path)
        df.to_parquet(parquet_path, engine='pyarrow')
    
    def query_athena(self, sql, database):
        """Athenaでクエリを実行"""
        response = self.athena_client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={'Database': database},
            ResultConfiguration={'OutputLocation': f's3://{self.bucket}/athena-results/'}
        )
        return self._wait_for_query(response['QueryExecutionId'])
```

## データモデル

### ツールレスポンス形式

すべてのツールは統一されたレスポンス形式を返します。

```json
{
  "success": true,
  "result": {
    // ツール固有の結果
  },
  "metadata": {
    "execution_time": 1.23,
    "timestamp": "2026-01-08T18:00:00Z"
  }
}
```

### エラーレスポンス形式

```json
{
  "success": false,
  "error": {
    "code": "ESTAT_API_ERROR",
    "message": "e-Stat APIからエラーが返されました",
    "details": {
      "api_error": "LIMIT_EXCEEDED"
    }
  },
  "metadata": {
    "timestamp": "2026-01-08T18:00:00Z"
  }
}
```

### データセット情報

```json
{
  "id": "0003454502",
  "title": "産業別就業者数",
  "gov_org": "総務省",
  "survey_date": "202010",
  "relevance_score": 0.85,
  "size": 150000,
  "last_updated": "2021-06-30"
}
```

## 正確性プロパティ

プロパティは、システムが満たすべき普遍的な特性を定義します。これらは、すべての有効な実行において真であるべき形式的な記述です。

### プロパティ1: 検索結果の一貫性

*すべての*検索クエリに対して、同じクエリを2回実行した場合、同じデータセットIDのセットが返される（順序は異なる可能性がある）

**検証要件**: 要件1.1, 1.2

### プロパティ2: キーワード変換の可逆性

*すべての*元のクエリと承認されたキーワードマッピングに対して、apply_keyword_suggestionsを適用した後、元のクエリ構造が保持される

**検証要件**: 要件2.1, 2.2

### プロパティ3: データ完全性

*すべての*データセット取得操作に対して、取得されたレコード数は要求されたレコード数以下である

**検証要件**: 要件3.1, 3.2, 4.1, 4.4

### プロパティ4: チャンク結合の正確性

*すべての*チャンク取得操作に対して、結合されたデータセットのレコード数は、各チャンクのレコード数の合計と等しい

**検証要件**: 要件4.1, 4.4

### プロパティ5: フィルタリングの正確性

*すべての*フィルタ条件に対して、返されるすべてのレコードはフィルタ条件を満たす

**検証要件**: 要件5.1, 5.4

### プロパティ6: Parquet変換の型保持

*すべての*JSON→Parquet変換に対して、変換後のデータ型は元のデータ型と互換性がある

**検証要件**: 要件6.2

### プロパティ7: S3保存の冪等性

*すべての*S3保存操作に対して、同じデータを2回保存しても、最終的な状態は1回保存した場合と同じである

**検証要件**: 要件3.4, 4.5, 9.2

### プロパティ8: エラーメッセージの安全性

*すべての*エラーレスポンスに対して、APIキーやAWS認証情報などの機密情報が含まれていない

**検証要件**: 要件12.4

### プロパティ9: 後方互換性

*すべての*既存のツール呼び出しに対して、新しい実装は同じ形式のレスポンスを返す

**検証要件**: 要件14.1, 14.2, 14.3

### プロパティ10: タイムアウト制限なし

*すべての*e-Stat API呼び出しに対して、ECS Fargateはタイムアウトエラーを返さない（e-Stat API自体のタイムアウトを除く）

**検証要件**: 要件13.4

## エラーハンドリング

### エラー分類

1. **e-Stat APIエラー**
   - LIMIT_EXCEEDED: レート制限超過
   - INVALID_PARAMETER: 無効なパラメータ
   - NOT_FOUND: データセットが見つからない

2. **AWSサービスエラー**
   - S3_ACCESS_DENIED: S3アクセス拒否
   - ATHENA_QUERY_FAILED: Athenaクエリ失敗
   - NETWORK_ERROR: ネットワークエラー

3. **データ変換エラー**
   - PARSE_ERROR: JSONパースエラー
   - CONVERSION_ERROR: データ型変換エラー
   - ENCODING_ERROR: エンコーディングエラー

### リトライ戦略

```python
def retry_with_backoff(func, max_retries=3, base_delay=1.0):
    """指数バックオフでリトライ"""
    for attempt in range(max_retries):
        try:
            return func()
        except RetryableError as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)
```

### エラーログ

すべてのエラーはCloudWatch Logsに記録されます。

```python
logger.error(
    "e-Stat API error",
    extra={
        "error_code": "LIMIT_EXCEEDED",
        "dataset_id": dataset_id,
        "request_id": request_id
    }
)
```

## テスト戦略

### ユニットテスト

各ツール関数の個別テスト。

- キーワードサジェスト機能のテスト
- スコアリングアルゴリズムのテスト
- データ変換機能のテスト
- AWS統合のモックテスト

### プロパティベーステスト

正確性プロパティの検証。

- プロパティ1-10の各プロパティに対して100回以上のランダム入力でテスト
- 各テストは設計文書のプロパティ番号を参照

### 統合テスト

エンドツーエンドのワークフローテスト。

- 検索→取得→変換→分析の完全フロー
- エラーハンドリングとリトライの検証
- AWS統合の実環境テスト

### パフォーマンステスト

- 同時リクエスト処理能力
- 大規模データセット取得時間
- メモリ使用量

## デプロイメント

### 環境変数

```bash
ESTAT_APP_ID=<e-Stat APIキー>
S3_BUCKET=estat-data-lake
AWS_REGION=ap-northeast-1
PORT=8080
LOG_LEVEL=INFO
```

### Dockerイメージ

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY mcp_servers/ ./mcp_servers/
COPY server_http.py .
EXPOSE 8080
CMD ["python", "server_http.py"]
```

### ECSタスク定義

- CPU: 512 (0.5 vCPU)
- メモリ: 1024 MB
- タイムアウト: なし
- ヘルスチェック: /health

### 更新手順

1. コードを修正
2. Dockerイメージをビルド（amd64）
3. ECRにプッシュ
4. ECSサービスを更新（force-new-deployment）
5. ヘルスチェックで確認

## パフォーマンス最適化

### コネクションプーリング

```python
session = requests.Session()
adapter = HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=3
)
session.mount('https://', adapter)
```

### キャッシング

頻繁にアクセスされるデータセットメタデータをメモリキャッシュ。

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_dataset_metadata(dataset_id):
    """メタデータをキャッシュ"""
    return fetch_metadata_from_api(dataset_id)
```

### 並列処理

チャンク取得を並列化。

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=5) as executor:
    chunks = list(executor.map(fetch_chunk, chunk_ranges))
```

## セキュリティ

### 認証

- IAMロールベースの認証
- 環境変数からの認証情報取得
- APIキーの暗号化保存

### データ保護

- S3バケットの暗号化
- HTTPS通信の強制
- 機密情報のログ出力禁止

### アクセス制御

- S3バケットポリシー
- IAMポリシーの最小権限原則
- セキュリティグループの適切な設定
