# estat-aws-remote ツール詳細設計書

## 📋 目次

1. [ツール1: search_estat_data](#ツール1-search_estat_data)
2. [ツール2: apply_keyword_suggestions](#ツール2-apply_keyword_suggestions)
3. [ツール3: fetch_dataset_auto](#ツール3-fetch_dataset_auto)
4. [ツール4: fetch_large_dataset_complete](#ツール4-fetch_large_dataset_complete)
5. [ツール5: fetch_dataset_filtered](#ツール5-fetch_dataset_filtered)
6. [ツール6: save_dataset_as_csv](#ツール6-save_dataset_as_csv)
7. [ツール7: save_metadata_as_csv](#ツール7-save_metadata_as_csv)
8. [ツール8: get_csv_download_url](#ツール8-get_csv_download_url)
9. [ツール9: get_estat_table_url](#ツール9-get_estat_table_url)
10. [ツール10: transform_to_parquet](#ツール10-transform_to_parquet)
11. [ツール11: load_to_iceberg](#ツール11-load_to_iceberg)
12. [ツール12: analyze_with_athena](#ツール12-analyze_with_athena)

---

## ツール1: search_estat_data

### 概要
自然言語クエリでe-Stat統計データを検索し、関連性の高いデータセットを提案する。

### メソッドシグネチャ
```python
async def search_estat_data(
    self,
    query: str,
    max_results: int = 5,
    auto_suggest: bool = True,
    scoring_method: str = "enhanced"
) -> Dict[str, Any]
```

### パラメータ詳細

| パラメータ | 型 | デフォルト | 必須 | 説明 |
|-----------|-----|-----------|------|------|
| query | str | - | ✓ | 検索クエリ |
| max_results | int | 5 | - | 返却する最大データセット数 |
| auto_suggest | bool | True | - | キーワードサジェスト有効化 |
| scoring_method | str | "enhanced" | - | "basic" or "enhanced" |


### 処理フロー

```
Step 0: キーワードサジェスト確認
  ↓ (サジェストあり)
Step 0a: サジェスト提案を返却
  ↓ (サジェストなし/適用後)
Step 1: e-Stat API呼び出し (getStatsList)
  ↓
Step 2: 基本スコアリング (全結果)
  ↓
Step 3: Top 20選択
  ↓
Step 4: メタデータ並列取得 (Top 20)
  ↓
Step 5: 強化スコアリング
  ↓
Step 6: Top N返却
```

### 実装詳細

#### Step 0: キーワードサジェスト

```python
if auto_suggest:
    keyword_suggestions = get_keyword_suggestions(query)
    if keyword_suggestions:
        suggestion_message = format_suggestion_message(keyword_suggestions)
        return {
            "success": True,
            "has_suggestions": True,
            "suggestions": {
                "original_query": query,
                "suggestions": keyword_suggestions,
                "message": suggestion_message
            }
        }
```

**キーワード辞書の例**:
- "収入" → "所得"
- "会社" → "事業所"
- "年齢" → "年齢階級"

#### Step 1: e-Stat API呼び出し

```python
params = {
    "appId": self.app_id,
    "searchWord": query,
    "limit": 100
}
response = await self._call_estat_api("getStatsList", params)
table_list = response.get('GET_STATS_LIST', {}).get('DATALIST_INF', {}).get('TABLE_INF', [])
```


#### Step 2: 基本スコアリング

**スコアリング要素** (合計100%):

1. **タイトルマッチ (25%)**
```python
title = self._extract_value(dataset.get('TITLE', ''))
matches = sum(1 for keyword in query_keywords if keyword in title)
score += 0.25 * (matches / len(query_keywords))
```

2. **統計名・分類マッチ (15%)**
```python
stats_name = dataset.get('STATISTICS_NAME', '')
main_cat = self._extract_value(dataset.get('MAIN_CATEGORY', ''))
sub_cat = self._extract_value(dataset.get('SUB_CATEGORY', ''))
category_text = f"{stats_name} {main_cat} {sub_cat}"
```

3. **説明文マッチ (10%)**
```python
description = dataset.get('DESCRIPTION', '')
desc_matches = sum(1 for keyword in query_keywords if keyword in description)
score += 0.1 * (desc_matches / len(query_keywords))
```

4. **更新日の新しさ (15%)**
```python
open_date = dataset.get('OPEN_DATE', '')
date_obj = datetime.strptime(open_date, '%Y-%m-%d')
days_old = (datetime.now() - date_obj).days

if days_old <= 365:
    freshness = 1.0
elif days_old <= 1825:  # 5年
    freshness = 1.0 - (days_old - 365) / 1460 * 0.5
elif days_old <= 3650:  # 10年
    freshness = 0.5 - (days_old - 1825) / 1825 * 0.5
else:
    freshness = 0.0
```

5. **政府組織の信頼性 (10%)**
```python
trusted_orgs = ['総務省', '警察庁', '国土交通省', '厚生労働省', '内閣府']
gov_org = self._extract_value(dataset.get('GOV_ORG', ''))
if any(org in gov_org for org in trusted_orgs):
    score += 0.1
```

6. **データの完全性 (5%)**
```python
completeness = 0
if dataset.get('STATISTICS_NAME'): completeness += 1
if dataset.get('DESCRIPTION'): completeness += 1
if dataset.get('TITLE_SPEC'): completeness += 1
score += 0.05 * (completeness / 3)
```


#### Step 4: メタデータ並列取得

```python
tasks = [
    self._get_metadata_quick(item['table'].get('@id'))
    for item in top_20
]
metadata_list = await asyncio.gather(*tasks, return_exceptions=True)
```

**メタデータ取得内容**:
- 総レコード数
- カテゴリ情報（地域、年度など）
- 10万件超過判定

#### Step 5: 強化スコアリング

**追加要素** (基本スコア80% + 追加20%):

7. **カテゴリマッチ (15%)**
```python
categories = metadata.get('categories', {})
for category_info in categories.values():
    category_values = category_info.get('values', [])
    category_text = ' '.join(category_values)
    matches = sum(1 for keyword in query_keywords if keyword in category_text)
    total_matches += matches
```

8. **データ規模の適切性 (5%)**
```python
if total_records >= 10000: return 1.0
elif total_records >= 1000: return 0.9
elif total_records >= 100: return 0.7
elif total_records >= 10: return 0.5
else: return 0.3
```

### レスポンス形式

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
      "gov_org": "総務省",
      "survey_date": "2020-10-01",
      "open_date": "2021-04-14",
      "score": 0.892,
      "total_records": 47000,
      "total_records_formatted": "47,000件",
      "requires_filtering": false,
      "categories": {
        "area": {
          "name": "地域",
          "count": 47,
          "sample": ["北海道", "青森県", "岩手県", "宮城県", "秋田県"]
        },
        "time": {
          "name": "時間軸",
          "count": 10,
          "sample": ["2020年", "2021年", "2022年", "2023年", "2024年"]
        }
      }
    }
  ],
  "message": "Found 5 relevant datasets with metadata."
}
```


### エラーハンドリング

```python
try:
    # 処理
except Exception as e:
    logger.error(f"Error in search_estat_data: {e}", exc_info=True)
    return format_error_response(e, "search_estat_data", {"query": query})
```

### パフォーマンス

- **並列処理**: Top 20のメタデータを並列取得
- **キャッシング**: HTTPセッションのコネクションプーリング
- **実行時間**: 通常2-5秒

---

## ツール2: apply_keyword_suggestions

### 概要
ユーザーが承認したキーワード変換を適用して新しいクエリを生成する。

### メソッドシグネチャ

```python
def apply_keyword_suggestions_tool(
    self,
    original_query: str,
    accepted_keywords: Dict[str, str]
) -> Dict[str, Any]
```

### パラメータ詳細

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| original_query | str | ✓ | 元のクエリ |
| accepted_keywords | Dict[str, str] | ✓ | 承認された変換 {"収入": "所得"} |

### 処理フロー

```
Step 1: 元のクエリを単語分割
  ↓
Step 2: 各単語をチェック
  ├─ 変換対象 → 新しいキーワードに置換
  └─ 非対象 → そのまま保持
  ↓
Step 3: 新しいクエリを生成
```

### 実装詳細

```python
def apply_keyword_suggestions_tool(self, original_query: str, accepted_keywords: Dict[str, str]):
    new_query = apply_keyword_suggestions(original_query, accepted_keywords)
    
    return {
        "success": True,
        "original_query": original_query,
        "transformed_query": new_query,
        "accepted_keywords": accepted_keywords,
        "message": f"クエリを変換しました。新しいクエリ: '{new_query}'"
    }
```

**keyword_dictionary.pyの実装**:
```python
def apply_keyword_suggestions(query: str, accepted_suggestions: dict) -> str:
    keywords = query.split()
    new_keywords = []
    
    for keyword in keywords:
        if keyword in accepted_suggestions:
            new_keywords.append(accepted_suggestions[keyword])
        else:
            new_keywords.append(keyword)
    
    return " ".join(new_keywords)
```

### 使用例

**入力**:
```json
{
  "original_query": "年齢別 収入",
  "accepted_keywords": {
    "年齢別": "年齢階級",
    "収入": "所得"
  }
}
```

**出力**:
```json
{
  "success": true,
  "original_query": "年齢別 収入",
  "transformed_query": "年齢階級 所得",
  "accepted_keywords": {
    "年齢別": "年齢階級",
    "収入": "所得"
  },
  "message": "クエリを変換しました。新しいクエリ: '年齢階級 所得'"
}
```


---

## ツール3: fetch_dataset_auto

### 概要
データセットのサイズを自動判定し、最適な取得方法を選択する。

### メソッドシグネチャ

```python
async def fetch_dataset_auto(
    self,
    dataset_id: str,
    save_to_s3: bool = True,
    convert_to_japanese: bool = True
) -> Dict[str, Any]
```

### パラメータ詳細

| パラメータ | 型 | デフォルト | 必須 | 説明 |
|-----------|-----|-----------|------|------|
| dataset_id | str | - | ✓ | データセットID |
| save_to_s3 | bool | True | - | S3に保存するか |
| convert_to_japanese | bool | True | - | コード→和名変換 |

### 処理フロー

```
Step 1: データサイズ事前確認
  ├─ API呼び出し (limit=1, metaGetFlg=Y)
  └─ TOTAL_NUMBER取得
  ↓
Step 2: サイズ判定
  ├─ ≤ 100,000件 → _fetch_single_request()
  └─ > 100,000件 → fetch_large_dataset_complete()
```

### 実装詳細

#### Step 1: サイズ確認

```python
test_params = {
    "appId": self.app_id,
    "statsDataId": dataset_id,
    "limit": 1,
    "metaGetFlg": "Y"
}

test_response = await self._call_estat_api("getStatsData", test_params)

total_number = test_response.get('GET_STATS_DATA', {}).get(
    'STATISTICAL_DATA', {}
).get('RESULT_INF', {}).get('TOTAL_NUMBER', 0)

logger.info(f"Dataset size: {total_number:,} records")
```

#### Step 2: 自動選択

```python
LARGE_DATASET_THRESHOLD = 100000  # 10万件

if total_number <= LARGE_DATASET_THRESHOLD:
    logger.info("Small dataset - using single request")
    return await self._fetch_single_request(dataset_id, convert_to_japanese, save_to_s3)
else:
    logger.info("Large dataset - using complete retrieval")
    return await self.fetch_large_dataset_complete(
        dataset_id=dataset_id,
        max_records=min(total_number, 1000000),
        chunk_size=100000,
        save_to_s3=save_to_s3,
        convert_to_japanese=convert_to_japanese
    )
```


### 小規模データ取得 (_fetch_single_request)

```python
async def _fetch_single_request(
    self,
    dataset_id: str,
    convert_to_japanese: bool = True,
    save_to_s3: bool = True
) -> Dict[str, Any]:
    
    params = {
        "appId": self.app_id,
        "statsDataId": dataset_id,
        "limit": LARGE_DATASET_THRESHOLD
    }
    
    data = await self._call_estat_api("getStatsData", params)
    
    # データ抽出
    stats_data = data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {})
    value_list = stats_data.get('DATA_INF', {}).get('VALUE', [])
    
    # S3保存
    if save_to_s3 and self.s3_client:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        s3_key = f"raw/data/{dataset_id}_{timestamp}.json"
        
        self.s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
            ContentType='application/json'
        )
        s3_location = f"s3://{S3_BUCKET}/{s3_key}"
    
    return {
        "success": True,
        "dataset_id": dataset_id,
        "records_fetched": len(value_list),
        "expected_records": total_number,
        "completeness_ratio": 1.0,
        "s3_location": s3_location,
        "sample_data": value_list[:5]
    }
```

### レスポンス例

**小規模データ**:
```json
{
  "success": true,
  "dataset_id": "0003458339",
  "records_fetched": 47000,
  "expected_records": 47000,
  "completeness_ratio": 1.0,
  "processing_time": "2.3秒",
  "sample_data": [
    {"@area": "01000", "@time": "2020", "$": "5224614"},
    {"@area": "02000", "@time": "2020", "$": "1237984"}
  ],
  "s3_location": "s3://estat-data-lake/raw/data/0003458339_20260115_143022.json",
  "message": "Successfully fetched 47,000 records (100.0% complete)"
}
```

---

## ツール4: fetch_large_dataset_complete

### 概要
大規模データセットを分割取得する（MCPタイムアウト制限により最初のチャンクのみ）。

### メソッドシグネチャ

```python
async def fetch_large_dataset_complete(
    self,
    dataset_id: str,
    max_records: int = 1000000,
    chunk_size: int = 100000,
    save_to_s3: bool = True,
    convert_to_japanese: bool = True
) -> Dict[str, Any]
```

### パラメータ詳細

| パラメータ | 型 | デフォルト | 必須 | 説明 |
|-----------|-----|-----------|------|------|
| dataset_id | str | - | ✓ | データセットID |
| max_records | int | 1000000 | - | 取得する最大レコード数 |
| chunk_size | int | 100000 | - | 1チャンクあたりのレコード数 |
| save_to_s3 | bool | True | - | S3に保存するか |
| convert_to_japanese | bool | True | - | コード→和名変換 |


### 処理フロー

```
Step 1: メタデータ取得
  ├─ getMetaInfo API
  └─ OVERALL_TOTAL_NUMBER取得
  ↓
Step 2: 実際の総数確認
  ├─ getStatsData API (limit=1)
  └─ TOTAL_NUMBER取得
  ↓
Step 3: 取得対象レコード数決定
  target_records = min(actual_total, max_records)
  ↓
Step 4: チャンク数計算
  total_chunks = (target_records + chunk_size - 1) // chunk_size
  ↓
Step 5: 最初のチャンク取得
  ├─ startPosition=1
  ├─ limit=chunk_size
  └─ S3保存
  ↓
Step 6: 警告メッセージ返却
  "MCP timeout limit prevents full retrieval"
```

### 実装詳細

#### チャンク取得

```python
# 最初のチャンクのみ取得
params = {
    "appId": self.app_id,
    "statsDataId": dataset_id,
    "limit": chunk_size,
    "startPosition": 1
}

chunk_data = await self._call_estat_api("getStatsData", params)

chunk_values = chunk_data.get('GET_STATS_DATA', {}).get(
    'STATISTICAL_DATA', {}
).get('DATA_INF', {}).get('VALUE', [])

logger.info(f"Retrieved {len(chunk_values):,} records")
```

#### S3保存

```python
if save_to_s3 and self.s3_client:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    s3_key = f"raw/data/{dataset_id}_chunk_001_{timestamp}.json"
    
    self.s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(chunk_data, ensure_ascii=False, indent=2).encode('utf-8'),
        ContentType='application/json'
    )
    s3_location = f"s3://{S3_BUCKET}/{s3_key}"
```

### レスポンス例

```json
{
  "success": true,
  "dataset_id": "0003410379",
  "metadata_total": 500000,
  "actual_total": 500000,
  "target_records": 500000,
  "chunk_size": 100000,
  "total_chunks_needed": 5,
  "chunks_retrieved": 1,
  "records_in_chunk": 100000,
  "completeness": "20.0%",
  "processing_time": "8.5秒",
  "sample_data": [...],
  "s3_location": "s3://estat-data-lake/raw/data/0003410379_chunk_001_20260115_143500.json",
  "next_action": "Use Python script for complete retrieval",
  "recommendation": "For complete data retrieval of 500,000 records, use the standalone Python script 'fetch_0003410379_chunked.py' to avoid MCP timeout limits",
  "message": "Retrieved first chunk (100,000 records). Total 5 chunks needed for complete dataset.",
  "warning": "MCP timeout limit prevents full retrieval. Use standalone script for complete data."
}
```

### 制限事項

- **MCPタイムアウト**: 30-60秒の制限により、最初のチャンクのみ取得
- **完全取得**: スタンドアロンPythonスクリプトを推奨
- **最大レコード数**: 100万件まで


---

## ツール5: fetch_dataset_filtered

### 概要
カテゴリ指定でデータを絞り込んで取得する。10万件以上のデータセットに有効。

### メソッドシグネチャ

```python
async def fetch_dataset_filtered(
    self,
    dataset_id: str,
    filters: Dict[str, str],
    save_to_s3: bool = True,
    convert_to_japanese: bool = True
) -> Dict[str, Any]
```

### パラメータ詳細

| パラメータ | 型 | デフォルト | 必須 | 説明 |
|-----------|-----|-----------|------|------|
| dataset_id | str | - | ✓ | データセットID |
| filters | Dict[str, str] | - | ✓ | フィルタ条件 |
| save_to_s3 | bool | True | - | S3に保存するか |
| convert_to_japanese | bool | True | - | コード→和名変換 |

### フィルタ形式

```python
filters = {
    "area": "13000",      # 地域コード（東京都）
    "cat01": "A1101",     # カテゴリ1
    "time": "2020"        # 時間軸（2020年）
}
```

### 処理フロー

```
Step 1: メタデータ取得
  ├─ getMetaInfo API
  └─ カテゴリ情報抽出
  ↓
Step 2: フィルタ検証・変換
  ├─ 日本語名 → コードに変換
  ├─ コード → そのまま使用
  ├─ 部分マッチ → 候補提案
  └─ 不正値 → エラー返却
  ↓
Step 3: データ取得
  ├─ getStatsData API
  ├─ フィルタパラメータ追加
  └─ limit=100,000
  ↓
Step 4: S3保存
  ↓
Step 5: 結果返却
```

### 実装詳細

#### Step 1: メタデータ取得

```python
meta_params = {"appId": self.app_id, "statsDataId": dataset_id}
meta_data = await self._call_estat_api("getMetaInfo", meta_params)

class_objs = meta_data.get('GET_META_INFO', {}).get(
    'METADATA_INF', {}
).get('CLASS_INF', {}).get('CLASS_OBJ', [])

# カテゴリ情報を抽出
available_categories = {}
for class_obj in class_objs:
    cat_id = class_obj.get('@id')
    cat_name = class_obj.get('@name')
    classes = class_obj.get('CLASS', [])
    
    available_codes = []
    code_to_name = {}
    
    for cls in classes:
        code = cls.get('@code')
        name = cls.get('@name')
        available_codes.append(code)
        code_to_name[code] = name
    
    available_categories[cat_id] = {
        'name': cat_name,
        'codes': available_codes,
        'code_to_name': code_to_name
    }
```


#### Step 2: フィルタ検証・変換

```python
validated_filters = {}
filter_info = {}

for filter_key, filter_value in filters.items():
    if filter_key in available_categories:
        cat_info = available_categories[filter_key]
        
        # 日本語名 → コード変換
        if filter_value in cat_info['code_to_name'].values():
            for code, name in cat_info['code_to_name'].items():
                if name == filter_value:
                    validated_filters[f"cd{filter_key.title()}"] = code
                    filter_info[filter_key] = name
                    break
        
        # コード → そのまま使用
        elif filter_value in cat_info['codes']:
            validated_filters[f"cd{filter_key.title()}"] = filter_value
            filter_info[filter_key] = cat_info['code_to_name'].get(filter_value)
        
        # 部分マッチ
        else:
            partial_matches = [code for code in cat_info['codes'] if filter_value in code]
            if partial_matches:
                best_match = partial_matches[0]
                validated_filters[f"cd{filter_key.title()}"] = best_match
                filter_info[filter_key] = cat_info['code_to_name'].get(best_match)
            else:
                return {
                    "success": False,
                    "error": f"Filter value '{filter_value}' not found for category '{filter_key}'",
                    "available_codes": cat_info['codes'][:20]
                }
```

#### Step 3: データ取得

```python
params = {
    "appId": self.app_id,
    "statsDataId": dataset_id,
    "limit": LARGE_DATASET_THRESHOLD,
    "metaGetFlg": "Y"
}

# 検証済みフィルタを追加
params.update(validated_filters)

data = await self._call_estat_api("getStatsData", params)
```

### 使用例

**入力**:
```json
{
  "dataset_id": "0003410379",
  "filters": {
    "area": "東京都",
    "time": "2020"
  }
}
```

**レスポンス**:
```json
{
  "success": true,
  "dataset_id": "0003410379",
  "filters_applied": {
    "area": "東京都",
    "time": "2020年"
  },
  "records_fetched": 5420,
  "total_available": 500000,
  "filter_effectiveness": "1.1%",
  "processing_time": "3.2秒",
  "sample_data": [...],
  "s3_location": "s3://estat-data-lake/raw/data/0003410379_filtered_20260115_144000.json",
  "next_action": "transform_to_parquet",
  "message": "Successfully fetched 5,420 records with filters (filtered from 500,000 total records)"
}
```

### エラーケース

**不正なカテゴリ**:
```json
{
  "success": false,
  "error": "Category 'invalid_cat' not found in dataset metadata",
  "available_categories": ["area", "cat01", "cat02", "time"],
  "suggestion": "Use one of the available category names"
}
```

**不正な値**:
```json
{
  "success": false,
  "error": "Filter value '99999' not found for category 'area'",
  "available_codes": ["01000", "02000", "13000", "27000", ...],
  "suggestion": "Use one of the available codes for area"
}
```


---

## ツール6: save_dataset_as_csv

### 概要
取得したJSONデータをCSV形式に変換してS3に保存する。Excel互換のBOM付きUTF-8。

### メソッドシグネチャ

```python
async def save_dataset_as_csv(
    self,
    dataset_id: str,
    s3_json_path: Optional[str] = None,
    local_json_path: Optional[str] = None,
    output_filename: Optional[str] = None
) -> Dict[str, Any]
```

### パラメータ詳細

| パラメータ | 型 | デフォルト | 必須 | 説明 |
|-----------|-----|-----------|------|------|
| dataset_id | str | - | ✓ | データセットID |
| s3_json_path | str | None | - | S3上のJSONファイルパス |
| local_json_path | str | None | - | ローカルのJSONファイルパス |
| output_filename | str | None | - | 出力ファイル名 |

### 処理フロー

```
Step 1: データソース決定
  ├─ s3_json_path指定 → S3から読み込み
  ├─ local_json_path指定 → ローカルから読み込み
  └─ 未指定 → fetch_dataset_auto()で取得
  ↓
Step 2: JSONデータ抽出
  ├─ GET_STATS_DATA.STATISTICAL_DATA
  └─ DATA_INF.VALUE
  ↓
Step 3: DataFrame変換
  df = pd.DataFrame(value_list)
  ↓
Step 4: CSV変換
  encoding='utf-8-sig' (BOM付き)
  ↓
Step 5: S3保存
  s3://estat-data-lake/csv/{filename}
```

### 実装詳細

#### Step 1: S3からの読み込み

```python
if s3_json_path:
    # S3パスをパース
    if s3_json_path.startswith('s3://'):
        s3_json_path = s3_json_path[5:]
    
    parts = s3_json_path.split('/', 1)
    bucket = parts[0]
    key = parts[1]
    
    # S3から読み込み
    response = self.s3_client.get_object(Bucket=bucket, Key=key)
    data = json.loads(response['Body'].read().decode('utf-8'))
```

#### Step 2: データ抽出

```python
stats_data = data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {})
value_list = stats_data.get('DATA_INF', {}).get('VALUE', [])

if isinstance(value_list, dict):
    value_list = [value_list]
```

#### Step 3-4: CSV変換

```python
import pandas as pd
import io

df = pd.DataFrame(value_list)

csv_buffer = io.StringIO()
df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
csv_content = csv_buffer.getvalue()
```

#### Step 5: S3保存

```python
if not output_filename:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = f"{dataset_id}_{timestamp}.csv"

s3_key = f"csv/{output_filename}"

self.s3_client.put_object(
    Bucket=S3_BUCKET,
    Key=s3_key,
    Body=csv_content.encode('utf-8-sig'),
    ContentType='text/csv'
)

s3_location = f"s3://{S3_BUCKET}/{s3_key}"
```


### レスポンス例

```json
{
  "success": true,
  "dataset_id": "0003458339",
  "records_count": 47000,
  "columns": ["@area", "@time", "@cat01", "$", "@unit"],
  "s3_location": "s3://estat-data-lake/csv/0003458339_20260115_144500.csv",
  "s3_bucket": "estat-data-lake",
  "s3_key": "csv/0003458339_20260115_144500.csv",
  "filename": "0003458339_20260115_144500.csv",
  "message": "Successfully saved 47,000 records as CSV to S3"
}
```

### フォールバック処理

S3保存失敗時はローカルに保存:

```python
except Exception as s3_error:
    logger.error(f"S3 save failed, falling back to local: {s3_error}")
    local_csv_path = output_filename
    with open(local_csv_path, 'w', encoding='utf-8-sig') as f:
        f.write(csv_content)
    
    return {
        "success": True,
        "local_path": local_csv_path,
        "s3_error": str(s3_error),
        "message": "Successfully saved as CSV locally (S3 failed)"
    }
```

### 特徴

- **BOM付きUTF-8**: Excelで文字化けしない
- **pandas使用**: 高速なDataFrame処理
- **フォールバック**: S3失敗時はローカル保存
- **自動ファイル名**: タイムスタンプ付き

### 修正履歴

**2026年1月9日**: download_csv_from_s3の修正
- `download_file`から`get_object`メソッドに変更
- ディレクトリの自動作成機能を追加
- 一時ファイル作成時のエラーを解消

---

## ツール7: save_metadata_as_csv

### 概要
データセットのメタデータ情報（カテゴリー情報）をCSV形式でS3に保存する。

### メソッドシグネチャ

```python
async def save_metadata_as_csv(
    self,
    dataset_id: str,
    output_filename: Optional[str] = None
) -> Dict[str, Any]
```

### パラメータ詳細

| パラメータ | 型 | デフォルト | 必須 | 説明 |
|-----------|-----|-----------|------|------|
| dataset_id | str | - | ✓ | データセットID |
| output_filename | str | None | - | 出力ファイル名 |

### 処理フロー

```
Step 1: メタデータ取得
  getMetaInfo API
  ↓
Step 2: カテゴリ情報抽出
  CLASS_INF.CLASS_OBJ
  ↓
Step 3: CSV形式に変換
  category_id, category_name, code, name
  ↓
Step 4: S3保存
  s3://estat-data-lake/csv/{dataset_id}_metadata_{timestamp}.csv
```

### 実装詳細

#### Step 1-2: メタデータ取得とカテゴリ抽出

```python
# メタデータ取得
meta_params = {"appId": self.app_id, "statsDataId": dataset_id}
meta_data = await self._call_estat_api("getMetaInfo", meta_params)

# カテゴリ情報抽出
class_objs = meta_data.get('GET_META_INFO', {}).get(
    'METADATA_INF', {}
).get('CLASS_INF', {}).get('CLASS_OBJ', [])

if not isinstance(class_objs, list):
    class_objs = [class_objs] if class_objs else []

# CSV行を生成
csv_rows = [['category_id', 'category_name', 'code', 'name']]

for class_obj in class_objs:
    cat_id = class_obj.get('@id', '')
    cat_name = class_obj.get('@name', '')
    classes = class_obj.get('CLASS', [])
    
    if not isinstance(classes, list):
        classes = [classes] if classes else []
    
    for cls in classes:
        code = cls.get('@code', '')
        name = cls.get('@name', '')
        csv_rows.append([cat_id, cat_name, code, name])
```

#### Step 3-4: CSV変換とS3保存

```python
import csv
from io import StringIO

# CSV生成
csv_buffer = StringIO()
csv_writer = csv.writer(csv_buffer)
csv_writer.writerows(csv_rows)
csv_content = csv_buffer.getvalue()

# ファイル名決定
if not output_filename:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = f"{dataset_id}_metadata_{timestamp}.csv"

s3_key = f"csv/{output_filename}"

# S3保存
self.s3_client.put_object(
    Bucket=S3_BUCKET,
    Key=s3_key,
    Body=csv_content.encode('utf-8-sig'),
    ContentType='text/csv'
)

s3_location = f"s3://{S3_BUCKET}/{s3_key}"
```

### レスポンス例

```json
{
  "success": true,
  "dataset_id": "0003410379",
  "categories_count": 4,
  "total_codes": 2847,
  "s3_location": "s3://estat-data-lake/csv/0003410379_metadata_20260116_150000.csv",
  "s3_bucket": "estat-data-lake",
  "s3_key": "csv/0003410379_metadata_20260116_150000.csv",
  "filename": "0003410379_metadata_20260116_150000.csv",
  "message": "Successfully saved metadata (4 categories, 2847 codes) as CSV to S3"
}
```

### CSV出力例

```csv
category_id,category_name,code,name
tab,表章項目,01,事業所数
tab,表章項目,02,従業者数
cat01,産業分類,A,農業、林業
cat01,産業分類,B,漁業
area,地域,00000,全国
area,地域,01000,北海道
time,時間軸,2020,2020年
time,時間軸,2021,2021年
```

### 用途

1. **フィルタ条件の確認**: `fetch_dataset_filtered`で使用可能なコードを確認
2. **データ理解**: データセットの構造を把握
3. **ドキュメント作成**: データセットの説明資料作成

---

## ツール8: get_csv_download_url

### 概要
S3に保存されたCSVファイルの署名付きダウンロードURLを生成する。

### メソッドシグネチャ

```python
async def get_csv_download_url(
    self,
    s3_path: str,
    expires_in: int = 3600,
    filename: Optional[str] = None
) -> Dict[str, Any]
```

### パラメータ詳細

| パラメータ | 型 | デフォルト | 必須 | 説明 |
|-----------|-----|-----------|------|------|
| s3_path | str | - | ✓ | S3パス (s3://bucket/key) |
| expires_in | int | 3600 | - | URL有効期限（秒） |
| filename | str | None | - | ダウンロード時のファイル名 |

### 処理フロー

```
Step 1: S3パスをパース
  s3://bucket/key → (bucket, key)
  ↓
Step 2: ファイル存在確認
  head_object() → ファイルサイズ取得
  ↓
Step 3: 署名付きURL生成
  generate_presigned_url()
  ↓
Step 4: URL返却
  有効期限情報付き
```

### 実装詳細

#### Step 1: S3パスパース

```python
if not s3_path.startswith('s3://'):
    return {"success": False, "error": "s3_path must start with 's3://'"}

s3_path_clean = s3_path[5:]
parts = s3_path_clean.split('/', 1)
bucket = parts[0]
key = parts[1]
```

#### Step 2: ファイル存在確認

```python
try:
    head_response = self.s3_client.head_object(Bucket=bucket, Key=key)
    file_size = head_response.get('ContentLength', 0)
    file_size_mb = file_size / (1024 * 1024)
    logger.info(f"File size: {file_size_mb:.2f} MB")
except self.s3_client.exceptions.NoSuchKey:
    return {
        "success": False,
        "error": f"File not found in S3: {s3_path}",
        "bucket": bucket,
        "key": key
    }
```


#### Step 3: 署名付きURL生成

```python
# ファイル名を決定
if not filename:
    filename = key.split('/')[-1]

# 署名付きURL生成
params = {
    'Bucket': bucket,
    'Key': key,
    'ResponseContentDisposition': f'attachment; filename="{filename}"'
}

presigned_url = self.s3_client.generate_presigned_url(
    'get_object',
    Params=params,
    ExpiresIn=expires_in
)
```

### レスポンス例

```json
{
  "success": true,
  "s3_path": "s3://estat-data-lake/csv/0003458339_20260115_144500.csv",
  "s3_bucket": "estat-data-lake",
  "s3_key": "csv/0003458339_20260115_144500.csv",
  "download_url": "https://estat-data-lake.s3.ap-northeast-1.amazonaws.com/csv/0003458339_20260115_144500.csv?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...",
  "filename": "0003458339_20260115_144500.csv",
  "expires_in_seconds": 3600,
  "expires_at": 1736928300.0,
  "file_size_bytes": 12458960,
  "file_size_mb": 11.88,
  "processing_time_seconds": 0.15,
  "message": "署名付きURLを生成しました。このURLをブラウザで開くか、curlでダウンロードしてください。有効期限: 3600秒"
}
```

### 使用方法

**ブラウザでダウンロード**:
```
URLをブラウザのアドレスバーに貼り付け
```

**curlでダウンロード**:
```bash
curl -o output.csv "https://estat-data-lake.s3.ap-northeast-1.amazonaws.com/..."
```

### セキュリティ

- **有効期限**: デフォルト1時間（3600秒）
- **署名検証**: AWS署名により改ざん防止
- **ダウンロード専用**: アップロードや削除は不可

---

## ツール8: download_csv_from_s3

### 概要
S3に保存されたCSVファイルをローカルにダウンロードする。

### メソッドシグネチャ

```python
async def download_csv_from_s3(
    self,
    s3_path: str,
    local_path: Optional[str] = None,
    return_content: bool = False
) -> Dict[str, Any]
```

### パラメータ詳細

| パラメータ | 型 | デフォルト | 必須 | 説明 |
|-----------|-----|-----------|------|------|
| s3_path | str | - | ✓ | S3パス (s3://bucket/key) |
| local_path | str | None | - | ローカル保存先パス |
| return_content | bool | False | - | CSV内容を直接返すか |

### 処理フロー

```
Step 1: S3パスをパース
  ↓
Step 2: ローカルパス決定
  ├─ 指定あり → そのまま使用
  └─ 指定なし → ファイル名から自動生成
  ↓
Step 3: ディレクトリ作成
  os.makedirs(local_dir, exist_ok=True)
  ↓
Step 4: S3からダウンロード
  get_object()
  ↓
Step 5: ファイル保存 or 内容返却
  ├─ return_content=False → ファイル保存
  └─ return_content=True → 内容を返却
```


### 実装詳細

#### ローカルパス決定

```python
if not local_path:
    filename = key.split('/')[-1]
    local_path = filename

# パスを正規化（絶対パスに変換）
import os
local_path = os.path.abspath(local_path)

# ディレクトリが存在しない場合は作成
local_dir = os.path.dirname(local_path)
if local_dir and not os.path.exists(local_dir):
    os.makedirs(local_dir, exist_ok=True)
```

#### S3からダウンロード

```python
# S3オブジェクトの存在確認
try:
    head_response = self.s3_client.head_object(Bucket=bucket, Key=key)
    s3_file_size = head_response.get('ContentLength', 0)
except self.s3_client.exceptions.NoSuchKey:
    return {
        "success": False,
        "error": f"File not found in S3: {s3_path}",
        "bucket": bucket,
        "key": key
    }

# ダウンロード
response = self.s3_client.get_object(Bucket=bucket, Key=key)
content = response['Body'].read()
```

#### モード1: ファイル保存

```python
if not return_content:
    with open(local_path, 'wb') as f:
        f.write(content)
    
    file_size = os.path.getsize(local_path)
    
    # 行数カウント
    with open(local_path, 'r', encoding='utf-8') as f:
        line_count = sum(1 for _ in f)
    
    return {
        "success": True,
        "s3_path": s3_path,
        "local_path": local_path,
        "file_size_bytes": file_size,
        "file_size_mb": round(file_size / (1024 * 1024), 2),
        "line_count": line_count,
        "message": f"Successfully downloaded CSV to {local_path}"
    }
```

#### モード2: 内容返却

```python
if return_content:
    csv_content = content.decode('utf-8')
    line_count = len(csv_content.split('\n'))
    
    return {
        "success": True,
        "s3_path": s3_path,
        "content": csv_content,
        "file_size_bytes": len(content),
        "file_size_mb": round(len(content) / (1024 * 1024), 2),
        "line_count": line_count,
        "message": f"Successfully retrieved CSV content"
    }
```

### レスポンス例

**ファイル保存モード**:
```json
{
  "success": true,
  "s3_path": "s3://estat-data-lake/csv/0003458339_20260115_144500.csv",
  "s3_bucket": "estat-data-lake",
  "s3_key": "csv/0003458339_20260115_144500.csv",
  "local_path": "/Users/user/Downloads/0003458339_20260115_144500.csv",
  "file_size_bytes": 12458960,
  "file_size_mb": 11.88,
  "line_count": 47001,
  "processing_time_seconds": 2.34,
  "message": "Successfully downloaded CSV to /Users/user/Downloads/0003458339_20260115_144500.csv (11.88 MB)"
}
```

**内容返却モード**:
```json
{
  "success": true,
  "s3_path": "s3://estat-data-lake/csv/0003458339_20260115_144500.csv",
  "content": "@area,@time,@cat01,$,@unit\n01000,2020,A1101,5224614,人\n...",
  "file_size_bytes": 12458960,
  "file_size_mb": 11.88,
  "line_count": 47001,
  "message": "Successfully retrieved CSV content (11.88 MB, 47001 lines)"
}
```

### エラーハンドリング

**ファイル未存在**:
```json
{
  "success": false,
  "error": "File not found in S3: s3://estat-data-lake/csv/invalid.csv",
  "bucket": "estat-data-lake",
  "key": "csv/invalid.csv"
}
```

**権限エラー**:
```json
{
  "success": false,
  "error": "Permission denied: Cannot write to /protected/path/file.csv",
  "local_path": "/protected/path/file.csv"
}
```


---

## ツール9: get_estat_table_url

### 概要
統計表IDからe-Stat公式ホームページの統計表ページURLを生成する。

### メソッドシグネチャ

```python
def get_estat_table_url(
    self,
    dataset_id: str
) -> Dict[str, Any]
```

### パラメータ詳細

| パラメータ | 型 | デフォルト | 必須 | 説明 |
|-----------|-----|-----------|------|------|
| dataset_id | str | - | ✓ | 統計表ID（例: 0002112323） |

### 処理フロー

```
Step 1: 統計表IDのバリデーション
  ├─ 空チェック
  └─ 数字抽出
  ↓
Step 2: URL生成
  https://www.e-stat.go.jp/dbview?sid={dataset_id}
  ↓
Step 3: レスポンス返却
```

### 実装詳細

#### Step 1: バリデーション

```python
# 統計表IDのバリデーション
if not dataset_id:
    return {
        "success": False,
        "error": "dataset_id is required"
    }

# 統計表IDから数字以外を除去（念のため）
clean_id = ''.join(filter(str.isdigit, str(dataset_id)))

if not clean_id:
    return {
        "success": False,
        "error": f"Invalid dataset_id: {dataset_id}. Must contain numeric characters."
    }
```

#### Step 2: URL生成

```python
# e-StatホームページのURLを生成
table_url = f"https://www.e-stat.go.jp/dbview?sid={clean_id}"

logger.info(f"Generated e-Stat URL for dataset {clean_id}")
```

### レスポンス例

**成功時**:
```json
{
  "success": true,
  "dataset_id": "0002112323",
  "original_dataset_id": "0002112323",
  "table_url": "https://www.e-stat.go.jp/dbview?sid=0002112323",
  "processing_time_seconds": 0.0001,
  "message": "統計表のホームページURL: https://www.e-stat.go.jp/dbview?sid=0002112323"
}
```

**エラー時**:
```json
{
  "success": false,
  "error": "dataset_id is required"
}
```

### 使用例

**基本的な使用**:
```python
# 統計表IDからURL生成
result = await get_estat_table_url(dataset_id="0003458339")

# ブラウザで開く
print(result["table_url"])
# → https://www.e-stat.go.jp/dbview?sid=0003458339
```

**検索結果と組み合わせ**:
```python
# 1. データセット検索
search_result = await search_estat_data(query="北海道 人口")

# 2. 最上位のデータセットIDを取得
dataset_id = search_result["results"][0]["dataset_id"]

# 3. e-StatホームページのURLを生成
url_result = await get_estat_table_url(dataset_id=dataset_id)

# 4. URLを表示
print(f"詳細はこちら: {url_result['table_url']}")
```

### 特徴

1. **高速**: API呼び出し不要、即座にURL生成
2. **シンプル**: 統計表IDのみで動作
3. **公式リンク**: e-Stat公式サイトへの直接リンク
4. **バリデーション**: 不正なIDを検出

### 用途

1. **データ確認**: e-Stat公式サイトで統計表の詳細を確認
2. **レポート作成**: 統計表へのリンクを含むレポート作成
3. **データソース明示**: データの出典を明確化
4. **手動ダウンロード**: e-Statから直接ダウンロードしたい場合

### e-Stat統計表ページの情報

生成されたURLで表示される情報:
- 統計表の正式名称
- 調査年月日
- 公開日
- 提供統計名
- 提供分類
- 表章項目
- 分類事項
- データのプレビュー
- Excel/CSV形式でのダウンロードオプション

---

## ツール10: transform_to_parquet

### 概要
JSONデータをParquet形式に変換してS3に保存する。データサイズを50-80%削減。

### メソッドシグネチャ

```python
async def transform_to_parquet(
    self,
    s3_json_path: str,
    data_type: str,
    output_prefix: Optional[str] = None
) -> Dict[str, Any]
```

### パラメータ詳細

| パラメータ | 型 | デフォルト | 必須 | 説明 |
|-----------|-----|-----------|------|------|
| s3_json_path | str | - | ✓ | S3上のJSONファイルパス |
| data_type | str | - | ✓ | データ種別 |
| output_prefix | str | None | - | 出力先プレフィックス |

### データ種別

| data_type | スキーマ | 用途 |
|-----------|---------|------|
| population | year, region_code, region_name, category | 人口統計 |
| economy | year, quarter, region_code, indicator | 経済統計 |
| education | year, region_code, school_type, metric | 教育統計 |
| generic | year, region_code, category | 汎用 |

### 処理フロー

```
Step 1: S3からJSON読み込み
  get_object()
  ↓
Step 2: データ抽出
  GET_STATS_DATA.STATISTICAL_DATA.DATA_INF.VALUE
  ↓
Step 3: レコード変換
  ├─ 値の正規化（'-' → None）
  ├─ 数値変換
  └─ data_type別フィールド追加
  ↓
Step 4: DataFrame作成
  pd.DataFrame(records)
  ↓
Step 5: Parquet変換
  pa.Table.from_pandas(df)
  ↓
Step 6: S3保存
  put_object()
```

### 実装詳細

#### Step 2-3: データ抽出と変換

```python
stats_data = data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {})
values = stats_data.get('DATA_INF', {}).get('VALUE', [])

records = []
dataset_id = key.split('/')[-1].split('_')[0]

for value in values:
    # 値を取得（'-'や空文字の場合はNoneに変換）
    raw_value = value.get('$', '0')
    try:
        numeric_value = float(raw_value) if raw_value and raw_value != '-' else None
    except (ValueError, TypeError):
        numeric_value = None
    
    record = {
        'stats_data_id': dataset_id,
        'value': numeric_value,
        'unit': value.get('@unit', ''),
        'updated_at': datetime.now()
    }
    
    # データ種別ごとのフィールド追加
    if data_type == 'population':
        record['year'] = int(value.get('@time', '2020'))
        record['region_code'] = value.get('@cat01', '')
        record['region_name'] = ''
        record['category'] = value.get('@cat02', '')
    
    records.append(record)
```


#### Step 4-5: DataFrame → Parquet変換

```python
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from io import BytesIO

df = pd.DataFrame(records)
table = pa.Table.from_pandas(df)

# Parquetに変換
buffer = BytesIO()
pq.write_table(table, buffer)
buffer.seek(0)
```

#### Step 6: S3保存

```python
if output_prefix:
    parquet_key = f"{output_prefix}/{data_type}/{dataset_id}_{timestamp}.parquet"
else:
    parquet_key = key.replace('raw/data/', 'processed/').replace('.json', '.parquet')

self.s3_client.put_object(
    Bucket=bucket,
    Key=parquet_key,
    Body=buffer.getvalue(),
    ContentType='application/octet-stream'
)

s3_parquet_path = f"s3://{bucket}/{parquet_key}"
```

### スキーマ詳細

#### population スキーマ

```python
{
    'stats_data_id': 'STRING',
    'year': 'INT',
    'region_code': 'STRING',
    'region_name': 'STRING',
    'category': 'STRING',
    'value': 'DOUBLE',
    'unit': 'STRING',
    'updated_at': 'TIMESTAMP'
}
```

#### economy スキーマ

```python
{
    'stats_data_id': 'STRING',
    'year': 'INT',
    'quarter': 'INT',
    'region_code': 'STRING',
    'indicator': 'STRING',
    'value': 'DOUBLE',
    'unit': 'STRING',
    'updated_at': 'TIMESTAMP'
}
```

### レスポンス例

```json
{
  "success": true,
  "source_path": "s3://estat-data-lake/raw/data/0003458339_20260115_144500.json",
  "target_path": "s3://estat-data-lake/processed/0003458339_20260115_145000.parquet",
  "records_processed": 47000,
  "data_type": "population",
  "message": "Successfully converted 47000 records to Parquet format"
}
```

### Parquetの利点

1. **データ圧縮**: 50-80%のサイズ削減
2. **カラムナーストレージ**: 列単位の高速読み込み
3. **スキーマ保持**: データ型情報を保持
4. **高速クエリ**: Athenaでの分析が高速

### 必要ライブラリ

```python
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
```

---

## ツール11: load_to_iceberg

### 概要
ParquetデータをAthena Icebergテーブルに投入する。

### メソッドシグネチャ

```python
async def load_to_iceberg(
    self,
    table_name: str,
    s3_parquet_path: str,
    create_if_not_exists: bool = True
) -> Dict[str, Any]
```

### パラメータ詳細

| パラメータ | 型 | デフォルト | 必須 | 説明 |
|-----------|-----|-----------|------|------|
| table_name | str | - | ✓ | テーブル名 |
| s3_parquet_path | str | - | ✓ | S3上のParquetファイルパス |
| create_if_not_exists | bool | True | - | テーブル自動作成 |


### 処理フロー

```
Step 1: データベース存在確認/作成
  ├─ Glue.get_database()
  └─ 存在しない場合 → CREATE DATABASE
  ↓
Step 2: Icebergテーブル作成
  CREATE TABLE IF NOT EXISTS ... TBLPROPERTIES ('table_type'='ICEBERG')
  ↓
Step 3: 外部テーブル作成
  CREATE EXTERNAL TABLE ... STORED AS PARQUET
  ↓
Step 4: データ投入
  INSERT INTO {table_name} SELECT * FROM {external_table}
  ↓
Step 5: レコード数確認
  SELECT COUNT(*) FROM {table_name}
  ↓
Step 6: 外部テーブル削除
  DROP TABLE {external_table}
```

### 実装詳細

#### Step 1: データベース作成

```python
database = 'estat_db'
output_location = f's3://{S3_BUCKET}/athena-results/'

# データベース存在確認
try:
    import boto3
    glue_client = boto3.client('glue', region_name=AWS_REGION)
    glue_client.get_database(Name=database)
except Exception:
    # データベース作成
    create_db_query = f"CREATE DATABASE IF NOT EXISTS {database}"
    await self._execute_athena_query(create_db_query, database="default", output_location=output_location)
```

#### Step 2: Icebergテーブル作成

```python
create_table_query = f"""
CREATE TABLE IF NOT EXISTS {database}.{table_name} (
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
"""

await self._execute_athena_query(create_table_query, database=database, output_location=output_location)
```

#### Step 3: 外部テーブル作成

```python
external_table = f"{table_name}_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
parquet_dir = parquet_key.rsplit("/", 1)[0] + "/"

create_external_query = f"""
CREATE EXTERNAL TABLE IF NOT EXISTS {database}.{external_table} (
    stats_data_id STRING,
    year INT,
    region_code STRING,
    category STRING,
    value DOUBLE,
    unit STRING,
    updated_at TIMESTAMP
)
STORED AS PARQUET
LOCATION 's3://{bucket}/{parquet_dir}'
"""

await self._execute_athena_query(create_external_query, database=database, output_location=output_location)
```

#### Step 4: データ投入

```python
insert_query = f"""
INSERT INTO {database}.{table_name}
SELECT * FROM {database}.{external_table}
"""

# Athenaワークグループを使用してクエリ実行
await self._execute_athena_query(insert_query, database=database, output_location=output_location)
```

**重要な変更点（2026年1月14日）**:
- `ResultConfiguration`の代わりに`WorkGroup='estat-mcp-workgroup'`を明示的に指定
- Athenaワークグループで出力場所を一元管理
- `s3-tables-temp-data-*`バケットへの不要な参照を削除

#### Step 5: レコード数確認

```python
count_query = f"SELECT COUNT(*) FROM {database}.{table_name}"
count_result = await self._execute_athena_query(count_query, database=database, output_location=output_location)

if count_result[0] and count_result[1]:
    record_count = count_result[1][0][0]
```


### Athenaクエリ実行ヘルパー

```python
async def _execute_athena_query(
    self,
    query: str,
    database: str,
    output_location: str
) -> tuple:
    
    # S3出力ディレクトリの確認
    if not self.s3_client:
        return (False, "S3 client not available")
    
    try:
        self.s3_client.put_object(
            Bucket=S3_BUCKET,
            Key='athena-results/.keep',
            Body=b''
        )
        logger.info(f"Athena output location ready: {output_location}")
    except Exception as e:
        logger.error(f"Failed to create athena-results directory: {e}")
        return (False, f"Failed to setup Athena output location: {str(e)}")
    
    # クエリ実行（ワークグループを明示的に指定）
    try:
        response = self.athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': database},
            WorkGroup='estat-mcp-workgroup'
        )
    except Exception as e:
        logger.error(f"Failed to start query execution: {e}")
        return (False, f"Failed to start query: {str(e)}")
    
    query_execution_id = response['QueryExecutionId']
    
    # 完了待機（最大60秒）
    max_wait = 60
    wait_interval = 2
    elapsed = 0
    
    while elapsed < max_wait:
        response = self.athena_client.get_query_execution(
            QueryExecutionId=query_execution_id
        )
        
        status = response['QueryExecution']['Status']['State']
        
        if status == 'SUCCEEDED':
            # 結果取得
            result_response = self.athena_client.get_query_results(
                QueryExecutionId=query_execution_id
            )
            
            rows = result_response['ResultSet']['Rows']
            if len(rows) > 1:
                data_rows = []
                for row in rows[1:]:  # ヘッダー除外
                    data_row = [col.get('VarCharValue', '') for col in row['Data']]
                    data_rows.append(data_row)
                return (True, data_rows)
            else:
                return (True, [])
        
        elif status in ['FAILED', 'CANCELLED']:
            error_msg = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
            return (False, error_msg)
        
        time.sleep(wait_interval)
        elapsed += wait_interval
    
    return (False, "Query timeout")
```

### レスポンス例

```json
{
  "success": true,
  "table_name": "population_data",
  "database": "estat_db",
  "records_loaded": "47000",
  "source_path": "s3://estat-data-lake/processed/0003458339_20260115_145000.parquet",
  "table_location": "s3://estat-data-lake/iceberg-tables/population_data/",
  "message": "Successfully loaded data to table population_data (47000 records)"
}
```

### Icebergテーブルの特徴

1. **ACID保証**: トランザクション対応
2. **タイムトラベル**: 過去のスナップショット参照
3. **スキーマ進化**: カラム追加・削除が容易
4. **パーティション管理**: 自動パーティション最適化

### エラーハンドリング

**データベース作成失敗**:
```json
{
  "success": false,
  "error": "Failed to create database: Access Denied"
}
```

**テーブル作成失敗**:
```json
{
  "success": false,
  "error": "Failed to create Iceberg table: Invalid location"
}
```

**データ投入失敗**:
```json
{
  "success": false,
  "error": "Failed to insert data: Schema mismatch"
}
```

---

## ツール12: analyze_with_athena

### 概要
Athenaで統計分析を実行する。基本統計、高度分析、カスタムクエリに対応。

### メソッドシグネチャ

```python
async def analyze_with_athena(
    self,
    table_name: str,
    analysis_type: str = "basic",
    custom_query: Optional[str] = None
) -> Dict[str, Any]
```

### パラメータ詳細

| パラメータ | 型 | デフォルト | 必須 | 説明 |
|-----------|-----|-----------|------|------|
| table_name | str | - | ✓ | テーブル名 |
| analysis_type | str | "basic" | - | 分析タイプ |
| custom_query | str | None | - | カスタムSQLクエリ |

### 分析タイプ

| analysis_type | 内容 |
|--------------|------|
| basic | 基本統計（レコード数、平均、最小、最大、合計、年別集計） |
| advanced | 高度分析（地域別、カテゴリ別、時系列トレンド） |
| custom | カスタムSQLクエリ実行 |


### 処理フロー

```
Step 1: 分析タイプ判定
  ├─ basic → 基本統計実行
  ├─ advanced → 高度分析実行
  └─ custom → カスタムクエリ実行
  ↓
Step 2: SQLクエリ実行
  _execute_athena_query()
  ↓
Step 3: 結果パース
  ↓
Step 4: 結果返却
```

### 実装詳細

#### basic分析

**1. レコード数**:
```python
count_query = f"SELECT COUNT(*) as total_records FROM {database}.{table_name}"
count_result = await self._execute_athena_query(count_query, database, output_location)

results["total_records"] = int(count_result[1][0][0])
```

**2. 基本統計**:
```python
stats_query = f"""
SELECT 
    COUNT(*) as count,
    AVG(value) as avg_value,
    MIN(value) as min_value,
    MAX(value) as max_value,
    SUM(value) as sum_value
FROM {database}.{table_name}
WHERE value IS NOT NULL
"""

stats_result = await self._execute_athena_query(stats_query, database, output_location)

results["statistics"] = {
    "count": int(row[0]),
    "avg_value": float(row[1]),
    "min_value": float(row[2]),
    "max_value": float(row[3]),
    "sum_value": float(row[4])
}
```

**3. 年別集計**:
```python
year_query = f"""
SELECT 
    year,
    COUNT(*) as count,
    AVG(value) as avg_value
FROM {database}.{table_name}
WHERE value IS NOT NULL
GROUP BY year
ORDER BY year
LIMIT 10
"""

year_result = await self._execute_athena_query(year_query, database, output_location)

results["by_year"] = [
    {
        "year": int(row[0]),
        "count": int(row[1]),
        "avg_value": float(row[2])
    }
    for row in year_result[1]
]
```

#### advanced分析

**1. 地域別集計**:
```python
region_query = f"""
SELECT 
    region_code,
    COUNT(*) as count,
    AVG(value) as avg_value,
    SUM(value) as sum_value
FROM {database}.{table_name}
WHERE value IS NOT NULL
GROUP BY region_code
ORDER BY sum_value DESC
LIMIT 10
"""

region_result = await self._execute_athena_query(region_query, database, output_location)
results["by_region"] = region_result[1]
```

**2. カテゴリ別集計**:
```python
category_query = f"""
SELECT 
    category,
    COUNT(*) as count,
    AVG(value) as avg_value
FROM {database}.{table_name}
WHERE value IS NOT NULL AND category IS NOT NULL
GROUP BY category
ORDER BY count DESC
LIMIT 10
"""

category_result = await self._execute_athena_query(category_query, database, output_location)
results["by_category"] = category_result[1]
```

**3. 時系列トレンド**:
```python
trend_query = f"""
SELECT 
    year,
    AVG(value) as avg_value,
    MIN(value) as min_value,
    MAX(value) as max_value
FROM {database}.{table_name}
WHERE value IS NOT NULL
GROUP BY year
ORDER BY year
"""

trend_result = await self._execute_athena_query(trend_query, database, output_location)
results["trend"] = trend_result[1]
```


#### custom分析

```python
if custom_query:
    query_result = await self._execute_athena_query(custom_query, database, output_location)
    results["custom_query"] = {
        "success": query_result[0],
        "result": query_result[1] if query_result[0] else None,
        "error": query_result[1] if not query_result[0] else None
    }
```

### レスポンス例

#### basic分析

```json
{
  "success": true,
  "table_name": "population_data",
  "database": "estat_db",
  "analysis_type": "basic",
  "results": {
    "total_records": 47000,
    "statistics": {
      "count": 47000,
      "avg_value": 2654321.5,
      "min_value": 56789,
      "max_value": 13960000,
      "sum_value": 124753310500
    },
    "by_year": [
      {"year": 2020, "count": 4700, "avg_value": 2654321.5},
      {"year": 2021, "count": 4700, "avg_value": 2648900.2},
      {"year": 2022, "count": 4700, "avg_value": 2643500.8}
    ]
  },
  "message": "Successfully analyzed table population_data"
}
```

#### advanced分析

```json
{
  "success": true,
  "table_name": "population_data",
  "database": "estat_db",
  "analysis_type": "advanced",
  "results": {
    "by_region": [
      ["13000", "10000", "13960000.0", "139600000000.0"],
      ["27000", "10000", "8839000.0", "88390000000.0"],
      ["01000", "10000", "5224614.0", "52246140000.0"]
    ],
    "by_category": [
      ["総人口", "47000", "2654321.5"],
      ["男性", "47000", "1298765.2"],
      ["女性", "47000", "1355556.3"]
    ],
    "trend": [
      ["2020", "2654321.5", "56789.0", "13960000.0"],
      ["2021", "2648900.2", "56234.0", "13920000.0"],
      ["2022", "2643500.8", "55678.0", "13880000.0"]
    ]
  },
  "message": "Successfully analyzed table population_data"
}
```

#### custom分析

```json
{
  "success": true,
  "table_name": "population_data",
  "database": "estat_db",
  "analysis_type": "custom",
  "results": {
    "custom_query": {
      "success": true,
      "result": [
        ["北海道", "5224614"],
        ["青森県", "1237984"],
        ["岩手県", "1210534"]
      ],
      "error": null
    }
  },
  "message": "Successfully analyzed table population_data"
}
```

### カスタムクエリ例

**地域別人口ランキング**:
```sql
SELECT region_code, SUM(value) as total_population
FROM estat_db.population_data
WHERE category = '総人口'
GROUP BY region_code
ORDER BY total_population DESC
LIMIT 10
```

**年度別増減率**:
```sql
SELECT 
    year,
    SUM(value) as total,
    LAG(SUM(value)) OVER (ORDER BY year) as prev_year,
    (SUM(value) - LAG(SUM(value)) OVER (ORDER BY year)) / LAG(SUM(value)) OVER (ORDER BY year) * 100 as growth_rate
FROM estat_db.population_data
GROUP BY year
ORDER BY year
```

### パフォーマンス

- **基本統計**: 2-5秒
- **高度分析**: 5-10秒
- **カスタムクエリ**: クエリ複雑度による

### エラーハンドリング

**テーブル未存在**:
```json
{
  "success": false,
  "error": "Table not found: estat_db.invalid_table"
}
```

**SQLエラー**:
```json
{
  "success": false,
  "error": "SYNTAX_ERROR: line 1:8: Column 'invalid_column' cannot be resolved"
}
```

---

## 付録: 共通ヘルパーメソッド

### _call_estat_api

e-Stat APIを呼び出す（リトライ付き）

```python
@retry_with_backoff(max_retries=3, base_delay=1.0)
async def _call_estat_api(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{self.base_url}/{endpoint}"
    
    try:
        response = self.session.get(url, params=params, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        raise RetryableError("e-Stat API request timed out")
    except requests.exceptions.RequestException as e:
        if response.status_code in [429, 503, 504]:
            raise RetryableError(f"e-Stat API error: {e}")
        raise EStatError(f"e-Stat API error: {e}")
```

### _get_metadata_quick

メタデータを高速取得

```python
async def _get_metadata_quick(self, dataset_id: str) -> Dict[str, Any]:
    params = {"appId": self.app_id, "statsDataId": dataset_id}
    meta_data = await self._call_estat_api("getMetaInfo", params)
    
    # 総レコード数計算
    # カテゴリ情報抽出
    # 10万件判定
    
    return {
        "total_records": total_records,
        "total_records_formatted": f"{total_records:,}件",
        "requires_filtering": total_records >= LARGE_DATASET_THRESHOLD,
        "categories": categories
    }
```

### _extract_value

フィールドから値を抽出

```python
def _extract_value(self, field: Any) -> str:
    if isinstance(field, dict):
        return field.get('$', '')
    elif isinstance(field, str):
        return field
    else:
        return ''
```

---

## まとめ

### ツール分類

**検索系**:
- search_estat_data
- apply_keyword_suggestions

**取得系**:
- fetch_dataset_auto
- fetch_large_dataset_complete
- fetch_dataset_filtered

**変換・保存系**:
- save_dataset_as_csv
- save_metadata_as_csv
- transform_to_parquet

**ダウンロード・URL生成系**:
- get_csv_download_url
- get_estat_table_url

**分析系**:
- load_to_iceberg
- analyze_with_athena

### 典型的なワークフロー

**パターン1: CSV取得とダウンロード**
```
search_estat_data 
  → fetch_dataset_auto 
  → save_dataset_as_csv 
  → get_csv_download_url
```

**パターン2: メタデータ確認とフィルタ取得**
```
search_estat_data 
  → save_metadata_as_csv 
  → get_csv_download_url (メタデータCSV)
  → fetch_dataset_filtered (確認したコードでフィルタ)
  → save_dataset_as_csv
```

**パターン3: 大規模データ分析**
```
search_estat_data 
  → fetch_dataset_filtered 
  → transform_to_parquet 
  → load_to_iceberg 
  → analyze_with_athena
```

**パターン4: データソース確認**
```
search_estat_data 
  → get_estat_table_url (e-Stat公式サイトで詳細確認)
  → fetch_dataset_auto
```

---

## 修正履歴

### v2.3.0 (2026年1月16日)

**ツール構成の修正**:
1. **get_estat_table_url追加**
   - 統計表IDからe-Stat公式ホームページURLを生成
   - API呼び出し不要の高速処理
   - データソース確認に便利

2. **save_metadata_as_csv追加**
   - データセットのメタデータ（カテゴリ情報）をCSV保存
   - フィルタ条件の確認に使用
   - データ構造の理解を支援

3. **ツール番号の再編成**
   - 全12ツールに整理
   - 機能別に分類を明確化

### v2.2.0 (2026年1月16日)

**Athenaツールの修正**:
1. **Athenaワークグループの導入**
   - `estat-mcp-workgroup`を作成し、出力先を`s3://estat-data-lake/athena-results/`に統一
   - `ResultConfiguration`の代わりに`WorkGroup`パラメータを使用
   - `s3-tables-temp-data-*`バケットへの不要な参照を削除

2. **エラーハンドリングの強化**
   - S3クライアントの存在チェックを追加
   - Athena出力ディレクトリの事前作成
   - 詳細なエラーメッセージの提供

**download_csv_from_s3の修正**:
1. **ダウンロード方法の変更**
   - `download_file`から`get_object`メソッドに変更
   - 一時ファイル作成時のエラーを解消

2. **ディレクトリ管理の改善**
   - 保存先ディレクトリの自動作成
   - サブディレクトリへの保存に対応

### v2.1.0 (2026年1月15日)

**初版リリース**:
- 全11ツールの詳細設計を完成
- MCP streamable-httpプロトコル対応
- AWS ECS Fargateデプロイメント対応

---

**作成日**: 2026年1月15日  
**最終更新**: 2026年1月16日  
**バージョン**: v2.3.0  
**作成者**: Kiro AI Assistant
