# E-stat データレイク専用MCPサーバー

既存のE-stat AWS MCPサーバーに影響を与えずに、データレイク取り込みに特化した機能を提供するローカルMCPサーバーです。

## 特徴

- **既存MCPサーバーと独立**: 既存のMCPサーバーに変更を加えずに使用可能
- **データレイク特化**: データ取り込み、変換、検証、保存に最適化
- **ローカル実行**: プロジェクトディレクトリ内で完結
- **既存ツールとの連携**: 既存のMCPツールでデータ取得後、このサーバーで処理

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install mcp pandas pyarrow boto3
```

### 2. Kiro設定への追加

`.kiro/settings/mcp.json`に以下を追加：

```json
{
  "mcpServers": {
    "estat-datalake": {
      "command": "python3",
      "args": [
        "datalake/mcp_server/datalake_mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": ".",
        "AWS_REGION": "ap-northeast-1"
      },
      "disabled": false,
      "autoApprove": [
        "fetch_and_transform_dataset",
        "validate_transformed_data",
        "save_to_parquet",
        "create_iceberg_table",
        "register_dataset_metadata",
        "ingest_complete_dataset"
      ]
    }
  }
}
```

### 3. MCPサーバーの再接続

Kiroのコマンドパレットから「MCP: Reconnect All Servers」を実行

## 利用可能なツール

### 1. fetch_and_transform_dataset

E-statデータセットを取得してIceberg形式に変換

**パラメータ:**
- `dataset_id` (必須): データセットID
- `domain` (オプション): データドメイン（デフォルト: generic）
- `s3_input_path` (オプション): S3入力パス

**使用例:**
```python
# 既存MCPツールでデータ取得
result = mcp_estat_aws_remote_fetch_dataset_auto(
    dataset_id="0004021107",
    save_to_s3=True
)

# データレイクMCPで変換
transform_result = fetch_and_transform_dataset(
    dataset_id="0004021107",
    domain="population",
    s3_input_path=result["s3_location"]
)
```

### 2. validate_transformed_data

変換済みデータの品質を検証

**パラメータ:**
- `data` (必須): 検証対象のデータ
- `required_columns` (オプション): 必須カラムのリスト

### 3. save_to_parquet

データをParquet形式でS3に保存

**パラメータ:**
- `data` (必須): 保存対象のデータ
- `dataset_id` (必須): データセットID
- `domain` (必須): データドメイン
- `s3_output_path` (オプション): S3出力パス

### 4. create_iceberg_table

Icebergテーブルを作成

**パラメータ:**
- `domain` (必須): データドメイン
- `table_name` (オプション): テーブル名
- `database` (オプション): データベース名

### 5. register_dataset_metadata

データセットのメタデータを登録

**パラメータ:**
- `dataset_id` (必須): データセットID
- `domain` (必須): データドメイン
- `dataset_name` (オプション): データセット名
- `total_records` (オプション): 総レコード数
- `table_name` (オプション): テーブル名

### 6. ingest_complete_dataset

データセットの完全取り込み（取得→変換→検証→保存→登録）

**パラメータ:**
- `dataset_id` (必須): データセットID
- `domain` (必須): データドメイン
- `s3_input_path` (オプション): S3入力パス

## ワークフロー例

### 基本的なデータ取り込み

```python
# ステップ1: 既存MCPツールでデータ取得
fetch_result = mcp_estat_aws_remote_fetch_dataset_auto(
    dataset_id="0004021107",
    convert_to_japanese=True,
    save_to_s3=True
)

# ステップ2: データレイクMCPで変換
transform_result = fetch_and_transform_dataset(
    dataset_id="0004021107",
    domain="population",
    s3_input_path=fetch_result["s3_location"]
)

# ステップ3: データ検証
validation_result = validate_transformed_data(
    data=transform_result["transformed_data"],
    required_columns=["dataset_id", "value"]
)

# ステップ4: Parquet保存
save_result = save_to_parquet(
    data=transform_result["transformed_data"],
    dataset_id="0004021107",
    domain="population"
)

# ステップ5: テーブル作成
table_result = create_iceberg_table(
    domain="population"
)

# ステップ6: メタデータ登録
metadata_result = register_dataset_metadata(
    dataset_id="0004021107",
    dataset_name="年齢（各歳），男女別人口及び人口性比",
    domain="population",
    total_records=4080,
    table_name="population_data"
)
```

### 完全自動取り込み

```python
# 既存MCPツールでデータ取得
fetch_result = mcp_estat_aws_remote_fetch_dataset_auto(
    dataset_id="0004021107",
    save_to_s3=True
)

# データレイクMCPで完全取り込み
result = ingest_complete_dataset(
    dataset_id="0004021107",
    domain="population",
    s3_input_path=fetch_result["s3_location"]
)
```

## トラブルシューティング

### MCPサーバーが起動しない

1. 依存パッケージがインストールされているか確認
   ```bash
   pip list | grep -E "mcp|pandas|pyarrow|boto3"
   ```

2. Pythonパスが正しいか確認
   ```bash
   which python3
   ```

3. MCPサーバーのログを確認
   - Kiroのコマンドパレット → "MCP: Show Server Logs"

### ツールが見つからない

1. MCPサーバーを再接続
   - Kiroのコマンドパレット → "MCP: Reconnect All Servers"

2. サーバーが有効になっているか確認
   - `.kiro/settings/mcp.json`の`disabled`が`false`であることを確認

### AWS認証エラー

1. AWS認証情報が設定されているか確認
   ```bash
   aws configure list
   ```

2. 環境変数を確認
   ```bash
   echo $AWS_ACCESS_KEY_ID
   echo $AWS_SECRET_ACCESS_KEY
   echo $AWS_REGION
   ```

## 開発

### ツールの追加

`datalake_mcp_server.py`の`list_tools()`と`call_tool()`に新しいツールを追加

### デバッグ

```bash
# ローカルでMCPサーバーを起動
python3 datalake/mcp_server/datalake_mcp_server.py

# ログレベルを変更
export LOG_LEVEL=DEBUG
python3 datalake/mcp_server/datalake_mcp_server.py
```

## 参考

- [MCP Documentation](https://modelcontextprotocol.io/)
- [E-stat API Documentation](https://www.e-stat.go.jp/api/)
- [Apache Iceberg Documentation](https://iceberg.apache.org/)
