# e-Stat Enhanced MCP Server - ツール一覧

このドキュメントでは、e-Stat Enhanced MCPサーバーで利用可能な全てのツールについて説明します。

## 📋 目次

1. [データ検索](#1-データ検索)
2. [データ取得](#2-データ取得)
3. [CSV操作（新機能）](#3-csv操作新機能)
4. [データ変換](#4-データ変換)
5. [データ分析](#5-データ分析)

---

## 1. データ検索

### 🔍 search_estat_data
自然言語でe-Statデータを検索し、キーワードサジェスト機能付きで最適なデータセットを提案します。

**パラメータ:**
- `query` (必須): 検索クエリ（例: "年齢別 収入"、"東京都 交通事故"）
- `max_results` (オプション): 返却する最大件数（デフォルト: 5、最大: 20）
- `auto_suggest` (オプション): キーワードサジェスト機能を有効にするか（デフォルト: true）
- `scoring_method` (オプション): スコアリング方法（"enhanced" または "basic"、デフォルト: "enhanced"）

**返却値:**
- スコア順にソートされた統計表リスト
- 各データセットのメタデータ（総レコード数、カテゴリ詳細含む）
- キーワードサジェスト（該当する場合）

**使用例:**
```json
{
  "query": "東京都の交通事故統計",
  "max_results": 5,
  "auto_suggest": true
}
```

### 💡 apply_keyword_suggestions
ユーザーが承認したキーワード変換を適用して新しい検索クエリを生成します。

**パラメータ:**
- `original_query` (必須): 元のクエリ
- `accepted_keywords` (必須): 承認されたキーワード変換（{元のキーワード: 新しいキーワード}の辞書形式）

**返却値:**
- 変換後のクエリ

**使用例:**
```json
{
  "original_query": "年齢別 収入",
  "accepted_keywords": {
    "収入": "所得"
  }
}
```

---

## 2. データ取得

### 📥 fetch_dataset_auto
データセットを自動取得（デフォルトで全データ取得、大規模データは自動分割）

**パラメータ:**
- `dataset_id` (必須): データセットID
- `save_to_s3` (オプション): S3に保存するか（デフォルト: true）
- `convert_to_japanese` (オプション): コード→和名変換を実施するか（デフォルト: true）

**返却値:**
- 取得したレコード数
- 完全性比率
- S3保存場所（save_to_s3=trueの場合）
- サンプルデータ

**使用例:**
```json
{
  "dataset_id": "0002070001",
  "save_to_s3": true,
  "convert_to_japanese": true
}
```

### 🚀 fetch_large_dataset_complete
大規模データセットの完全取得（分割取得対応、最大100万件）

**パラメータ:**
- `dataset_id` (必須): データセットID
- `max_records` (オプション): 取得する最大レコード数（デフォルト: 1,000,000）
- `chunk_size` (オプション): 1回あたりの取得件数（デフォルト: 100,000）
- `save_to_s3` (オプション): S3に保存するか（デフォルト: true）
- `convert_to_japanese` (オプション): コード→和名変換を実施するか（デフォルト: true）

**返却値:**
- 取得したレコード数
- チャンク数
- 処理時間
- S3保存場所

**使用例:**
```json
{
  "dataset_id": "0004040079",
  "max_records": 500000,
  "chunk_size": 100000
}
```

### 🎯 fetch_dataset_filtered
10万件以上のデータセットをカテゴリ指定で絞り込み取得

**パラメータ:**
- `dataset_id` (必須): データセットID
- `filters` (必須): フィルタ条件（例: {"area": "13000", "time": "2020"}）
- `save_to_s3` (オプション): S3に保存するか（デフォルト: true）
- `convert_to_japanese` (オプション): コード→和名変換を実施するか（デフォルト: true）

**返却値:**
- フィルタリングされたデータ
- 取得したレコード数
- S3保存場所

**使用例:**
```json
{
  "dataset_id": "0002070001",
  "filters": {
    "area": "13000",
    "time": "2020"
  }
}
```

---

## 3. CSV操作（新機能）

### 💾 save_dataset_as_csv
取得したデータセットをCSV形式でS3に保存します。

**パラメータ:**
- `dataset_id` (必須): データセットID
- `s3_json_path` (オプション): S3上のJSONファイルパス
- `local_json_path` (オプション): ローカルのJSONファイルパス
- `output_filename` (オプション): 出力ファイル名（デフォルト: dataset_id_YYYYMMDD_HHMMSS.csv）

**注意:** `s3_json_path` または `local_json_path` のいずれかを指定する必要があります。

**返却値:**
- 保存されたレコード数
- カラム一覧
- S3保存場所（s3://bucket/key 形式）
- ファイル名

**使用例1（S3から）:**
```json
{
  "dataset_id": "0002070001",
  "s3_json_path": "s3://estat-data-lake/raw/data/0002070001_20260108_002907.json"
}
```

**使用例2（ローカルから）:**
```json
{
  "dataset_id": "0002070001",
  "local_json_path": "0002070001_complete_20260108_002907.json",
  "output_filename": "traffic_accidents_2020.csv"
}
```

### 🔗 get_estat_table_url
統計表IDからe-Statホームページのリンクを生成します。

**パラメータ:**
- `dataset_id` (必須): 統計表ID（例: "0002112323"）

**返却値:**
- 統計表のホームページURL
- 処理時間

**使用例:**
```json
{
  "dataset_id": "0002112323"
}
```

**返却例:**
```json
{
  "success": true,
  "dataset_id": "0002112323",
  "table_url": "https://www.e-stat.go.jp/dbview?sid=0002112323",
  "processing_time_seconds": 0.0001,
  "message": "統計表のホームページURL: https://www.e-stat.go.jp/dbview?sid=0002112323"
}
```

**用途:**
- データの出典確認
- 統計表の詳細な説明を確認
- データの更新履歴を確認
- 関連する統計表を探す

### 📎 get_csv_download_url
S3 CSVファイルの署��付きダウンロードURLを生成します（ブラウザまたはcurlでダウンロード可能）。

**パラメータ:**
- `s3_path` (必須): S3上のCSVファイルパス（s3://bucket/key 形式）
- `expires_in` (オプション): URL有効期限（秒）（デフォルト: 3600秒 = 1時間）
- `filename` (オプション): ダウンロード時のファイル名（省略時はS3のキー名を使用）

**返却値:**
- 署名付きダウンロードURL
- ファイルサイズ（バイト、MB）
- 有効期限

**使用例:**
```json
{
  "s3_path": "s3://estat-data-lake/csv/0002070001_20260108_002907.csv",
  "expires_in": 3600,
  "filename": "traffic_accidents.csv"
}
```

### ⬇️ download_csv_from_s3
S3に保存されたCSVファイルをローカルにダウンロードします。

**パラメータ:**
- `s3_path` (必須): S3上のCSVファイルパス（s3://bucket/key 形式）
- `local_path` (オプション): ローカル保存先パス（デフォルト: カレントディレクトリ）

**返却値:**
- ダウンロード先のローカルパス
- ファイルサイズ（バイト、MB）

**使用例:**
```json
{
  "s3_path": "s3://estat-data-lake/csv/0002070001_20260108_002907.csv",
  "local_path": "traffic_accidents.csv"
}
```

---

## 4. データ変換

### 🔄 transform_to_parquet
JSONデータをParquet形式に変換してS3に保存します。

**パラメータ:**
- `s3_json_path` (必須): S3上のJSONファイルパス
- `data_type` (必須): データ種別
- `output_prefix` (オプション): 出力先プレフィックス

**返却値:**
- 変換されたレコード数
- Parquet保存場所

**使用例:**
```json
{
  "s3_json_path": "s3://estat-data-lake/raw/data/0002070001_20260108_002907.json",
  "data_type": "traffic_accidents"
}
```

### 🗄️ load_to_iceberg
ParquetデータをIcebergテーブルに投入します。

**パラメータ:**
- `table_name` (必須): テーブル名
- `s3_parquet_path` (必須): S3上のParquetファイルパス
- `create_if_not_exists` (オプション): テーブルが存在しない場合に作成するか（デフォルト: true）

**返却値:**
- テーブル名
- 投入されたレコード数

**使用例:**
```json
{
  "table_name": "traffic_accidents",
  "s3_parquet_path": "s3://estat-data-lake/parquet/traffic_accidents.parquet"
}
```

---

## 5. データ分析

### 📊 analyze_with_athena
Athenaで統計分析を実行します。

**パラメータ:**
- `table_name` (必須): テーブル名
- `analysis_type` (オプション): 分析タイプ（"basic" または "advanced"、デフォルト: "basic"）
- `custom_query` (オプション): カスタムクエリ

**返却値:**
- 分析結果
- 実行されたクエリ
- 成功した分析数

**使用例:**
```json
{
  "table_name": "traffic_accidents",
  "analysis_type": "basic"
}
```

---

## 🔄 典型的なワークフロー

### ワークフロー1: データ検索から分析まで

1. **データ検索**
   ```json
   search_estat_data({ "query": "交通事故統計" })
   ```

2. **データ取得**
   ```json
   fetch_dataset_auto({ "dataset_id": "0002070001" })
   ```

3. **CSV保存**
   ```json
   save_dataset_as_csv({
     "dataset_id": "0002070001",
     "s3_json_path": "s3://estat-data-lake/raw/data/0002070001_20260108_002907.json"
   })
   ```

4. **CSVダウンロード**
   ```json
   download_csv_from_s3({
     "s3_path": "s3://estat-data-lake/csv/0002070001_20260108_002907.csv"
   })
   ```

### ワークフロー2: 高度な分析パイプライン

1. **データ検索** → `search_estat_data`
2. **データ取得** → `fetch_large_dataset_complete`
3. **Parquet変換** → `transform_to_parquet`
4. **Icebergロード** → `load_to_iceberg`
5. **Athena分析** → `analyze_with_athena`

---

## 🔧 設定

### 環境変数
- `ESTAT_APP_ID`: e-Stat APIキー（必須）
- `S3_BUCKET`: S3バケット名（デフォルト: estat-data-lake）
- `AWS_REGION`: AWSリージョン（デフォルト: ap-northeast-1）

### MCP設定（~/.kiro/settings/mcp.json）
```json
{
  "mcpServers": {
    "estat-enhanced": {
      "command": "python3",
      "args": ["/path/to/estat_enhanced_analysis.py"],
      "env": {
        "ESTAT_APP_ID": "your_api_key",
        "S3_BUCKET": "estat-data-lake",
        "AWS_REGION": "ap-northeast-1"
      },
      "disabled": false,
      "autoApprove": [
        "search_estat_data",
        "apply_keyword_suggestions",
        "fetch_dataset_auto",
        "fetch_dataset_filtered",
        "fetch_large_dataset_complete",
        "save_dataset_as_csv",
        "download_csv_from_s3",
        "transform_to_parquet",
        "load_to_iceberg",
        "analyze_with_athena"
      ]
    }
  }
}
```

---

## 📝 注意事項

1. **CSV機能の制限事項:**
   - CSVファイルはBOM付きUTF-8で保存されます（Excel互換）
   - 大規模データセット（100万件以上）の場合、メモリ使用量に注意してください
   - S3へのアップロード/ダウンロードにはAWS認証情報が必要です

2. **データ取得の推奨事項:**
   - 10万件未満: `fetch_dataset_auto`
   - 10万件以上: `fetch_large_dataset_complete` または `fetch_dataset_filtered`

3. **パフォーマンス:**
   - 大規模データセットの取得には時間がかかる場合があります
   - 並列処理により高速化されていますが、APIレート制限に注意してください

---

## 🆕 更新履歴

### v2.1.0 (2026-01-08)
- ✨ **新機能:** `save_dataset_as_csv` - データセットをCSV形式でS3に保存
- ✨ **新機能:** `download_csv_from_s3` - S3からCSVファイルをダウンロード
- 📝 ドキュメント更新

### v2.0.0 (2026-01-05)
- 初回リリース
- 8つの基本ツールを実装
