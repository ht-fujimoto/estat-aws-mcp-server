# MCP Transform Parquet Tool Fix Report

## 問題の概要

`transform_to_parquet` MCPツールで以下のエラーが発生：

```
'list' object has no attribute 'get'
```

## 原因

スクリプトで保存したJSONデータは直接リスト形式 `[{...}, {...}]` だが、ツールはE-stat API標準形式（`GET_STATS_DATA`構造）のみを想定していた。

## 修正内容

### 1. `.env`ファイルの更新

APIキーを追加：

```bash
ESTAT_APP_ID=320dd2fbff6974743e3f95505c9f346650ab635e
```

### 2. `mcp_servers/estat_aws/server.py`の修正

#### 修正箇所1: データ形式の判定ロジック追加

**Before:**
```python
# JSONデータを読み込み
response = self.s3_client.get_object(Bucket=bucket, Key=key)
data = json.loads(response['Body'].read())

# データを抽出
stats_data = data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {})
data_inf = stats_data.get('DATA_INF', {})
values = data_inf.get('VALUE', [])
```

**After:**
```python
# JSONデータを読み込み
response = self.s3_client.get_object(Bucket=bucket, Key=key)
data = json.loads(response['Body'].read())

# データ形式を判定
# 形式1: E-stat API標準形式（GET_STATS_DATA構造）
# 形式2: 直接リスト形式（スクリプトで保存したデータ）
values = []

if isinstance(data, list):
    # 形式2: 直接リスト形式
    logger.info("Detected direct list format")
    values = data
elif isinstance(data, dict):
    # 形式1: E-stat API標準形式
    logger.info("Detected E-stat API format")
    stats_data = data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {})
    data_inf = stats_data.get('DATA_INF', {})
    values = data_inf.get('VALUE', [])
```

#### 修正箇所2: 辞書型チェックの追加

**Before:**
```python
for value in values:
    # 値を取得（'-'や空文字の場合はNoneに変換）
    raw_value = value.get('$', '0')
```

**After:**
```python
for value in values:
    # 辞書でない場合はスキップ
    if not isinstance(value, dict):
        logger.warning(f"Skipping non-dict value: {type(value)}")
        continue
    
    # 値を取得（'-'や空文字の場合はNoneに変換）
    raw_value = value.get('$', '0')
```

## 修正されたファイル

1. `.env` - APIキー追加
2. `mcp_servers/estat_aws/server.py` - データ形式判定ロジック追加
3. `estat-aws-package/mcp_servers/estat_aws/server.py` - 同期済み

## デプロイ手順

### オプション1: ECSへのデプロイ（推奨）

```bash
# Dockerデーモンを起動してから実行
./update_mcp_server_fix.sh
```

### オプション2: 手動デプロイ

```bash
# 1. Dockerイメージをビルド
cd estat-aws-package
docker build -t estat-mcp-server:v2.2.1-fix .

# 2. ECRにプッシュ
aws ecr get-login-password --region ap-northeast-1 | \
  docker login --username AWS --password-stdin \
  639135896267.dkr.ecr.ap-northeast-1.amazonaws.com

docker tag estat-mcp-server:v2.2.1-fix \
  639135896267.dkr.ecr.ap-northeast-1.amazonaws.com/estat-mcp-server:v2.2.1-fix

docker push 639135896267.dkr.ecr.ap-northeast-1.amazonaws.com/estat-mcp-server:v2.2.1-fix

# 3. ECSサービスを更新
aws ecs update-service \
  --cluster estat-mcp-cluster \
  --service estat-mcp-service \
  --force-new-deployment \
  --region ap-northeast-1
```

## テスト方法

修正後、以下のMCPツールでテスト：

```python
# テスト1: 直接リスト形式のデータ
mcp_estat_aws_remote_transform_to_parquet(
    s3_json_path="s3://estat-data-lake/raw/data/0002070002_chunk_002_20260120_090055.json",
    data_type="economy"
)

# テスト2: 完全データセット
mcp_estat_aws_remote_transform_to_parquet(
    s3_json_path="s3://estat-data-lake/raw/data/0002070002_chunk_999_20260120_090056.json",
    data_type="economy"
)
```

## 期待される結果

```json
{
  "success": true,
  "source_path": "s3://estat-data-lake/raw/data/0002070002_chunk_999_20260120_090056.json",
  "target_path": "s3://estat-data-lake/processed/0002070002_chunk_999_20260120_090056.parquet",
  "records_processed": 103629,
  "data_type": "economy",
  "message": "Successfully converted 103629 records to Parquet format"
}
```

## 影響範囲

- **影響あり**: `transform_to_parquet` ツールを使用する全ての処理
- **影響なし**: 他のMCPツール（検索、取得、Iceberg投入など）

## 備考

- 修正により、E-stat API標準形式と直接リスト形式の両方に対応
- 既存の動作には影響なし（後方互換性あり）
- エラーハンドリングが強化され、より堅牢に

## 関連ファイル

- `mcp_servers/estat_aws/server.py` - メインの修正ファイル
- `estat-aws-package/mcp_servers/estat_aws/server.py` - デプロイ用コピー
- `.env` - APIキー設定
- `update_mcp_server_fix.sh` - デプロイスクリプト
- `fetch_complete_household_data.py` - データ取得スクリプト
- `convert_to_parquet_complete.py` - Parquet変換スクリプト

---

**作成日**: 2026-01-20  
**バージョン**: v2.2.1-fix  
**ステータス**: 修正完了、デプロイ待ち
