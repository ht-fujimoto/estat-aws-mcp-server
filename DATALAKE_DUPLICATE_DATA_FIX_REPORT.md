# データレイク重複データ修正レポート

## 概要

**日時**: 2026-01-20  
**ステータス**: ✓ 修正完了  
**問題**: Icebergテーブルに重複データが存在  
**解決策**: テーブルを再作成し、正しいデータのみを投入

## 問題の詳細

### 発見された重複データ

修正前のデータ状況：

| データセットID | レコード数 | 期待値 | 重複倍率 |
|--------------|-----------|--------|---------|
| 0002070002（家計調査） | 714,516 | 103,629 | 約7倍 |
| 0003217721（労働力調査） | 155,776 | 38,944 | 約4倍 |
| その他のテストデータ | 492,091 | 0 | - |
| **総レコード数** | **1,362,383** | **142,573** | **約10倍** |

### 原因分析

1. **複数回のデータ投入**
   - チャンク1（100,000レコード）
   - チャンク2（3,629レコード）
   - 統合ファイル（103,629レコード）
   - 完全ファイル（103,629レコード）
   - 同じデータが複数回投入されていた

2. **テストデータの残存**
   - 以前のテスト時に投入したデータが削除されていなかった
   - 7つの異なるデータセットが混在

3. **スキーマの不一致**
   - Icebergテーブルのスキーマ（STRING型）
   - Parquetファイルのスキーマ（INT64型）
   - 型の不一致により、データ投入時にエラーが発生

## 修正プロセス

### ステップ1: 重複データの確認

スクリプト: `check_duplicate_data.py`

```bash
python3 check_duplicate_data.py
```

**結果**:
- データセットID別のレコード数を確認
- S3上のParquetファイルを確認
- 重複の原因を特定

### ステップ2: Parquetファイルのスキーマ確認

スクリプト: `check_parquet_schema.py`

```bash
python3 check_parquet_schema.py
```

**実際のスキーマ**:
```
stats_data_id: STRING
value: DOUBLE
unit: STRING
updated_at: TIMESTAMP
year: INT64 (BIGINT)
quarter: INT64 (BIGINT)
region_code: STRING
indicator: STRING
```

### ステップ3: Icebergテーブルの再作成

スクリプト: `recreate_iceberg_with_correct_schema.py`

```bash
python3 recreate_iceberg_with_correct_schema.py
```

**実行内容**:
1. 既存のeconomy_dataテーブルを削除
2. 正しいスキーマで新しいテーブルを作成
3. 一時的な外部テーブルを作成
4. Parquetファイルをコピー
5. 一時テーブルからIcebergテーブルにデータを投入
6. 一時テーブルを削除

### ステップ4: データの検証

スクリプト: `verify_clean_data.py`

```bash
python3 verify_clean_data.py
```

## 修正後のデータ状況

### データセット別の基本統計

| データセットID | レコード数 | 年数 | 最小年 | 最大年 | 有効値 | 平均値 |
|--------------|-----------|------|--------|--------|--------|--------|
| 0002070002（家計調査） | 103,629 | 163 | 1985000103 | 2025000709 | 76,477 | 34,681.40 |
| 0003217721（労働力調査） | 38,944 | 31 | 2018000103 | 2025000709 | 38,944 | 269.29 |
| **総レコード数** | **142,573** | - | - | - | **115,421** | - |

### 家計調査データ（年次別 - 上位10年）

| 年 | レコード数 | 平均値 |
|----|-----------|--------|
| 2025000709 | 379 | 41,526.81 |
| 2025000406 | 379 | 45,221.37 |
| 2025000103 | 379 | 38,523.88 |
| 2024001012 | 379 | 47,137.07 |
| 2024000709 | 379 | 39,132.07 |
| 2024000406 | 379 | 42,581.37 |
| 2024000103 | 379 | 36,527.50 |
| 2023001012 | 379 | 44,272.66 |
| 2023000709 | 379 | 37,573.71 |
| 2023000406 | 379 | 40,683.51 |

### 労働力調査データ（年次別 - 上位10年）

| 年 | レコード数 | 平均値 |
|----|-----------|--------|
| 2025000709 | 1,262 | 267.92 |
| 2025000406 | 1,267 | 267.14 |
| 2025000103 | 1,257 | 268.15 |
| 2024001012 | 1,250 | 270.28 |
| 2024000709 | 1,266 | 266.78 |
| 2024000406 | 1,248 | 271.38 |
| 2024000103 | 1,259 | 267.46 |
| 2023001012 | 1,240 | 272.04 |
| 2023000709 | 1,284 | 263.84 |
| 2023000406 | 1,258 | 269.07 |

## 技術的な詳細

### 正しいIcebergテーブルスキーマ

```sql
CREATE TABLE estat_db.economy_data (
    stats_data_id STRING,
    value DOUBLE,
    unit STRING,
    updated_at TIMESTAMP,
    year BIGINT,
    quarter BIGINT,
    region_code STRING,
    indicator STRING
)
LOCATION 's3://estat-data-lake/iceberg-tables/economy_data/'
TBLPROPERTIES (
    'table_type'='ICEBERG',
    'format'='parquet',
    'write_compression'='snappy'
)
```

### データ投入方法

1. **一時的な外部テーブルを作成**
   ```sql
   CREATE EXTERNAL TABLE estat_db.temp_household_data (...)
   STORED AS PARQUET
   LOCATION 's3://estat-data-lake/processed/household/'
   ```

2. **Parquetファイルをコピー**
   ```python
   s3.copy_object(
       Bucket='estat-data-lake',
       CopySource={'Bucket': 'estat-data-lake', 'Key': 'processed/0002070002_chunk_999_20260120_090056.parquet'},
       Key='processed/household/data.parquet'
   )
   ```

3. **一時テーブルからIcebergテーブルにデータを投入**
   ```sql
   INSERT INTO estat_db.economy_data
   SELECT * FROM estat_db.temp_household_data
   ```

## 使用したスクリプト

1. `check_duplicate_data.py` - 重複データの確認
2. `check_parquet_schema.py` - Parquetファイルのスキーマ確認
3. `recreate_iceberg_with_correct_schema.py` - Icebergテーブルの再作成
4. `verify_clean_data.py` - データの検証

## S3ストレージ構成（修正後）

```
s3://estat-data-lake/
├── raw/data/                          # 生データ（JSON）
│   ├── 0002070002_chunk_999_*.json   # 家計調査 統合ファイル
│   └── 0003217721_*.json             # 労働力調査
├── processed/                         # 変換済みデータ（Parquet）
│   ├── 0002070002_chunk_999_*.parquet # 家計調査（103,629レコード）
│   ├── 0003217721_*.parquet          # 労働力調査（38,944レコード）
│   ├── household/                     # 一時ディレクトリ
│   │   └── data.parquet
│   └── labor/                         # 一時ディレクトリ
│       └── data.parquet
└── iceberg-tables/                    # Icebergテーブル
    └── economy_data/                  # 経済データ（142,573レコード）
```

## Athenaクエリ例

### 基本的なデータ確認

```sql
-- 総レコード数
SELECT COUNT(*) as total_records
FROM estat_db.economy_data;
-- 結果: 142,573

-- データセット別のレコード数
SELECT 
    stats_data_id,
    COUNT(*) as record_count
FROM estat_db.economy_data
GROUP BY stats_data_id
ORDER BY stats_data_id;
-- 結果:
-- 0002070002: 103,629
-- 0003217721: 38,944
```

### 統計分析

```sql
-- データセット別の基本統計
SELECT 
    stats_data_id,
    COUNT(*) as record_count,
    COUNT(DISTINCT year) as unique_years,
    MIN(year) as min_year,
    MAX(year) as max_year,
    COUNT(value) as non_null_values,
    AVG(value) as avg_value
FROM estat_db.economy_data
GROUP BY stats_data_id;
```

### 年次別の分析

```sql
-- 家計調査の年次別平均値
SELECT 
    year,
    COUNT(*) as record_count,
    AVG(value) as avg_value
FROM estat_db.economy_data
WHERE stats_data_id = '0002070002' AND value IS NOT NULL
GROUP BY year
ORDER BY year DESC;
```

## 今後の推奨事項

### 1. データ投入プロセスの改善

- **重複チェック**: データ投入前に既存データを確認
- **トランザクション管理**: 投入失敗時のロールバック機能
- **ログ記録**: データ投入履歴の記録

### 2. スキーマ管理

- **スキーマバージョニング**: スキーマ変更の履歴管理
- **自動スキーマ検出**: Parquetファイルからスキーマを自動生成
- **型変換の自動化**: データ型の不一致を自動で解決

### 3. データ品質管理

- **定期的な重複チェック**: 週次または月次で重複データを確認
- **データ整合性チェック**: 期待値との比較
- **異常値検出**: 統計的手法による異常値の検出

### 4. テストデータの管理

- **テスト環境の分離**: 本番環境とテスト環境を分離
- **テストデータの自動削除**: テスト完了後の自動クリーンアップ
- **テストデータのタグ付け**: テストデータを識別可能にする

## まとめ

✓ 重複データを完全に削除  
✓ 正しいスキーマでIcebergテーブルを再作成  
✓ 家計調査データ（103,629レコード）を投入  
✓ 労働力調査データ（38,944レコード）を投入  
✓ 総レコード数: 142,573レコード（期待値と一致）  
✓ データ品質を検証  

データレイクは正常な状態に戻り、統計分析に使用できる状態になりました。

---

**作成日**: 2026-01-20  
**バージョン**: 1.0  
**ステータス**: ✓ 修正完了
