# Athenaツール使用例

修正後の`load_to_iceberg`と`analyze_with_athena`ツールの使用方法を説明します。

## 前提条件

### 1. AWS認証情報の設定

```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=ap-northeast-1
export S3_BUCKET=estat-data-lake
```

### 2. S3バケットの準備

- バケット`estat-data-lake`が存在すること
- バケットに対する読み書き権限があること
- Athenaの結果を保存するための`athena-results/`ディレクトリが作成可能であること

### 3. IAMポリシーの確認

以下の権限が必要です：

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
        "glue:CreateDatabase",
        "glue:GetTable",
        "glue:CreateTable"
      ],
      "Resource": "*"
    }
  ]
}
```

## 使用例

### 1. データセットの取得とParquet変換

まず、e-StatからデータセットをCSV形式で取得し、Parquet形式に変換します。

```python
# MCPツールを使用
# ステップ1: データセットを検索
result = await search_estat_data(
    query="北海道 人口",
    max_results=5
)

# ステップ2: データセットを取得してCSVとして保存
dataset_id = result['results'][0]['dataset_id']
csv_result = await save_dataset_as_csv(
    dataset_id=dataset_id,
    output_filename=f"{dataset_id}.csv"
)

# ステップ3: CSVをParquetに変換
parquet_result = await transform_to_parquet(
    s3_json_path=csv_result['s3_csv_path'],
    data_type="estat_data"
)
```

### 2. Icebergテーブルへのデータ投入

Parquetデータをテーブルに投入します。

```python
# load_to_icebergツールを使用
result = await load_to_iceberg(
    table_name="hokkaido_population",
    s3_parquet_path=parquet_result['s3_parquet_path'],
    create_if_not_exists=True
)

print(result)
# 出力例:
# {
#   "success": True,
#   "table_name": "hokkaido_population",
#   "database": "estat_db",
#   "records_loaded": "1234",
#   "source_path": "s3://estat-data-lake/parquet/data/...",
#   "table_location": "s3://estat-data-lake/tables/hokkaido_population/",
#   "message": "Successfully loaded data to table hokkaido_population (1234 records)"
# }
```

### 3. Athenaでの基本分析

テーブルに対して基本的な統計分析を実行します。

```python
# analyze_with_athenaツールを使用（基本分析）
result = await analyze_with_athena(
    table_name="hokkaido_population",
    analysis_type="basic"
)

print(result)
# 出力例:
# {
#   "success": True,
#   "table_name": "hokkaido_population",
#   "database": "estat_db",
#   "analysis_type": "basic",
#   "results": {
#     "total_records": 1234,
#     "statistics": {
#       "count": 1234,
#       "avg_value": 50000.5,
#       "min_value": 100.0,
#       "max_value": 1000000.0,
#       "sum_value": 61700617.0
#     },
#     "by_year": [
#       {"year": 2020, "count": 617, "avg_value": 50100.2},
#       {"year": 2021, "count": 617, "avg_value": 49900.8}
#     ]
#   },
#   "message": "Successfully analyzed table hokkaido_population"
# }
```

### 4. Athenaでの高度な分析

より詳細な分析を実行します。

```python
# analyze_with_athenaツールを使用（高度な分析）
result = await analyze_with_athena(
    table_name="hokkaido_population",
    analysis_type="advanced"
)

print(result)
# 出力例:
# {
#   "success": True,
#   "table_name": "hokkaido_population",
#   "database": "estat_db",
#   "analysis_type": "advanced",
#   "results": {
#     "by_region": [
#       ["01100", 123, 500000.0, 61500000.0],
#       ["01101", 100, 300000.0, 30000000.0],
#       ...
#     ],
#     "by_category": [
#       ["総人口", 617, 500000.0],
#       ["男性", 617, 250000.0],
#       ...
#     ],
#     "trend": [
#       [2020, 500000.0, 100.0, 1000000.0],
#       [2021, 499000.0, 100.0, 999000.0],
#       ...
#     ]
#   },
#   "message": "Successfully analyzed table hokkaido_population"
# }
```

### 5. カスタムクエリの実行

独自のSQLクエリを実行します。

```python
# analyze_with_athenaツールを使用（カスタムクエリ）
custom_sql = """
SELECT 
    year,
    region_code,
    SUM(value) as total_population
FROM estat_db.hokkaido_population
WHERE category = '総人口'
GROUP BY year, region_code
ORDER BY year DESC, total_population DESC
LIMIT 10
"""

result = await analyze_with_athena(
    table_name="hokkaido_population",
    custom_query=custom_sql
)

print(result)
# 出力例:
# {
#   "success": True,
#   "table_name": "hokkaido_population",
#   "database": "estat_db",
#   "analysis_type": "basic",
#   "results": {
#     "custom_query": {
#       "success": True,
#       "result": [
#         ["2021", "01100", "1950000"],
#         ["2021", "01101", "500000"],
#         ...
#       ],
#       "error": None
#     }
#   },
#   "message": "Successfully analyzed table hokkaido_population"
# }
```

## エラーハンドリング

### S3バケットへのアクセスエラー

```python
result = await load_to_iceberg(
    table_name="test_table",
    s3_parquet_path="s3://estat-data-lake/parquet/data.parquet"
)

if not result['success']:
    print(f"エラー: {result['error']}")
    print(f"メッセージ: {result['message']}")
    # 出力例:
    # エラー: Failed to setup Athena output location: Access Denied
    # メッセージ: S3バケット 'estat-data-lake' にathena-resultsディレクトリを作成できませんでした。バケットのアクセス権限を確認してください。
```

### テーブルが存在しないエラー

```python
result = await analyze_with_athena(
    table_name="nonexistent_table",
    analysis_type="basic"
)

if not result['success']:
    print(f"エラー: {result['error']}")
    # 出力例:
    # エラー: Failed to start query: Table 'estat_db.nonexistent_table' does not exist
```

## トラブルシューティング

### 1. Athena出力ディレクトリが作成できない

**症状:**
```
Failed to setup Athena output location: Access Denied
```

**対処方法:**
- S3バケットへの書き込み権限を確認
- IAMポリシーに`s3:PutObject`権限が含まれているか確認

### 2. Athenaクエリがタイムアウトする

**症状:**
```
Query timeout
```

**対処方法:**
- データセットのサイズを確認
- クエリを最適化（WHERE句で絞り込むなど）
- `_execute_athena_query`の`max_wait`パラメータを増やす

### 3. データベースが作成できない

**症状:**
```
Failed to create database: Access Denied
```

**対処方法:**
- Glueへのアクセス権限を確認
- IAMポリシーに`glue:CreateDatabase`権限が含まれているか確認

## ベストプラクティス

1. **データサイズの確認**
   - 大規模データセットの場合は、事前にサイズを確認
   - 必要に応じてフィルタリングを適用

2. **エラーハンドリング**
   - 常に`success`フィールドをチェック
   - エラー時は`error`と`message`フィールドを確認

3. **コスト管理**
   - Athenaのクエリ実行コストを監視
   - 不要なテーブルは定期的に削除

4. **パフォーマンス最適化**
   - Parquetフォーマットを使用（圧縮率が高い）
   - パーティショニングを活用（年、地域コードなど）

## まとめ

修正後のツールは以下の特徴があります：

- ✅ 明確なエラーメッセージ
- ✅ 適切なエラーハンドリング
- ✅ デフォルトワークグループの使用
- ✅ S3出力場所の明示的な指定

これらの改善により、より安定した分析ワークフローが実現できます。
