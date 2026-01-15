# e-Stat汎用メタデータ抽出ツール

このツールは、任意のe-Statデータセットから指定されたメタデータフィールドを抽出するPythonスクリプトです。

## 機能

- 任意のデータセットIDからメタデータを取得
- 指定された16個のフィールドを自動抽出
- エラーハンドリングとタイムアウト対応
- JSON形式での結果保存
- コマンドライン対応

## 抽出されるフィールド

### 要求フィールド
1. `statsCode` - 統計コード
2. `limit` - 制限（メタデータAPIでは取得不可のためN/A）
3. `updatedDate` - 更新日
4. `SURVEY_YEARS` - 調査年
5. `OPEN_YEARS` - 公開年
6. `MAIN_CATEGORY` - 主分類
7. `SUB_CATEGORY` - 副分類
8. `OVERALL_TOTAL_NUMBER` - 総レコード数
9. `UPDATED_DATE` - 更新日
10. `STATISTICS_NAME_SPEC` - 統計名仕様
11. `TABULATION_CATEGORY` - 集計分類
12. `TABULATION_SUB_CATEGORY1` - 集計副分類1
13. `TABULATION_SUB_CATEGORY2` - 集計副分類2
14. `TABULATION_SUB_CATEGORY3` - 集計副分類3
15. `TABULATION_SUB_CATEGORY4` - 集計副分類4
16. `TABULATION_SUB_CATEGORY5` - 集計副分類5

### 追加参考情報
- `datasetId` - データセットID
- `STAT_NAME` - 統計名
- `GOV_ORG` - 政府機関
- `STATISTICS_NAME` - 統計名詳細
- `TITLE` - タイトル
- `CYCLE` - 周期
- `COLLECT_AREA` - 収集地域
- `DESCRIPTION` - 説明

## 使用方法

### 1. 基本的な使用方法

```bash
# 特定のデータセットIDを指定
python3 universal_dataset_metadata_extractor.py 0004019302

# 別のデータセット
python3 universal_dataset_metadata_extractor.py 0002060001
```

### 2. オプション付き実行

```bash
# ファイル保存をスキップ
python3 universal_dataset_metadata_extractor.py 0004019302 --no-save

# タイムアウト時間を変更（デフォルト60秒）
python3 universal_dataset_metadata_extractor.py 0004019302 --timeout 120
```

### 3. テストモード

```bash
# 引数なしで実行するとテストモード（0004019302で実行）
python3 universal_dataset_metadata_extractor.py
```

### 4. ヘルプ表示

```bash
python3 universal_dataset_metadata_extractor.py --help
```

## 出力ファイル

実行すると以下のファイルが生成されます：

1. `extracted_fields_{dataset_id}.json` - 抽出されたフィールドのみ
2. `metadata_{dataset_id}.json` - 完全なメタデータ

## Pythonコードでの使用例

```python
from universal_dataset_metadata_extractor import EstatMetadataExtractor

# 抽出器を初期化
extractor = EstatMetadataExtractor()

# データセットを処理
fields = extractor.process_dataset("0004019302")

if fields:
    print(f"統計コード: {fields['statsCode']}")
    print(f"総レコード数: {fields['OVERALL_TOTAL_NUMBER']}")
    print(f"主分類: {fields['MAIN_CATEGORY']}")
```

## エラーハンドリング

- APIタイムアウト対応
- ネットワークエラー処理
- データ構造の違いに対する安全な取得
- 存在しないフィールドは'N/A'として処理

## 対応データセット

e-Stat APIで提供される全てのデータセットに対応しています。

## 注意事項

- APIキーは環境変数またはスクリプト内で設定
- `limit`フィールドはgetMetaInfo APIでは取得できないため常に'N/A'
- 一部のデータセットでは特定のフィールドが存在しない場合があります

## 実行例

```bash
$ python3 universal_dataset_metadata_extractor.py 0004019302

データセット 0004019302 のメタデータを取得中...
抽出フィールドを extracted_fields_0004019302.json に保存しました
完全なメタデータを metadata_0004019302.json に保存しました

=== データセット 0004019302 の抽出フィールド ===

【要求されたフィールド】
statsCode: 00200521
limit: N/A
updatedDate: 2024-09-30
SURVEY_YEARS: 202010
OPEN_YEARS: 2024-09-30
MAIN_CATEGORY: 人口・世帯
SUB_CATEGORY: 人口
OVERALL_TOTAL_NUMBER: 70686
...

✅ データセット 0004019302 の処理が完了しました
```