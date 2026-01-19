# 設計書

## 概要

本設計書は、E-stat APIから取得したデータをApache Iceberg形式でAWS S3に格納するデータレイクの構築方法を定義します。既存のE-stat AWS統合システムを基盤として、段階的にIcebergデータレイクを構築します。

### 設計目標

1. **段階的構築**: 一部のデータセットから開始し、実現可能性を検証
2. **既存システム活用**: 既存のE-stat AWS MCPサーバーの機能を最大限活用
3. **スケーラビリティ**: 将来的な全データ取り込みに対応可能な設計
4. **クエリ最適化**: Athenaでの高速分析を実現するパーティション戦略

### 既存システムとの関係

既存のE-stat AWS統合システムは以下の機能を提供しています：

- **データ検索**: `search_estat_data` - 自然言語でのデータセット検索
- **データ取得**: `fetch_dataset_auto` - 10万件以下のデータセット取得
- **フィルタ取得**: `fetch_dataset_filtered` - カテゴリ指定での絞り込み取得
- **データ変換**: `transform_to_parquet` - JSON→Parquet変換
- **Iceberg投入**: `load_to_iceberg` - Icebergテーブルへのデータ投入
- **分析**: `analyze_with_athena` - Athenaでの統計分析

**重要な制約**:
- `fetch_large_dataset_complete`は現在、最初のチャンクのみ取得（MCPタイムアウト制限）
- 10万件以上のデータセットは`fetch_dataset_filtered`でフィルタリングが必要

本設計では、これらの既存機能と制約を考慮して、実現可能なデータレイク構築プロセスを定義します。

## アーキテクチャ

### Icebergデータレイクのメリット

データセットごとに個別のフォルダが作成されても、Icebergは以下のメリットを提供します：

#### 1. 統一されたクエリインターフェース
- 複数のデータセットを1つのテーブルに統合可能
- SQLで横断的なクエリが可能
- 例: 全データセットから特定地域のデータを一括取得

```sql
-- 複数のデータセットを統合したテーブルから検索
SELECT year, region_code, SUM(value) as total
FROM estat_db.population_data
WHERE region_code = '13000'  -- 東京都
GROUP BY year, region_code
ORDER BY year;
```

#### 2. ACIDトランザクション
- データ更新時の一貫性保証
- 読み取り中の書き込みが可能（スナップショット分離）
- ロールバック機能

#### 3. スキーマ進化
- 列の追加・削除が容易
- データ再書き込み不要
- 既存クエリへの影響最小化

#### 4. タイムトラベル
- 過去のデータ状態にアクセス可能
- データ変更履歴の追跡
- 誤った更新のロールバック

```sql
-- 過去のスナップショットにアクセス
SELECT * FROM estat_db.population_data
FOR SYSTEM_TIME AS OF '2024-01-01 00:00:00';
```

#### 5. パーティション管理の自動化
- パーティションの自動追加
- パーティションプルーニングによるクエリ最適化
- メタデータの効率的な管理

#### 6. データ品質の向上
- スキーマ検証
- データ型の強制
- 制約の適用

**結論**: データセットごとにフォルダが分かれていても、Icebergのメタデータレイヤーが統一的なビューを提供し、上記のメリットを享受できます。

### システム構成図

```
┌─────────────────────────────────────────────────────────────────┐
│                         E-stat API                               │
│                    (統計データソース)                             │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│              E-stat AWS MCP Server (既存)                        │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  データ取得・変換パイプライン                              │  │
│  │  - search_estat_data                                      │  │
│  │  - fetch_dataset_auto                                     │  │
│  │  - transform_to_parquet                                   │  │
│  │  - load_to_iceberg                                        │  │
│  └───────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                      AWS S3 Data Lake                            │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  raw/data/                                                │  │
│  │  └─ {dataset_id}_{timestamp}.json                        │  │
│  │                                                            │  │
│  │  processed/                                               │  │
│  │  └─ {dataset_id}_{timestamp}.parquet                     │  │
│  │                                                            │  │
│  │  iceberg-tables/                                          │  │
│  │  ├─ metadata/                                             │  │
│  │  │  └─ dataset_inventory (データセット一覧)               │  │
│  │  ├─ population/                                           │  │
│  │  ├─ economy/                                              │  │
│  │  └─ {domain}/                                             │  │
│  └───────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                   AWS Glue Data Catalog                          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Database: estat_db                                       │  │
│  │  ├─ dataset_inventory (メタデータテーブル)                │  │
│  │  ├─ population_data (人口統計)                            │  │
│  │  ├─ economy_data (経済統計)                               │  │
│  │  └─ {domain}_data                                         │  │
│  └───────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                      AWS Athena                                  │
│                   (クエリエンジン)                                │
└─────────────────────────────────────────────────────────────────┘
```

### レイヤー構成

#### 1. データ取得レイヤー
- **役割**: E-stat APIからのデータ取得
- **コンポーネント**: E-stat AWS MCPサーバー
- **出力**: S3 raw/data/ (JSON形式)

#### 2. データ変換レイヤー
- **役割**: JSON→Parquet変換、スキーマ正規化
- **コンポーネント**: transform_to_parquet
- **出力**: S3 processed/ (Parquet形式)

#### 3. データ格納レイヤー
- **役割**: Icebergテーブルへのデータ投入
- **コンポーネント**: load_to_iceberg
- **出力**: S3 iceberg-tables/ + Glue Data Catalog

#### 4. クエリレイヤー
- **役割**: SQLベースのデータ分析
- **コンポーネント**: AWS Athena
- **出力**: 分析結果

## コンポーネントと インターフェース

### 1. データセット選択マネージャー

#### 責務
- 取り込み対象データセットの管理
- データセット優先順位付け
- 取り込みステータス追跡

#### インターフェース

```python
class DatasetSelectionManager:
    """データセット選択と管理"""
    
    def __init__(self, config_path: str):
        """
        Args:
            config_path: 設定ファイルパス
        """
        self.config = self._load_config(config_path)
        self.inventory = []
    
    def add_dataset(self, dataset_id: str, priority: int = 5, 
                   domain: str = "generic") -> bool:
        """
        データセットを追加
        
        Args:
            dataset_id: データセットID
            priority: 優先度 (1-10, 10が最高)
            domain: データドメイン (population, economy, etc.)
        
        Returns:
            追加成功フラグ
        """
        pass
    
    def get_next_dataset(self) -> Optional[Dict[str, Any]]:
        """
        次に取り込むデータセットを取得
        
        Returns:
            データセット情報 or None
        """
        pass
    
    def update_status(self, dataset_id: str, status: str) -> bool:
        """
        データセットのステータスを更新
        
        Args:
            dataset_id: データセットID
            status: ステータス (pending, processing, completed, failed)
        
        Returns:
            更新成功フラグ
        """
        pass

#### 設定ファイル形式

```yaml
# dataset_config.yaml
datasets:
  - id: "0003458339"
    name: "人口推計"
    domain: "population"
    priority: 10
    status: "pending"
  
  - id: "0003410379"
    name: "経済センサス"
    domain: "economy"
    priority: 8
    status: "pending"
  
  - id: "0003109687"
    name: "家計調査"
    domain: "economy"
    priority: 7
    status: "pending"
```

### 2. データ取り込みオーケストレーター

#### 責務
- データ取り込みプロセスの統合管理
- エラーハンドリングとリトライ
- 進捗追跡とログ記録

#### インターフェース

```python
class DataIngestionOrchestrator:
    """データ取り込みオーケストレーター"""
    
    def __init__(self, mcp_client, selection_manager: DatasetSelectionManager):
        """
        Args:
            mcp_client: E-stat AWS MCPクライアント
            selection_manager: データセット選択マネージャー
        """
        self.mcp = mcp_client
        self.selection_manager = selection_manager
    
    async def ingest_dataset(self, dataset_id: str, domain: str) -> Dict[str, Any]:
        """
        データセットを取り込む
        
        Args:
            dataset_id: データセットID
            domain: データドメイン
        
        Returns:
            取り込み結果
        """
        # Step 1: データ取得
        fetch_result = await self.mcp.call_tool(
            "fetch_dataset_auto",
            {"dataset_id": dataset_id}
        )
        
        # Step 2: Parquet変換
        transform_result = await self.mcp.call_tool(
            "transform_to_parquet",
            {
                "s3_json_path": fetch_result["s3_location"],
                "data_type": domain
            }
        )
        
        # Step 3: Iceberg投入
        table_name = f"{domain}_data"
        load_result = await self.mcp.call_tool(
            "load_to_iceberg",
            {
                "table_name": table_name,
                "s3_parquet_path": transform_result["target_path"]
            }
        )
        
        return {
            "dataset_id": dataset_id,
            "domain": domain,
            "table_name": table_name,
            "records_loaded": load_result["records_loaded"],
            "status": "completed"
        }
    
    async def ingest_batch(self, batch_size: int = 5) -> List[Dict[str, Any]]:
        """
        バッチでデータセットを取り込む
        
        Args:
            batch_size: バッチサイズ
        
        Returns:
            取り込み結果のリスト
        """
        results = []
        for _ in range(batch_size):
            dataset = self.selection_manager.get_next_dataset()
            if not dataset:
                break
            
            try:
                result = await self.ingest_dataset(
                    dataset["id"],
                    dataset["domain"]
                )
                results.append(result)
                self.selection_manager.update_status(
                    dataset["id"],
                    "completed"
                )
            except Exception as e:
                results.append({
                    "dataset_id": dataset["id"],
                    "status": "failed",
                    "error": str(e)
                })
                self.selection_manager.update_status(
                    dataset["id"],
                    "failed"
                )
        
        return results
```

### 3. スキーママッピングエンジン

#### 責務
- E-statデータ構造の解析
- Icebergスキーマへのマッピング
- データ型推論と変換

#### スキーマ定義

```python
# ドメイン別スキーマ定義
DOMAIN_SCHEMAS = {
    "population": {
        "columns": [
            {"name": "stats_data_id", "type": "STRING", "description": "統計表ID"},
            {"name": "year", "type": "INT", "description": "年度"},
            {"name": "region_code", "type": "STRING", "description": "地域コード"},
            {"name": "region_name", "type": "STRING", "description": "地域名"},
            {"name": "category", "type": "STRING", "description": "カテゴリ"},
            {"name": "value", "type": "DOUBLE", "description": "値"},
            {"name": "unit", "type": "STRING", "description": "単位"},
            {"name": "updated_at", "type": "TIMESTAMP", "description": "更新日時"}
        ],
        "partition_by": ["year", "region_code"]
    },
    
    "economy": {
        "columns": [
            {"name": "stats_data_id", "type": "STRING", "description": "統計表ID"},
            {"name": "year", "type": "INT", "description": "年度"},
            {"name": "quarter", "type": "INT", "description": "四半期"},
            {"name": "region_code", "type": "STRING", "description": "地域コード"},
            {"name": "indicator", "type": "STRING", "description": "指標"},
            {"name": "value", "type": "DOUBLE", "description": "値"},
            {"name": "unit", "type": "STRING", "description": "単位"},
            {"name": "updated_at", "type": "TIMESTAMP", "description": "更新日時"}
        ],
        "partition_by": ["year", "region_code"]
    },
    
    "generic": {
        "columns": [
            {"name": "stats_data_id", "type": "STRING", "description": "統計表ID"},
            {"name": "year", "type": "INT", "description": "年度"},
            {"name": "region_code", "type": "STRING", "description": "地域コード"},
            {"name": "category", "type": "STRING", "description": "カテゴリ"},
            {"name": "value", "type": "DOUBLE", "description": "値"},
            {"name": "unit", "type": "STRING", "description": "単位"},
            {"name": "updated_at", "type": "TIMESTAMP", "description": "更新日時"}
        ],
        "partition_by": ["year"]
    }
}
```

#### インターフェース

```python
class SchemaMapper:
    """スキーママッピングエンジン"""
    
    def infer_domain(self, metadata: Dict[str, Any]) -> str:
        """
        メタデータからドメインを推論
        
        Args:
            metadata: E-statメタデータ
        
        Returns:
            ドメイン名 (population, economy, generic)
        """
        title = metadata.get("title", "").lower()
        
        if any(keyword in title for keyword in ["人口", "世帯", "出生", "死亡"]):
            return "population"
        elif any(keyword in title for keyword in ["経済", "GDP", "産業", "企業"]):
            return "economy"
        else:
            return "generic"
    
    def get_schema(self, domain: str) -> Dict[str, Any]:
        """
        ドメインのスキーマを取得
        
        Args:
            domain: ドメイン名
        
        Returns:
            スキーマ定義
        """
        return DOMAIN_SCHEMAS.get(domain, DOMAIN_SCHEMAS["generic"])
    
    def map_estat_to_iceberg(self, estat_record: Dict[str, Any], 
                            domain: str) -> Dict[str, Any]:
        """
        E-statレコードをIcebergスキーマにマッピング
        
        Args:
            estat_record: E-statレコード
            domain: ドメイン名
        
        Returns:
            Icebergレコード
        """
        schema = self.get_schema(domain)
        mapped_record = {}
        
        # ドメイン別のマッピングロジック
        if domain == "population":
            mapped_record = {
                "stats_data_id": estat_record.get("@id", ""),
                "year": int(estat_record.get("@time", "2020")),
                "region_code": estat_record.get("@area", ""),
                "region_name": "",  # メタデータから取得
                "category": estat_record.get("@cat01", ""),
                "value": float(estat_record.get("$", "0")),
                "unit": estat_record.get("@unit", ""),
                "updated_at": datetime.now()
            }
        
        return mapped_record
```

### 4. メタデータ管理システム

#### 責務
- データセットメタデータの保存
- データリネージ追跡
- データカタログ管理

#### Icebergテーブル: dataset_inventory

```sql
CREATE TABLE estat_db.dataset_inventory (
    dataset_id STRING,
    dataset_name STRING,
    domain STRING,
    organization STRING,
    survey_date DATE,
    open_date DATE,
    total_records BIGINT,
    ingestion_status STRING,
    ingestion_timestamp TIMESTAMP,
    table_name STRING,
    s3_raw_location STRING,
    s3_parquet_location STRING,
    s3_iceberg_location STRING,
    error_message STRING
)
LOCATION 's3://estat-data-lake/iceberg-tables/metadata/dataset_inventory/'
TBLPROPERTIES (
    'table_type'='ICEBERG',
    'format'='parquet'
)
```

#### インターフェース

```python
class MetadataManager:
    """メタデータ管理システム"""
    
    def __init__(self, athena_client):
        self.athena = athena_client
        self.database = "estat_db"
        self.table = "dataset_inventory"
    
    async def register_dataset(self, dataset_info: Dict[str, Any]) -> bool:
        """
        データセットをインベントリに登録
        
        Args:
            dataset_info: データセット情報
        
        Returns:
            登録成功フラグ
        """
        query = f"""
        INSERT INTO {self.database}.{self.table}
        VALUES (
            '{dataset_info["dataset_id"]}',
            '{dataset_info["dataset_name"]}',
            '{dataset_info["domain"]}',
            '{dataset_info["organization"]}',
            DATE '{dataset_info["survey_date"]}',
            DATE '{dataset_info["open_date"]}',
            {dataset_info["total_records"]},
            '{dataset_info["status"]}',
            TIMESTAMP '{dataset_info["timestamp"]}',
            '{dataset_info["table_name"]}',
            '{dataset_info["s3_raw_location"]}',
            '{dataset_info["s3_parquet_location"]}',
            '{dataset_info["s3_iceberg_location"]}',
            NULL
        )
        """
        
        result = await self.athena.execute_query(query)
        return result["success"]
    
    async def update_status(self, dataset_id: str, status: str, 
                          error_message: str = None) -> bool:
        """
        データセットのステータスを更新
        
        Args:
            dataset_id: データセットID
            status: ステータス
            error_message: エラーメッセージ
        
        Returns:
            更新成功フラグ
        """
        query = f"""
        UPDATE {self.database}.{self.table}
        SET ingestion_status = '{status}',
            error_message = '{error_message or ""}'
        WHERE dataset_id = '{dataset_id}'
        """
        
        result = await self.athena.execute_query(query)
        return result["success"]
    
    async def get_dataset_info(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """
        データセット情報を取得
        
        Args:
            dataset_id: データセットID
        
        Returns:
            データセット情報 or None
        """
        query = f"""
        SELECT * FROM {self.database}.{self.table}
        WHERE dataset_id = '{dataset_id}'
        """
        
        result = await self.athena.execute_query(query)
        if result["success"] and result["rows"]:
            return result["rows"][0]
        return None
```

## データモデル

### 1. データセットインベントリ

**テーブル名**: `dataset_inventory`

| カラム名 | 型 | 説明 |
|---------|-----|------|
| dataset_id | STRING | データセットID (主キー) |
| dataset_name | STRING | データセット名 |
| domain | STRING | ドメイン (population, economy, etc.) |
| organization | STRING | 提供組織 |
| survey_date | DATE | 調査日 |
| open_date | DATE | 公開日 |
| total_records | BIGINT | 総レコード数 |
| ingestion_status | STRING | 取り込みステータス |
| ingestion_timestamp | TIMESTAMP | 取り込み日時 |
| table_name | STRING | Icebergテーブル名 |
| s3_raw_location | STRING | 生データS3パス |
| s3_parquet_location | STRING | ParquetデータS3パス |
| s3_iceberg_location | STRING | IcebergテーブルS3パス |
| error_message | STRING | エラーメッセージ |

### 2. 人口統計データ

**テーブル名**: `population_data`

| カラム名 | 型 | 説明 | パーティション |
|---------|-----|------|--------------|
| stats_data_id | STRING | 統計表ID | - |
| year | INT | 年度 | ✓ |
| region_code | STRING | 地域コード | ✓ |
| region_name | STRING | 地域名 | - |
| category | STRING | カテゴリ | - |
| value | DOUBLE | 値 | - |
| unit | STRING | 単位 | - |
| updated_at | TIMESTAMP | 更新日時 | - |

**パーティション戦略**: `year`, `region_code`

### 3. 経済統計データ

**テーブル名**: `economy_data`

| カラム名 | 型 | 説明 | パーティション |
|---------|-----|------|--------------|
| stats_data_id | STRING | 統計表ID | - |
| year | INT | 年度 | ✓ |
| quarter | INT | 四半期 | - |
| region_code | STRING | 地域コード | ✓ |
| indicator | STRING | 指標 | - |
| value | DOUBLE | 値 | - |
| unit | STRING | 単位 | - |
| updated_at | TIMESTAMP | 更新日時 | - |

**パーティション戦略**: `year`, `region_code`

### 4. 汎用統計データ

**テーブル名**: `generic_data`

| カラム名 | 型 | 説明 | パーティション |
|---------|-----|------|--------------|
| stats_data_id | STRING | 統計表ID | - |
| year | INT | 年度 | ✓ |
| region_code | STRING | 地域コード | - |
| category | STRING | カテゴリ | - |
| value | DOUBLE | 値 | - |
| unit | STRING | 単位 | - |
| updated_at | TIMESTAMP | 更新日時 | - |

**パーティション戦略**: `year`

## 正確性プロパティ

プロパティとは、システムの全ての有効な実行において真であるべき特性や振る舞いの形式的な記述です。プロパティは、人間が読める仕様と機械で検証可能な正確性保証の橋渡しとなります。


### プロパティ反映

prework分析から、以下の冗長性を確認しました：

**冗長性の排除**:
- 要件1.5と要件11.4は同じパーティション設定を検証 → 要件1.5のプロパティに統合
- 要件5.1と要件5.2は両方ともテーブル作成時のスキーマとパーティション設定を検証 → 1つのプロパティに統合
- 要件7.1と要件7.2は両方ともテーブルメタデータの保存を検証 → 1つのプロパティに統合

### 正確性プロパティ

#### プロパティ1: S3バケット構造の一貫性
*任意の*Icebergテーブルに対して、テーブルを作成した後、S3上の`iceberg-tables/{domain}/{table_name}/`プレフィックスに格納されていなければならない
**検証: 要件 1.1**

#### プロパティ2: Glue Catalogへの登録
*任意の*Icebergテーブルに対して、テーブルを作成した後、AWS Glue Data Catalogに登録され、`estat_db`データベースから取得可能でなければならない
**検証: 要件 1.2**

#### プロパティ3: スキーマのラウンドトリップ
*任意の*テーブルスキーマに対して、テーブルを作成し、Glue Catalogから取得したスキーマは、元のスキーマと等価でなければならない
**検証: 要件 1.3**

#### プロパティ4: パーティション戦略の適用
*任意の*ドメイン（population, economy, generic）に対して、そのドメインのテーブルを作成した後、DOMAIN_SCHEMASで定義されたパーティションキーが設定されていなければならない
**検証: 要件 1.5, 11.4**

#### プロパティ5: 設定のラウンドトリップ
*任意の*データセット設定に対して、設定を保存し、読み込んだ設定は元の設定と等価でなければならない
**検証: 要件 2.1**

#### プロパティ6: ステータス管理の一貫性
*任意の*データセットIDとステータスに対して、ステータスを更新した後、取得したステータスは更新したステータスと一致しなければならない
**検証: 要件 2.3**

#### プロパティ7: メタデータのラウンドトリップ
*任意の*データセットIDに対して、メタデータを取得・保存し、保存されたメタデータから読み込んだ内容は、元のメタデータと等価でなければならない
**検証: 要件 2.4**

#### プロパティ8: データセットフィルタリング
*任意の*データセットリストと指定されたデータセットIDのサブセットに対して、取り込みパイプラインを実行した後、指定されたデータセットのみが処理されていなければならない
**検証: 要件 3.1**

#### プロパティ9: データ完全性
*任意の*データセットIDに対して、E-stat APIから取得したレコード数と、システムが取り込んだレコード数は一致しなければならない
**検証: 要件 3.2**

#### プロパティ10: JSON解析の正確性
*任意の*E-stat JSONレスポンスに対して、解析後の統計値は、元のJSONの`DATA_INF.VALUE`配列の全要素を含んでいなければならない
**検証: 要件 4.1**

#### プロパティ11: カテゴリコード変換
*任意の*E-statカテゴリコードに対して、変換後の列名は、キーワード辞書で定義された日本語名と一致しなければならない
**検証: 要件 4.2**

#### プロパティ12: データ型推論の正確性
*任意の*データ列に対して、推論されたデータ型は、列の全ての値が変換可能な型でなければならない
**検証: 要件 4.3**

#### プロパティ13: スキーマ正規化
*任意の*E-statデータから生成されたスキーマに対して、次元列（region_code, year, category等）とメジャー列（value, unit）が分離されていなければならない
**検証: 要件 4.4**

#### プロパティ14: 命名規則の一貫性
*任意の*2つのデータセットが共通の次元（例: region_code）を持つ場合、両方のスキーマで同じ列名が使用されていなければならない
**検証: 要件 4.5**

#### プロパティ15: テーブル作成とスキーマ設定
*任意の*データセットとドメインに対して、Icebergテーブルを作成した後、テーブルは正しいスキーマとパーティション仕様を持っていなければならない
**検証: 要件 5.1, 5.2**

#### プロパティ16: テーブルプロパティの設定
*任意の*Icebergテーブルに対して、テーブル作成後、`table_type='ICEBERG'`および`format='parquet'`プロパティが設定されていなければならない
**検証: 要件 5.3**

#### プロパティ17: Parquetファイル形式
*任意の*データ書き込み操作に対して、S3に保存されたファイルはParquet形式でなければならない
**検証: 要件 5.5**

#### プロパティ18: 必須列の存在検証
*任意の*データセットとそのメタデータに対して、取り込まれたデータは、メタデータで定義された全ての必須列を含んでいなければならない
**検証: 要件 6.1**

#### プロパティ19: 重複レコードの検出
*任意の*データセットに対して、同じ次元の組み合わせ（year, region_code, category）を持つレコードが複数存在する場合、システムは重複として検出しなければならない
**検証: 要件 6.4**

#### プロパティ20: テーブルメタデータの保存
*任意の*E-statメタデータに対して、Icebergテーブルを作成した後、テーブルプロパティにメタデータ（カテゴリ、次元、単位、説明、ソースURL、更新タイムスタンプ）が含まれていなければならない
**検証: 要件 7.1, 7.2**

#### プロパティ21: データセットIDとテーブル名のマッピング
*任意の*データセットIDとテーブル名に対して、メタデータテーブルに保存し、データセットIDで検索した結果は、保存したテーブル名と一致しなければならない
**検証: 要件 7.3**

#### プロパティ22: カテゴリコードの保持
*任意の*E-statデータに対して、変換後のデータは、元のカテゴリコードと変換後の日本語名の両方を含んでいなければならない
**検証: 要件 7.4**

#### プロパティ23: データリネージ情報の保存
*任意の*取り込み操作に対して、取り込まれたデータは、取り込みタイムスタンプとソースAPIバージョンを含むリネージ情報を持っていなければならない
**検証: 要件 7.5**

#### プロパティ24: 更新データセットの識別
*任意の*データセットリストと最終取り込み日時に対して、E-statの更新日時が最終取り込み日時より新しいデータセットのみが、更新対象として識別されなければならない
**検証: 要件 9.1**

#### プロパティ25: 差分取得
*任意の*データセットの更新前後のデータに対して、差分取得で取得されるレコードは、新規または変更されたレコードのみでなければならない
**検証: 要件 9.2**

#### プロパティ26: 取り込み操作のログ記録
*任意の*取り込み操作に対して、ログにはタイムスタンプ、データセットID、レコード数が記録されていなければならない
**検証: 要件 10.1**

#### プロパティ27: メトリクスの追跡
*任意の*取り込み操作に対して、取り込みスループット（レコード数/秒）、ストレージ使用量（バイト）のメトリクスが記録されていなければならない
**検証: 要件 10.3**

#### プロパティ28: ファイル圧縮
*任意の*Parquetファイルに対して、ファイルはSnappyまたはZSTDコーデックで圧縮されていなければならない
**検証: 要件 11.2**

## エラーハンドリング

### エラー分類

#### 1. データ取得エラー
- **E-stat APIタイムアウト**: リトライ（最大3回、指数バックオフ）
- **E-stat APIレート制限**: 待機後リトライ
- **データセット未存在**: エラーログ記録、次のデータセットへ

#### 2. データ変換エラー
- **JSON解析エラー**: エラーログ記録、生データをS3に保存
- **スキーマ推論エラー**: デフォルトスキーマ（generic）を使用
- **データ型変換エラー**: 問題レコードをスキップ、警告ログ記録

#### 3. データ投入エラー
- **Icebergテーブル作成エラー**: エラーログ記録、ロールバック
- **データ投入エラー**: トランザクションロールバック、エラーログ記録
- **スキーマ不一致エラー**: スキーマ進化を試行、失敗時はエラーログ

#### 4. システムエラー
- **S3アクセスエラー**: IAMロール確認、リトライ
- **Athenaクエリエラー**: クエリ構文確認、エラーログ記録
- **Glue Catalogエラー**: 権限確認、リトライ

### エラーハンドリング戦略

```python
class ErrorHandler:
    """エラーハンドリング戦略"""
    
    def __init__(self, logger, metrics_collector):
        self.logger = logger
        self.metrics = metrics_collector
    
    async def handle_ingestion_error(
        self,
        error: Exception,
        dataset_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        取り込みエラーを処理
        
        Args:
            error: 発生したエラー
            dataset_id: データセットID
            context: エラーコンテキスト
        
        Returns:
            エラー処理結果
        """
        # エラー分類
        error_type = self._classify_error(error)
        
        # ログ記録
        self.logger.error(
            f"Ingestion error for dataset {dataset_id}",
            extra={
                "error_type": error_type,
                "error_message": str(error),
                "context": context,
                "stack_trace": traceback.format_exc()
            }
        )
        
        # メトリクス記録
        self.metrics.increment("ingestion_errors", {
            "error_type": error_type,
            "dataset_id": dataset_id
        })
        
        # リトライ判定
        if self._is_retryable(error_type):
            return {
                "action": "retry",
                "retry_after": self._get_retry_delay(error_type),
                "max_retries": 3
            }
        else:
            return {
                "action": "skip",
                "reason": f"Non-retryable error: {error_type}"
            }
    
    def _classify_error(self, error: Exception) -> str:
        """エラーを分類"""
        if isinstance(error, requests.exceptions.Timeout):
            return "api_timeout"
        elif isinstance(error, requests.exceptions.HTTPError):
            if error.response.status_code == 429:
                return "rate_limit"
            elif error.response.status_code == 404:
                return "not_found"
        elif isinstance(error, json.JSONDecodeError):
            return "json_parse_error"
        elif isinstance(error, ValueError):
            return "data_validation_error"
        else:
            return "unknown_error"
    
    def _is_retryable(self, error_type: str) -> bool:
        """リトライ可能なエラーか判定"""
        retryable_errors = [
            "api_timeout",
            "rate_limit",
            "s3_access_error",
            "athena_query_error"
        ]
        return error_type in retryable_errors
    
    def _get_retry_delay(self, error_type: str) -> int:
        """リトライ遅延時間を取得（秒）"""
        delays = {
            "api_timeout": 5,
            "rate_limit": 60,
            "s3_access_error": 10,
            "athena_query_error": 15
        }
        return delays.get(error_type, 30)
```

## テスト戦略

### デュアルテストアプローチ

本システムでは、単体テストとプロパティベーステストを組み合わせた包括的なテスト戦略を採用します。

#### 単体テスト
- **目的**: 特定の例、エッジケース、エラー条件の検証
- **対象**:
  - 大規模データセットのチャンク取得（要件3.3）
  - エラー発生時のログ記録（要件3.4）
  - 取り込み中断後の再開（要件3.5）
  - スキーマ進化（要件5.4）
  - null値の警告ログ（要件6.2）
  - 範囲外の値の検証（要件6.3）
  - 不正レコードの隔離（要件6.5）
  - エラー時の詳細ログ（要件10.2）
  - タイムトラベルクエリ（要件8.3）
  - テーブル間JOIN（要件8.4）
  - スナップショット管理（要件9.4）
  - 通知送信（要件10.5）
  - S3ライフサイクルポリシー（要件11.1）
  - ファイル圧縮（要件11.3）
  - スナップショット期限切れ（要件11.5）

#### プロパティベーステスト
- **目的**: 全入力に対する普遍的なプロパティの検証
- **対象**: 上記の正確性プロパティ1-28
- **設定**:
  - 最小100回の反復実行
  - 各テストは設計書のプロパティを参照
  - タグ形式: `Feature: estat-datalake-construction, Property {番号}: {プロパティテキスト}`

### テストライブラリ

**Python**: Hypothesis
```python
from hypothesis import given, strategies as st
import pytest

@given(
    dataset_id=st.text(min_size=10, max_size=10, alphabet=st.characters(whitelist_categories=('Nd',))),
    domain=st.sampled_from(['population', 'economy', 'generic'])
)
def test_property_15_table_creation_and_schema(dataset_id, domain):
    """
    Feature: estat-datalake-construction, Property 15: テーブル作成とスキーマ設定
    任意のデータセットとドメインに対して、Icebergテーブルを作成した後、
    テーブルは正しいスキーマとパーティション仕様を持っていなければならない
    """
    # テーブル作成
    table_name = f"{domain}_data"
    create_table(dataset_id, domain, table_name)
    
    # スキーマ取得
    actual_schema = get_table_schema(table_name)
    expected_schema = DOMAIN_SCHEMAS[domain]
    
    # 検証
    assert actual_schema["columns"] == expected_schema["columns"]
    assert actual_schema["partition_by"] == expected_schema["partition_by"]
```

### テスト実行

```bash
# 全テスト実行
pytest tests/ -v

# プロパティベーステストのみ
pytest tests/ -v -m property

# 単体テストのみ
pytest tests/ -v -m unit

# 特定のプロパティテスト
pytest tests/ -v -k "property_15"
```


## 実装フェーズ

### 前提条件: 大規模データセットの取り扱い

#### 現状の制約
- `fetch_large_dataset_complete`はMCPタイムアウト制限により、最初のチャンク（10万件）のみ取得
- 10万件以上のデータセットは完全取得が困難

#### 対応戦略

**戦略1: フィルタリングによる分割取得（全データ取得可能）**

`fetch_dataset_filtered`は、指定したフィルタ条件に一致するデータを取得します。全データを取得するには、全てのフィルタ値を網羅的に指定します。

```python
# 例: 人口統計データセット（47都道府県 × 10年分 = 470回の取得）
async def fetch_complete_dataset(dataset_id: str, metadata: Dict):
    """
    フィルタを使って全データを分割取得
    
    Args:
        dataset_id: データセットID
        metadata: メタデータ（カテゴリ情報を含む）
    
    Returns:
        全データの統合結果
    """
    all_data = []
    
    # メタデータから全ての地域コードを取得
    regions = metadata['categories']['area']['values']  # ['01000', '02000', ...]
    years = metadata['categories']['time']['values']    # ['2015', '2016', ...]
    
    # 地域 × 年度の全組み合わせで取得
    for region in regions:
        for year in years:
            result = await mcp.call_tool(
                "fetch_dataset_filtered",
                {
                    "dataset_id": dataset_id,
                    "filters": {
                        "area": region,
                        "time": year
                    }
                }
            )
            
            if result["success"]:
                all_data.extend(result["data"])
                print(f"取得完了: {region} / {year} - {len(result['data'])}件")
    
    return all_data
```

**メリット**:
- 全データを確実に取得可能
- 各リクエストは10万件以下なのでタイムアウトなし
- 並列実行で高速化可能

**デメリット**:
- リクエスト数が多い（例: 47都道府県 × 10年 = 470回）
- 取得に時間がかかる（1リクエスト3秒として、約24分）

**戦略2: 並列取得による高速化**

```python
import asyncio

async def fetch_complete_dataset_parallel(dataset_id: str, metadata: Dict):
    """
    並列実行で全データを高速取得
    
    Args:
        dataset_id: データセットID
        metadata: メタデータ
    
    Returns:
        全データの統合結果
    """
    regions = metadata['categories']['area']['values']
    years = metadata['categories']['time']['values']
    
    # 全組み合わせのタスクを作成
    tasks = []
    for region in regions:
        for year in years:
            task = mcp.call_tool(
                "fetch_dataset_filtered",
                {
                    "dataset_id": dataset_id,
                    "filters": {"area": region, "time": year}
                }
            )
            tasks.append(task)
    
    # 並列実行（最大10並列）
    results = []
    for i in range(0, len(tasks), 10):
        batch = tasks[i:i+10]
        batch_results = await asyncio.gather(*batch)
        results.extend(batch_results)
    
    # データ統合
    all_data = []
    for result in results:
        if result["success"]:
            all_data.extend(result["data"])
    
    return all_data
```

**メリット**:
- 全データを確実に取得可能
- 並列実行で大幅に高速化（10並列で約2.4分）

**戦略3: MCPツールの拡張（長期的な解決策）**

`fetch_large_dataset_complete`を改善して、完全な分割取得を実装：

```python
# 改善版のツール実装（mcp_servers/estat_aws/server.py）
async def fetch_large_dataset_complete_v2(
    self,
    dataset_id: str,
    max_records: int = 1000000,
    chunk_size: int = 100000
) -> Dict[str, Any]:
    """
    大規模データセットの完全取得（改善版）
    
    全チャンクを取得し、S3に保存
    """
    # 総レコード数を確認
    total_records = await self._get_total_records(dataset_id)
    total_chunks = (total_records + chunk_size - 1) // chunk_size
    
    all_chunks = []
    for chunk_num in range(total_chunks):
        start_position = chunk_num * chunk_size + 1
        
        # チャンク取得
        chunk_data = await self._fetch_chunk(
            dataset_id,
            start_position,
            chunk_size
        )
        
        # S3に保存
        s3_key = f"raw/data/{dataset_id}_chunk_{chunk_num:03d}.json"
        await self._save_to_s3(chunk_data, s3_key)
        
        all_chunks.append(s3_key)
    
    return {
        "success": True,
        "total_chunks": total_chunks,
        "total_records": total_records,
        "s3_locations": all_chunks
    }
```

**推奨アプローチ**:
1. **短期（フェーズ1-2）**: 戦略1・2で全データ取得を実現
2. **中期（フェーズ3-4）**: 戦略3でツール拡張を検討
3. **長期**: 自動化とスケジュール実行

**結論**: `fetch_dataset_filtered`を使った分割取得により、大規模データセットでも全データ取得が可能です。

### フェーズ1: 基盤構築（Week 1-2）

#### 目標
- データセット選択マネージャーの実装
- 設定ファイル管理
- メタデータテーブルの作成

#### 成果物
- `DatasetSelectionManager`クラス
- `dataset_config.yaml`設定ファイル
- `dataset_inventory` Icebergテーブル

#### 検証
- プロパティ5: 設定のラウンドトリップ
- プロパティ6: ステータス管理の一貫性
- プロパティ21: データセットIDとテーブル名のマッピング

### フェーズ2: データ取り込みパイプライン（Week 3-4）

#### 目標
- データ取り込みオーケストレーターの実装
- 既存MCPツールの統合
- エラーハンドリングの実装

#### 成果物
- `DataIngestionOrchestrator`クラス
- `ErrorHandler`クラス
- バッチ取り込みスクリプト

#### 検証
- プロパティ8: データセットフィルタリング
- プロパティ9: データ完全性
- プロパティ10: JSON解析の正確性

### フェーズ3: スキーママッピング（Week 5-6）

#### 目標
- スキーママッピングエンジンの実装
- ドメイン別スキーマ定義
- データ型推論ロジック

#### 成果物
- `SchemaMapper`クラス
- `DOMAIN_SCHEMAS`定義
- データ変換ロジック

#### 検証
- プロパティ11: カテゴリコード変換
- プロパティ12: データ型推論の正確性
- プロパティ13: スキーマ正規化
- プロパティ14: 命名規則の一貫性

### フェーズ4: Icebergテーブル管理（Week 7-8）

#### 目標
- Icebergテーブル作成ロジックの実装
- パーティション戦略の適用
- メタデータ管理の実装

#### 成果物
- テーブル作成スクリプト
- パーティション設定
- メタデータ管理システム

#### 検証
- プロパティ1: S3バケット構造の一貫性
- プロパティ2: Glue Catalogへの登録
- プロパティ3: スキーマのラウンドトリップ
- プロパティ4: パーティション戦略の適用
- プロパティ15: テーブル作成とスキーマ設定
- プロパティ16: テーブルプロパティの設定
- プロパティ17: Parquetファイル形式
- プロパティ20: テーブルメタデータの保存

### フェーズ5: データ品質とモニタリング（Week 9-10）

#### 目標
- データ品質検証の実装
- ログ記録とメトリクス収集
- モニタリングダッシュボード

#### 成果物
- データ検証ロジック
- ログ記録システム
- メトリクス収集システム

#### 検証
- プロパティ18: 必須列の存在検証
- プロパティ19: 重複レコードの検出
- プロパティ22: カテゴリコードの保持
- プロパティ23: データリネージ情報の保存
- プロパティ26: 取り込み操作のログ記録
- プロパティ27: メトリクスの追跡

### フェーズ6: 増分更新とコスト最適化（Week 11-12）

#### 目標
- 増分更新ロジックの実装
- S3ライフサイクルポリシーの設定
- ファイル圧縮の実装

#### 成果物
- 増分更新スクリプト
- S3ライフサイクルポリシー
- ファイル圧縮ロジック

#### 検証
- プロパティ24: 更新データセットの識別
- プロパティ25: 差分取得
- プロパティ28: ファイル圧縮

## デプロイメント

### 環境構成

#### 開発環境
- **目的**: 機能開発とテスト
- **データ**: サンプルデータセット（3-5個）
- **リソース**: 最小限のAWSリソース

#### ステージング環境
- **目的**: 統合テストと検証
- **データ**: 実データの一部（10-20個のデータセット）
- **リソース**: 本番相当のAWSリソース

#### 本番環境
- **目的**: 実運用
- **データ**: 全データセット
- **リソース**: スケーラブルなAWSリソース

### デプロイメント手順

#### 1. AWSリソースのプロビジョニング

```bash
# S3バケット作成
aws s3 mb s3://estat-data-lake --region ap-northeast-1

# Glueデータベース作成
aws glue create-database \
  --database-input '{"Name": "estat_db", "Description": "E-stat data lake"}'

# Athenaワークグループ作成
aws athena create-work-group \
  --name estat-mcp-workgroup \
  --configuration "ResultConfigurationUpdates={OutputLocation=s3://estat-data-lake/athena-results/}"
```

#### 2. IAMロールとポリシーの設定

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
        "glue:GetDatabase",
        "glue:GetTable",
        "glue:CreateTable",
        "glue:UpdateTable"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults"
      ],
      "Resource": "*"
    }
  ]
}
```

#### 3. 初期データセットの設定

```yaml
# dataset_config.yaml
datasets:
  # フェーズ1: 小規模データセット（検証用）
  - id: "0003458339"
    name: "人口推計（令和2年国勢調査基準）"
    domain: "population"
    priority: 10
    status: "pending"
  
  - id: "0003109687"
    name: "家計調査"
    domain: "economy"
    priority: 9
    status: "pending"
  
  - id: "0003348423"
    name: "労働力調査"
    domain: "economy"
    priority: 8
    status: "pending"
```

#### 4. データレイク初期化

```python
# initialize_datalake.py
import asyncio
from data_ingestion_orchestrator import DataIngestionOrchestrator
from dataset_selection_manager import DatasetSelectionManager
from mcp_client import MCPClient

async def main():
    # MCPクライアント初期化
    mcp_client = MCPClient(url="https://estat-mcp.snowmole.co.jp/mcp")
    
    # データセット選択マネージャー初期化
    selection_manager = DatasetSelectionManager("dataset_config.yaml")
    
    # オーケストレーター初期化
    orchestrator = DataIngestionOrchestrator(mcp_client, selection_manager)
    
    # メタデータテーブル作成
    await orchestrator.create_metadata_table()
    
    # 初期データセット取り込み
    results = await orchestrator.ingest_batch(batch_size=3)
    
    # 結果表示
    for result in results:
        print(f"Dataset {result['dataset_id']}: {result['status']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 運用手順

#### 日次運用

```bash
# 1. 新規データセットの確認
python check_new_datasets.py

# 2. 更新されたデータセットの取り込み
python ingest_updated_datasets.py

# 3. データ品質チェック
python validate_data_quality.py

# 4. メトリクスレポート生成
python generate_metrics_report.py
```

#### 週次運用

```bash
# 1. ファイル圧縮
python compact_small_files.py

# 2. 古いスナップショットの削除
python expire_old_snapshots.py --retention-days 30

# 3. ストレージ使用量レポート
python generate_storage_report.py
```

#### 月次運用

```bash
# 1. データレイク統計レポート
python generate_datalake_stats.py

# 2. コスト分析
python analyze_costs.py

# 3. パフォーマンス最適化
python optimize_partitions.py
```

## パフォーマンス最適化

### クエリ最適化

#### 1. パーティションプルーニング

```sql
-- 悪い例: 全データスキャン
SELECT * FROM estat_db.population_data
WHERE region_code = '13000';

-- 良い例: パーティションプルーニング
SELECT * FROM estat_db.population_data
WHERE year = 2020 AND region_code = '13000';
```

#### 2. 列選択の最適化

```sql
-- 悪い例: 全列取得
SELECT * FROM estat_db.population_data;

-- 良い例: 必要な列のみ取得
SELECT year, region_code, value 
FROM estat_db.population_data;
```

#### 3. 集計の最適化

```sql
-- 悪い例: サブクエリで集計
SELECT region_code, 
       (SELECT AVG(value) FROM estat_db.population_data p2 
        WHERE p2.region_code = p1.region_code) as avg_value
FROM estat_db.population_data p1
GROUP BY region_code;

-- 良い例: 直接集計
SELECT region_code, AVG(value) as avg_value
FROM estat_db.population_data
GROUP BY region_code;
```

### ストレージ最適化

#### 1. ファイルサイズの最適化

```python
# 小さなファイルを統合
def compact_small_files(table_name: str, min_file_size_mb: int = 100):
    """
    小さなファイルを統合して大きなファイルにする
    
    Args:
        table_name: テーブル名
        min_file_size_mb: 最小ファイルサイズ（MB）
    """
    query = f"""
    OPTIMIZE {table_name}
    REWRITE DATA USING BIN_PACK
    WHERE file_size_in_bytes < {min_file_size_mb * 1024 * 1024}
    """
    
    execute_athena_query(query)
```

#### 2. 圧縮率の向上

```python
# Parquet書き込み時の圧縮設定
import pyarrow.parquet as pq

pq.write_table(
    table,
    output_path,
    compression='ZSTD',  # 高圧縮率
    compression_level=3,  # 圧縮レベル
    use_dictionary=True,  # 辞書圧縮
    write_statistics=True  # 統計情報
)
```

#### 3. パーティション最適化

```python
# パーティション統計の確認
def analyze_partition_distribution(table_name: str):
    """
    パーティションのデータ分布を分析
    
    Args:
        table_name: テーブル名
    """
    query = f"""
    SELECT 
        year,
        region_code,
        COUNT(*) as record_count,
        SUM(file_size_in_bytes) / 1024 / 1024 as size_mb
    FROM {table_name}
    GROUP BY year, region_code
    ORDER BY size_mb DESC
    """
    
    results = execute_athena_query(query)
    
    # 不均衡なパーティションを特定
    for row in results:
        if row['size_mb'] > 1000:  # 1GB以上
            print(f"Large partition: {row['year']}/{row['region_code']} - {row['size_mb']}MB")
```

## セキュリティ

### データアクセス制御

#### 1. IAMポリシーによる制御

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadOnlyAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:role/DataAnalystRole"
      },
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::estat-data-lake",
        "arn:aws:s3:::estat-data-lake/*"
      ]
    },
    {
      "Sid": "WriteAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:role/DataEngineerRole"
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::estat-data-lake",
        "arn:aws:s3:::estat-data-lake/*"
      ]
    }
  ]
}
```

#### 2. Glue Data Catalogのアクセス制御

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase",
        "glue:GetTable",
        "glue:GetPartitions"
      ],
      "Resource": [
        "arn:aws:glue:ap-northeast-1:123456789012:catalog",
        "arn:aws:glue:ap-northeast-1:123456789012:database/estat_db",
        "arn:aws:glue:ap-northeast-1:123456789012:table/estat_db/*"
      ]
    }
  ]
}
```

### データ暗号化

#### 1. S3暗号化

```bash
# バケットのデフォルト暗号化を有効化
aws s3api put-bucket-encryption \
  --bucket estat-data-lake \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

#### 2. Athenaクエリ結果の暗号化

```bash
# ワークグループの暗号化設定
aws athena update-work-group \
  --work-group estat-mcp-workgroup \
  --configuration-updates "ResultConfigurationUpdates={EncryptionConfiguration={EncryptionOption=SSE_S3}}"
```

### 監査ログ

#### 1. CloudTrailの有効化

```bash
# CloudTrailトレイルの作成
aws cloudtrail create-trail \
  --name estat-datalake-trail \
  --s3-bucket-name estat-audit-logs

# ロギングの開始
aws cloudtrail start-logging \
  --name estat-datalake-trail
```

#### 2. S3アクセスログ

```bash
# S3アクセスログの有効化
aws s3api put-bucket-logging \
  --bucket estat-data-lake \
  --bucket-logging-status '{
    "LoggingEnabled": {
      "TargetBucket": "estat-access-logs",
      "TargetPrefix": "datalake-access/"
    }
  }'
```

## トラブルシューティング

### 一般的な問題と解決策

#### 1. データ取り込みの失敗

**症状**: データセットの取り込みが失敗する

**原因と対処**:
- E-stat APIタイムアウト → リトライ設定の確認、タイムアウト時間の延長
- データサイズ超過 → `fetch_dataset_filtered`でフィルタリング
- スキーマ不一致 → メタデータの再取得、スキーマ定義の確認

#### 2. Athenaクエリの遅延

**症状**: クエリ実行に時間がかかる

**原因と対処**:
- パーティションプルーニング未使用 → WHERE句にパーティションキーを追加
- 大量のデータスキャン → 列選択の最適化、集計の見直し
- 小さなファイルが多数 → ファイル圧縮の実行

#### 3. S3ストレージコストの増加

**症状**: ストレージコストが予想以上に増加

**原因と対処**:
- 古いスナップショットの蓄積 → スナップショット期限切れの実行
- 圧縮率の低下 → 圧縮設定の見直し、ZSTDコーデックの使用
- 重複データ → 重複レコードの検出と削除

#### 4. Glue Catalogの同期エラー

**症状**: テーブルがGlue Catalogに表示されない

**原因と対処**:
- IAM権限不足 → ロールのポリシー確認
- テーブル作成の失敗 → Athenaクエリログの確認
- カタログの不整合 → `MSCK REPAIR TABLE`の実行

## 今後の拡張計画

### 短期（3-6ヶ月）

1. **データセット自動検出**
   - E-stat APIから新規データセットを自動検出
   - 優先度の自動判定

2. **データ品質ダッシュボード**
   - リアルタイムのデータ品質メトリクス
   - 異常検知アラート

3. **増分更新の自動化**
   - スケジュール実行
   - 変更検出の最適化

### 中期（6-12ヶ月）

1. **全データセットの取り込み**
   - E-stat APIの全データセット対応
   - ドメイン分類の拡張

2. **高度な分析機能**
   - 時系列分析
   - 地域間比較
   - トレンド予測

3. **データカタログの充実**
   - データリネージの可視化
   - データ品質スコア
   - 利用統計

### 長期（12ヶ月以降）

1. **AIエージェント統合**
   - 自然言語クエリ
   - データ推奨
   - 自動レポート生成

2. **マルチソース統合**
   - 他の統計データソースとの統合
   - データ連携の自動化

3. **リアルタイムデータ対応**
   - ストリーミングデータの取り込み
   - リアルタイム分析

## まとめ

本設計書では、E-stat APIから取得したデータをApache Iceberg形式でAWS S3に格納するデータレイクの構築方法を定義しました。

### 主要な設計決定

1. **既存システムの活用**: E-stat AWS MCPサーバーの機能を最大限活用
2. **段階的構築**: 一部のデータセットから開始し、実現可能性を検証
3. **ドメイン別スキーマ**: population, economy, genericの3つのドメインで分類
4. **パーティション戦略**: year, region_codeによる効率的なクエリ最適化
5. **プロパティベーステスト**: 28個の正確性プロパティによる包括的な検証

### 期待される効果

1. **データアクセスの向上**: SQLベースの柔軟なデータ分析
2. **コスト削減**: Parquet圧縮とパーティショニングによるストレージ最適化
3. **データ品質の向上**: 自動検証とエラーハンドリング
4. **スケーラビリティ**: 将来的な全データ取り込みに対応可能な設計
5. **保守性**: モジュール化された設計と包括的なテスト

### 次のステップ

1. 要件定義書と設計書のレビュー
2. タスクリストの作成
3. フェーズ1の実装開始
