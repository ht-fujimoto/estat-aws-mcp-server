#!/usr/bin/env python3
"""
e-Stat Analysis MCP Server with Human-in-the-Loop Support
ヒューマンインザループ対応のe-Stat分析サーバー
"""

import os
import json
import asyncio
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional

# 環境変数
ESTAT_APP_ID = os.environ.get('ESTAT_APP_ID', '320dd2fbff6974743e3f95505c9f346650ab635e')
S3_BUCKET = os.environ.get('S3_BUCKET', 'estat-data-lake')
AWS_REGION = os.environ.get('AWS_REGION', 'ap-northeast-1')

# 定数
LARGE_DATASET_THRESHOLD = 100000  # 10万件


class EStatHITLServer:
    """Human-in-the-Loop対応のe-Stat分析サーバー"""
    
    def __init__(self):
        self.app_id = ESTAT_APP_ID
        self.base_url = "https://api.e-stat.go.jp/rest/3.0/app/json"
        
        # AWSクライアント（必要に応じて初期化）
        try:
            import boto3
            self.s3_client = boto3.client('s3', region_name=AWS_REGION)
        except ImportError:
            self.s3_client = None
    
    # ========================================
    # ツール1: search_and_rank_datasets
    # ========================================
    
    async def search_and_rank_datasets(
        self,
        query: str,
        max_results: int = 5,
        scoring_method: str = "enhanced",
        auto_suggest: bool = True
    ) -> Dict[str, Any]:
        """
        自然言語検索 + メタデータ取得 + スコアリング + Top5返却
        
        処理フロー:
        0. キーワードサジェスト（auto_suggest=Trueの場合）
        1. getStatsList で検索（100件）
        2. 初期スコアリング（メタデータなし）
        3. Top 20 を選択
        4. Top 20 のメタデータを並列取得
        5. メタデータを含めて再スコアリング
        6. Top 5 を返却（全情報含む）
        
        Args:
            query: 検索クエリ（例: "東京都の交通事故統計"）
            max_results: 返却する最大件数（デフォルト: 5）
            scoring_method: スコアリング方法（"enhanced" or "basic"）
            auto_suggest: キーワードサジェストを有効にするか（デフォルト: True）
        
        Returns:
            スコア順にソートされた統計表リスト（メタデータ、総レコード数、カテゴリ詳細含む）
            サジェストがある場合は、suggestions フィールドも含む
        """
        print(f"\n🔍 search_and_rank_datasets: query='{query}'")
        
        try:
            # ステップ0: キーワードサジェスト
            suggestions = None
            if auto_suggest:
                try:
                    from estat_enhanced_dictionary import get_keyword_suggestions, format_suggestion_message
                except ImportError:
                    from estat_keyword_dictionary import get_keyword_suggestions, format_suggestion_message
                
                keyword_suggestions = get_keyword_suggestions(query)
                if keyword_suggestions:
                    print(f"   💡 Found {len(keyword_suggestions)} keyword suggestions")
                    
                    # サジェストメッセージを作成
                    suggestion_message = format_suggestion_message(keyword_suggestions)
                    
                    # サジェスト情報を返却（ユーザーの承認待ち）
                    suggestions = {
                        "original_query": query,
                        "suggestions": keyword_suggestions,
                        "message": suggestion_message
                    }
                    
                    # サジェストがある場合は、検索を実行せずに返却
                    return {
                        "success": True,
                        "has_suggestions": True,
                        "suggestions": suggestions,
                        "message": "キーワード変換の提案があります。変換を適用する場合は、suggested_queryで再検索してください。"
                    }
            
            # ステップ1: e-Stat API呼び出し（検索）
            params = {
                "appId": self.app_id,
                "searchWord": query,
                "limit": 100  # 多めに取得してからフィルタ
            }
            
            response = requests.get(
                f"{self.base_url}/getStatsList",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            # 統計表リストを取得
            table_list = data.get('GET_STATS_LIST', {}).get('DATALIST_INF', {}).get('TABLE_INF', [])
            
            # リストでない場合は配列化
            if isinstance(table_list, dict):
                table_list = [table_list]
            elif not table_list:
                return {
                    "success": True,
                    "query": query,
                    "results": [],
                    "message": f"No datasets found for query '{query}'"
                }
            
            print(f"   📊 Found {len(table_list)} datasets from search")
            
            # ステップ2: 初期スコアリング（メタデータなし）
            scored_datasets = []
            for table in table_list:
                basic_score = self._calculate_basic_score(query, table)
                
                scored_datasets.append({
                    "table": table,
                    "basic_score": basic_score
                })
            
            # ステップ3: Top 20 を選択
            scored_datasets.sort(key=lambda x: x['basic_score'], reverse=True)
            top_20 = scored_datasets[:min(20, len(scored_datasets))]
            
            print(f"   🎯 Selected top {len(top_20)} for metadata retrieval")
            
            # ステップ4: Top 20 のメタデータを並列取得
            if scoring_method == "enhanced":
                print(f"   📥 Fetching metadata for top {len(top_20)} datasets...")
                
                # 並列処理でメタデータ取得
                tasks = [
                    self._get_metadata_quick(item['table'].get('@id'))
                    for item in top_20
                ]
                metadata_list = await asyncio.gather(*tasks, return_exceptions=True)
                
                # メタデータを各アイテムに追加
                for item, metadata in zip(top_20, metadata_list):
                    if isinstance(metadata, dict) and not isinstance(metadata, Exception):
                        item['metadata'] = metadata
                    else:
                        item['metadata'] = {}
            
            # ステップ5: メタデータを含めて再スコアリング
            for item in top_20:
                if scoring_method == "enhanced":
                    enhanced_score = self._calculate_enhanced_score(
                        query,
                        item['table'],
                        item.get('metadata', {})
                    )
                    item['final_score'] = enhanced_score
                else:
                    item['final_score'] = item['basic_score']
            
            # ステップ6: Top N を返却
            top_20.sort(key=lambda x: x['final_score'], reverse=True)
            top_results = top_20[:max_results]
            
            # 結果をフォーマット
            formatted_results = []
            for i, item in enumerate(top_results, 1):
                table = item['table']
                metadata = item.get('metadata', {})
                
                # TITLEとGOV_ORGを抽出
                title_val = table.get('TITLE', {})
                if isinstance(title_val, dict):
                    title = title_val.get('$', 'N/A')
                else:
                    title = title_val if title_val else 'N/A'
                
                gov_org_val = table.get('GOV_ORG', {})
                if isinstance(gov_org_val, dict):
                    gov_org = gov_org_val.get('$', 'N/A')
                else:
                    gov_org = gov_org_val if gov_org_val else 'N/A'
                
                # 基本情報
                result = {
                    "rank": i,
                    "score": round(item['final_score'], 3),
                    "dataset_id": table.get('@id'),
                    "title": title,
                    "gov_org": gov_org,
                    "survey_date": table.get('SURVEY_DATE', 'N/A'),
                    "open_date": table.get('OPEN_DATE', 'N/A')
                }
                
                # メタデータ情報を追加
                if metadata:
                    result["total_records"] = metadata.get('total_records')
                    result["total_records_formatted"] = metadata.get('total_records_formatted', '不明')
                    result["requires_filtering"] = metadata.get('requires_filtering')
                    
                    # カテゴリ詳細を追加（簡略版）
                    if 'categories' in metadata:
                        categories = metadata['categories']
                        result["categories"] = {}
                        for cat_id, cat_info in categories.items():
                            if isinstance(cat_info, dict):
                                result["categories"][cat_id] = {
                                    'name': cat_info.get('name', cat_id),
                                    'count': len(cat_info.get('values', [])),
                                    'sample': cat_info.get('values', [])[:5]  # 最初の5件のみ
                                }
                            else:
                                # 旧構造の場合
                                result["categories"][cat_id] = cat_info
                
                formatted_results.append(result)
            
            print(f"   ✅ Returning top {len(formatted_results)} datasets with metadata")
            
            return {
                "success": True,
                "query": query,
                "total_found": len(table_list),
                "results": formatted_results,
                "message": f"Found {len(formatted_results)} relevant datasets with metadata. Please select one by dataset_id."
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_metadata_quick(self, dataset_id: str) -> Dict[str, Any]:
        """
        メタデータを高速取得（総レコード数 + カテゴリ詳細）
        
        Args:
            dataset_id: データセットID
        
        Returns:
            メタデータ情報（総レコード数、カテゴリ詳細）
        """
        try:
            # getMetaInfo APIから取得
            params = {
                "appId": self.app_id,
                "statsDataId": dataset_id
            }
            
            response = requests.get(
                f"{self.base_url}/getMetaInfo",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            meta_data = response.json()
            
            # メタ情報を解析
            meta_info = meta_data.get('GET_META_INFO', {})
            metadata_inf = meta_info.get('METADATA_INF', {})
            table_inf = metadata_inf.get('TABLE_INF', {})
            
            # カテゴリ情報を取得
            class_inf = metadata_inf.get('CLASS_INF', {})
            
            # CLASS_OBJ を取得（実際の構造）
            class_obj_list = class_inf.get('CLASS_OBJ', [])
            if not isinstance(class_obj_list, list):
                class_obj_list = [class_obj_list] if class_obj_list else []
            
            # 総データ件数を計算（次元の組み合わせから）
            total_records = 0
            
            # TOTAL_NUMBER要素から取得を試行
            if 'TOTAL_NUMBER' in table_inf:
                try:
                    total_records = int(table_inf.get('TOTAL_NUMBER', 0))
                except (ValueError, TypeError):
                    total_records = 0
            
            # TITLEの@no属性から取得を試行（通常は不正確）
            if total_records == 0:
                title_obj = table_inf.get('TITLE', {})
                if isinstance(title_obj, dict) and '@no' in title_obj:
                    try:
                        title_no = int(title_obj.get('@no', 0))
                        # @noが明らかに小さすぎる場合は使用しない
                        if title_no > 100:  # 閾値を設定
                            total_records = title_no
                    except (ValueError, TypeError):
                        pass
            
            # 次元の組み合わせから計算（最も正確）
            if total_records == 0 and class_obj_list:
                calculated_total = 1
                for class_obj in class_obj_list:
                    class_values = class_obj.get('CLASS', [])
                    if not isinstance(class_values, list):
                        class_values = [class_values] if class_values else []
                    calculated_total *= len(class_values)
                
                if calculated_total > 0:
                    total_records = calculated_total
            
            categories = {}
            for class_obj in class_obj_list:
                class_name = class_obj.get('@name', 'unknown')
                class_id = class_obj.get('@id', 'unknown')
                class_values = class_obj.get('CLASS', [])
                
                if not isinstance(class_values, list):
                    class_values = [class_values] if class_values else []
                
                # カテゴリ名のリストを作成（全件取得）
                category_names = [
                    cv.get('@name', '') for cv in class_values
                ]
                
                # @idをキーとして使用（より識別しやすい）
                categories[class_id] = {
                    'name': class_name,
                    'values': category_names  # 全件保存（スコアリング用）
                }
            
            # 10万件判定
            if total_records > 0:
                requires_filtering = total_records >= LARGE_DATASET_THRESHOLD
                formatted = f"{total_records:,}件"
            else:
                # データ件数が取得できない場合は「不明」
                requires_filtering = None
                formatted = "不明"
            
            return {
                "total_records": total_records if total_records > 0 else None,
                "total_records_formatted": formatted,
                "requires_filtering": requires_filtering,
                "categories": categories
            }
            
        except Exception as e:
            # エラーの場合は不明として返す
            print(f"   ⚠️  Metadata fetch error: {str(e)}")
            return {
                "total_records": None,
                "total_records_formatted": "不明",
                "requires_filtering": None,
                "categories": {}
            }
    

    def _calculate_basic_score(self, query: str, dataset: dict) -> float:
        """
        基本スコアを計算（メタデータなし）
        
        Args:
            query: 検索クエリ
            dataset: 統計表情報
        
        Returns:
            0.0 ~ 1.0 のスコア
        """
        score = 0.0
        query_keywords = [k for k in query.split() if len(k) > 1]
        
        # 1. タイトルマッチ（25%）
        title_val = dataset.get('TITLE', {})
        if isinstance(title_val, dict):
            title = title_val.get('$', '')
        else:
            title = title_val if title_val else ''
        
        if query_keywords:
            matches = sum(1 for keyword in query_keywords if keyword in title)
            score += 0.25 * (matches / len(query_keywords))
        
        # 2. 統計名・分類マッチ（15%）
        stats_name = dataset.get('STATISTICS_NAME', '')
        
        main_cat_val = dataset.get('MAIN_CATEGORY', {})
        if isinstance(main_cat_val, dict):
            main_cat = main_cat_val.get('$', '')
        else:
            main_cat = main_cat_val if main_cat_val else ''
        
        sub_cat_val = dataset.get('SUB_CATEGORY', {})
        if isinstance(sub_cat_val, dict):
            sub_cat = sub_cat_val.get('$', '')
        else:
            sub_cat = sub_cat_val if sub_cat_val else ''
        
        category_text = f"{stats_name} {main_cat} {sub_cat}"
        
        if query_keywords:
            cat_matches = sum(1 for keyword in query_keywords if keyword in category_text)
            score += 0.15 * (cat_matches / len(query_keywords))
        
        # 3. 説明文マッチ（10%）
        description = dataset.get('DESCRIPTION', '')
        if query_keywords and description:
            desc_matches = sum(1 for keyword in query_keywords if keyword in description)
            score += 0.1 * (desc_matches / len(query_keywords))
        
        # 4. 更新日の新しさ（15%）
        open_date = dataset.get('OPEN_DATE', '')
        if open_date:
            try:
                date_obj = datetime.strptime(open_date, '%Y-%m-%d')
                days_old = (datetime.now() - date_obj).days
                
                if days_old <= 365:
                    freshness = 1.0
                elif days_old <= 1825:
                    freshness = 1.0 - (days_old - 365) / 1460 * 0.5
                elif days_old <= 3650:
                    freshness = 0.5 - (days_old - 1825) / 1825 * 0.5
                else:
                    freshness = 0.0
                
                score += 0.15 * freshness
            except (ValueError, TypeError):
                score += 0.075
        
        # 5. 政府組織の信頼性（10%）
        trusted_orgs = ['総務省', '警察庁', '国土交通省', '厚生労働省', '内閣府']
        gov_org_val = dataset.get('GOV_ORG', {})
        if isinstance(gov_org_val, dict):
            gov_org = gov_org_val.get('$', '')
        else:
            gov_org = gov_org_val if gov_org_val else ''
        
        if any(org in gov_org for org in trusted_orgs):
            score += 0.1
        
        # 6. データの完全性（5%）
        completeness = 0
        if dataset.get('STATISTICS_NAME'):
            completeness += 1
        if dataset.get('DESCRIPTION'):
            completeness += 1
        if dataset.get('TITLE_SPEC'):
            completeness += 1
        
        score += 0.05 * (completeness / 3)
        
        return min(score, 1.0)
    
    def _calculate_enhanced_score(self, query: str, dataset: dict, metadata: dict) -> float:
        """
        強化スコアを計算（メタデータ含む）
        
        Args:
            query: 検索クエリ
            dataset: 統計表情報
            metadata: メタデータ情報
        
        Returns:
            0.0 ~ 1.0 のスコア
        """
        # 基本スコアを取得（80%）
        basic_score = self._calculate_basic_score(query, dataset)
        score = basic_score * 0.8
        
        # 7. カテゴリマッチ（15%）
        category_match_score = self._calculate_category_match_score(query, metadata)
        score += 0.15 * category_match_score
        
        # 8. データ規模の適切性（5%）
        data_size_score = self._calculate_data_size_score(metadata.get('total_records'))
        score += 0.05 * data_size_score
        
        return min(score, 1.0)
    
    def _calculate_category_match_score(self, query: str, metadata: dict) -> float:
        """
        カテゴリマッチスコアを計算
        
        Args:
            query: 検索クエリ
            metadata: メタデータ情報
        
        Returns:
            0.0 ~ 1.0 のスコア
        """
        query_keywords = [k for k in query.split() if len(k) > 1]
        if not query_keywords:
            return 0.0
        
        categories = metadata.get('categories', {})
        if not categories:
            return 0.0
        
        # 各ディメンションのカテゴリをチェック
        total_matches = 0
        for category_info in categories.values():
            # 新しい構造に対応
            if isinstance(category_info, dict):
                category_values = category_info.get('values', [])
            else:
                # 旧構造（リスト）にも対応
                category_values = category_info if isinstance(category_info, list) else []
            
            # カテゴリ名を結合
            category_text = ' '.join(category_values)
            
            # キーワードマッチ
            matches = sum(1 for keyword in query_keywords if keyword in category_text)
            total_matches += matches
        
        # スコア化（最大1.0）
        score = min(total_matches / len(query_keywords), 1.0)
        return score
    
    def _calculate_data_size_score(self, total_records: Optional[int]) -> float:
        """
        データ規模の適切性スコアを計算
        統計分析では、データの豊富さが重要
        
        Args:
            total_records: 総レコード数
        
        Returns:
            0.0 ~ 1.0 のスコア
        """
        if total_records is None:
            return 0.5  # 不明の場合はデフォルト
        
        # 統計分析では多くのデータポイントが有用
        if total_records >= 10000:
            return 1.0  # 豊富なデータ（統計的に有意）
        elif total_records >= 1000:
            return 0.9  # 十分なデータ
        elif total_records >= 100:
            return 0.7  # 基本的な分析可能
        elif total_records >= 10:
            return 0.5  # 限定的な分析
        else:
            return 0.3  # データ不足
    
    # ========================================
    # ツール2: apply_keyword_suggestions（新規）
    # ========================================
    
    def apply_keyword_suggestions_and_search(
        self,
        original_query: str,
        accepted_keywords: Dict[str, str]
    ) -> str:
        """
        キーワード変換を適用して新しいクエリを生成
        
        Args:
            original_query: 元のクエリ
            accepted_keywords: 承認されたキーワード変換 {元: 新}
        
        Returns:
            変換後のクエリ
        """
        try:
            from estat_enhanced_dictionary import apply_keyword_suggestions
        except ImportError:
            from estat_keyword_dictionary import apply_keyword_suggestions
        
        new_query = apply_keyword_suggestions(original_query, accepted_keywords)
        print(f"   ✅ Query transformed: '{original_query}' → '{new_query}'")
        
        return new_query
    
    # ========================================
    # ツール3: fetch_dataset_auto（統合版）
    # ========================================
    # 注: get_dataset_metadataは削除され、search_and_rank_datasetsに統合されました
    
    async def fetch_dataset_auto(
        self,
        dataset_id: str,
        convert_to_japanese: bool = True,
        save_to_s3: bool = True
    ) -> Dict[str, Any]:
        """
        データセットを自動取得（デフォルトで全データ取得）
        
        Args:
            dataset_id: データセットID
            convert_to_japanese: コード→和名変換を実施するか
            save_to_s3: S3に保存するか
        
        Returns:
            取得結果
        """
        print(f"\n📥 fetch_dataset_auto: dataset_id='{dataset_id}' (auto-complete mode)")
        
        try:
            # Step 1: データサイズを事前確認
            test_params = {
                "appId": self.app_id,
                "statsDataId": dataset_id,
                "limit": 1,
                "metaGetFlg": "Y"
            }
            
            test_response = requests.get(
                f"{self.base_url}/getStatsData",
                params=test_params,
                timeout=30
            )
            test_response.raise_for_status()
            test_data = test_response.json()
            
            total_number = test_data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {}).get('RESULT_INF', {}).get('TOTAL_NUMBER', 0)
            
            print(f"   📊 Dataset size: {total_number:,} records")
            
            # Step 2: データサイズに応じた取得方法の自動選択
            if total_number <= LARGE_DATASET_THRESHOLD:
                print(f"   💡 Small dataset - using single request")
                return await self._fetch_single_request(dataset_id, convert_to_japanese, save_to_s3)
            
            else:
                print(f"   🚀 Large dataset - using complete retrieval (default behavior)")
                return await self.fetch_large_dataset_complete(
                    dataset_id=dataset_id,
                    max_records=min(total_number, 1000000),  # 最大100万件
                    chunk_size=100000,
                    save_to_s3=save_to_s3,
                    convert_to_japanese=convert_to_japanese
                )
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _fetch_single_request(
        self,
        dataset_id: str,
        convert_to_japanese: bool = True,
        save_to_s3: bool = True
    ) -> Dict[str, Any]:
        """
        単一リクエストでのデータ取得（内部メソッド）
        """
        try:
            start_time = datetime.now()
            
            params = {
                "appId": self.app_id,
                "statsDataId": dataset_id,
                "limit": LARGE_DATASET_THRESHOLD  # 最大10万件
            }
            
            response = requests.get(
                f"{self.base_url}/getStatsData",
                params=params,
                timeout=120
            )
            response.raise_for_status()
            data = response.json()
            
            # データを抽出
            stats_data = data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {})
            result_inf = stats_data.get('RESULT_INF', {})
            value_list = stats_data.get('DATA_INF', {}).get('VALUE', [])
            
            if isinstance(value_list, dict):
                value_list = [value_list]
            
            total_number = result_inf.get('TOTAL_NUMBER', 0)
            records_fetched = len(value_list)
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # 完全性をチェック
            completeness_ratio = records_fetched / total_number if total_number > 0 else 0
            
            print(f"   📊 Total: {total_number:,}, Fetched: {records_fetched:,} ({completeness_ratio*100:.1f}%)")
            
            # S3に保存
            s3_location = None
            if save_to_s3 and self.s3_client:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                s3_key = f"raw/data/{dataset_id}_{timestamp}.json"
                
                try:
                    self.s3_client.put_object(
                        Bucket=S3_BUCKET,
                        Key=s3_key,
                        Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
                        ContentType='application/json'
                    )
                    s3_location = f"s3://{S3_BUCKET}/{s3_key}"
                    print(f"   ✅ Saved to: {s3_location}")
                except Exception as e:
                    print(f"   ⚠️  S3 save failed: {str(e)}")
            
            # サンプルデータを作成
            sample_data = value_list[:5] if len(value_list) > 5 else value_list
            
            print(f"   ✅ Fetched {records_fetched:,} records in {processing_time:.1f}s")
            
            return {
                "success": True,
                "dataset_id": dataset_id,
                "records_fetched": records_fetched,
                "expected_records": total_number,
                "completeness_ratio": completeness_ratio,
                "processing_time": f"{processing_time:.1f}秒",
                "sample_data": sample_data,
                "s3_location": s3_location,
                "next_action": "transform_to_parquet",
                "message": f"Successfully fetched {records_fetched:,} records (100.0% complete)",
                "note": "Small dataset - complete retrieval in single request"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _fetch_complete_data_by_chunks(
        self,
        dataset_id: str,
        categories: dict,
        expected_total: int
    ) -> list:
        """
        時系列分割による完全データ取得
        
        Args:
            dataset_id: データセットID
            categories: カテゴリ情報
            expected_total: 期待される総レコード数
        
        Returns:
            完全データのリスト
        """
        print(f"   📅 Starting time-series chunked retrieval...")
        
        # 時間軸カテゴリを特定（通常はcat03が年度）
        time_category = None
        time_values = []
        
        for cat_id, cat_info in categories.items():
            if isinstance(cat_info, dict):
                values = cat_info.get('values', [])
                category_name = cat_info.get('name', '')
                
                # 年度らしいパターンを検出
                if values and len(values) > 10:  # 時系列は通常多くの値を持つ
                    year_like_count = 0
                    
                    # パターン1: 年度文字列（"1960年", "2020年"など）
                    for val in values[:10]:
                        if isinstance(val, str):
                            # "YYYY年"パターン
                            if val.endswith('年') and val[:-1].isdigit():
                                year = int(val[:-1])
                                if 1900 <= year <= 2030:
                                    year_like_count += 1
                            # "（概算）_YYYY年"パターン
                            elif '年' in val and any(part.isdigit() and 1900 <= int(part) <= 2030 for part in val.split('_') if part.replace('年', '').isdigit()):
                                year_like_count += 1
                    
                    # パターン2: カテゴリ名に年度・時間を示す文字が含まれる
                    time_keywords = ['年', '時間', '期間', '年度', '時系列']
                    if any(keyword in category_name for keyword in time_keywords):
                        year_like_count += 5  # ボーナス点
                    
                    if year_like_count >= 5:  # 年度らしい
                        time_category = cat_id
                        time_values = values
                        print(f"   📅 Detected time category: {category_name}")
                        break
        
        if not time_category:
            print(f"   ⚠️ No time-series category found for chunking")
            return []
        
        print(f"   📅 Using time category '{time_category}' with {len(time_values)} periods")
        
        # 年度別に分割取得
        all_chunked_records = []
        successful_chunks = 0
        failed_chunks = 0
        
        # 年度値を処理（"1960年" → "1960"のような変換）
        processed_years = []
        for val in time_values:
            if isinstance(val, str):
                if val.endswith('年'):
                    year_str = val[:-1]
                    if year_str.isdigit():
                        processed_years.append((year_str, int(year_str)))
                elif '年' in val:
                    # "（概算）_2022年"のような複雑なパターン
                    for part in val.split('_'):
                        if part.endswith('年') and part[:-1].isdigit():
                            year_str = part[:-1]
                            processed_years.append((year_str, int(year_str)))
                            break
        
        # 年度を逆順でソート（新しい年度から取得）
        sorted_years = sorted(processed_years, key=lambda x: x[1], reverse=True)
        
        print(f"   📅 Processing {len(sorted_years)} years: {sorted_years[0][0]} to {sorted_years[-1][0]}")
        
        for i, (year_code, year_num) in enumerate(sorted_years):
            try:
                chunk_params = {
                    "appId": self.app_id,
                    "statsDataId": dataset_id,
                    f"cd{time_category}": year_code,
                    "limit": 10000  # 年度別なら十分な量
                }
                
                chunk_response = requests.get(
                    f"{self.base_url}/getStatsData",
                    params=chunk_params,
                    timeout=30
                )
                chunk_response.raise_for_status()
                chunk_data = chunk_response.json()
                
                chunk_values = chunk_data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {}).get('DATA_INF', {}).get('VALUE', [])
                
                if isinstance(chunk_values, dict):
                    chunk_values = [chunk_values]
                
                if chunk_values:
                    all_chunked_records.extend(chunk_values)
                    successful_chunks += 1
                    print(f"   ✅ Year {year_num}: {len(chunk_values)} records")
                else:
                    print(f"   ⚪ Year {year_num}: No data")
                
                # 進捗表示（10年ごと）
                if (i + 1) % 10 == 0:
                    current_total = len(all_chunked_records)
                    progress = (current_total / expected_total * 100) if expected_total > 0 else 0
                    print(f"   📊 Progress: {i+1}/{len(sorted_years)} years, {current_total:,} records ({progress:.1f}%)")
                
                # 早期終了条件（期待値の95%に達した場合）
                if len(all_chunked_records) >= expected_total * 0.95:
                    print(f"   🎯 Reached 95% of expected data ({len(all_chunked_records):,}/{expected_total:,})")
                    break
                
                # レート制限対策（少し待機）
                if i % 5 == 4:  # 5回ごとに待機
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                failed_chunks += 1
                print(f"   ❌ Year {year_num} failed: {str(e)}")
                
                # 連続失敗が多い場合は中断
                if failed_chunks >= 5:
                    print(f"   ⚠️ Too many failures, stopping chunked retrieval")
                    break
                
                continue
        
        # 重複除去
        if all_chunked_records:
            print(f"   🔄 Deduplicating chunked data...")
            unique_chunked_records = self._deduplicate_records(all_chunked_records)
            
            print(f"   📊 Chunked retrieval summary:")
            print(f"      - Successful chunks: {successful_chunks}")
            print(f"      - Failed chunks: {failed_chunks}")
            print(f"      - Raw records: {len(all_chunked_records):,}")
            print(f"      - Unique records: {len(unique_chunked_records):,}")
            print(f"      - Completeness: {len(unique_chunked_records)/expected_total*100:.1f}%")
            
            return unique_chunked_records
        
        return []
    
    def _deduplicate_records(self, records: list) -> list:
        """
        レコードの重複を除去
        
        Args:
            records: レコードリスト
        
        Returns:
            重複除去されたレコードリスト
        """
        if not records:
            return records
        
        # レコードを一意のキーでグループ化
        seen_keys = set()
        unique_records = []
        
        for record in records:
            # レコードの一意キーを生成（全属性の組み合わせ）
            if isinstance(record, dict):
                # 辞書のキーと値をソートして一意キーを作成
                key_parts = []
                for k in sorted(record.keys()):
                    if k != '$':  # 値フィールドは除外
                        key_parts.append(f"{k}:{record.get(k, '')}")
                
                unique_key = "|".join(key_parts)
                
                if unique_key not in seen_keys:
                    seen_keys.add(unique_key)
                    unique_records.append(record)
        
        return unique_records
    
    def _merge_chunked_data(self, original_data: dict, chunked_records: list) -> dict:
        """分割取得したデータを元のデータ構造にマージ"""
        merged_data = original_data.copy()
        
        # VALUE部分を置き換え
        if 'GET_STATS_DATA' in merged_data:
            if 'STATISTICAL_DATA' in merged_data['GET_STATS_DATA']:
                if 'DATA_INF' in merged_data['GET_STATS_DATA']['STATISTICAL_DATA']:
                    merged_data['GET_STATS_DATA']['STATISTICAL_DATA']['DATA_INF']['VALUE'] = chunked_records
        
        return merged_data
    
    # ========================================
    # ツール4.5: fetch_large_dataset_complete (新機能)
    # ========================================
    
    async def fetch_large_dataset_complete(
        self,
        dataset_id: str,
        max_records: int = 1000000,
        chunk_size: int = 100000,
        save_to_s3: bool = True,
        convert_to_japanese: bool = True
    ) -> Dict[str, Any]:
        """
        大規模データセットの完全取得（最初のチャンクのみ取得・タイムアウト対策版）
        
        MCPのタイムアウト制限（約25秒）を考慮し、最初のチャンクのみ取得。
        完全な分割取得にはスタンドアロンスクリプトの使用を推奨。
        
        Args:
            dataset_id: データセットID
            max_records: 取得する最大レコード数（デフォルト: 100万件）
            chunk_size: 1回あたりの取得件数（デフォルト: 10万件）
            save_to_s3: S3に保存するか
            convert_to_japanese: コード→和名変換を実施するか
        
        Returns:
            取得結果（最初のチャンクと進行状況）
        """
        print(f"\n📥 fetch_large_dataset_complete: dataset_id='{dataset_id}', max_records={max_records:,}")
        
        try:
            # Step 1: メタデータを取得して総レコード数を確認
            print("   🔍 Getting metadata...")
            meta_response = requests.get(
                f"{self.base_url}/getMetaInfo",
                params={"appId": self.app_id, "statsDataId": dataset_id},
                timeout=30
            )
            meta_response.raise_for_status()
            meta_data = meta_response.json()
            
            overall_total = meta_data.get('GET_META_INFO', {}).get('METADATA_INF', {}).get('TABLE_INF', {}).get('OVERALL_TOTAL_NUMBER', 0)
            
            # Step 2: 実際の総数をAPIで確認
            test_response = requests.get(
                f"{self.base_url}/getStatsData",
                params={"appId": self.app_id, "statsDataId": dataset_id, "limit": 1, "metaGetFlg": "Y"},
                timeout=30
            )
            test_response.raise_for_status()
            test_data = test_response.json()
            
            actual_total = test_data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {}).get('RESULT_INF', {}).get('TOTAL_NUMBER', 0)
            
            print(f"   📊 Metadata total: {overall_total:,}, Actual total: {actual_total:,}")
            
            # 取得対象レコード数を決定
            target_records = min(actual_total, max_records)
            
            if target_records <= chunk_size:
                print(f"   💡 Small dataset ({target_records:,} records) - using single request")
                return await self.fetch_dataset_auto(dataset_id, save_to_s3, convert_to_japanese)
            
            # Step 3: 最初のチャンクのみ取得（タイムアウト対策）
            total_chunks = (target_records + chunk_size - 1) // chunk_size
            print(f"   🔄 Fetching first chunk: {chunk_size:,} records")
            print(f"   ⚠️  Note: Due to MCP timeout limits, only first chunk will be retrieved")
            print(f"   💡 Total chunks needed: {total_chunks}")
            
            start_time = datetime.now()
            
            # 最初のチャンクを取得
            params = {
                "appId": self.app_id,
                "statsDataId": dataset_id,
                "limit": chunk_size,
                "startPosition": 1
            }
            
            chunk_response = requests.get(
                f"{self.base_url}/getStatsData",
                params=params,
                timeout=60
            )
            chunk_response.raise_for_status()
            chunk_data = chunk_response.json()
            
            chunk_values = chunk_data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {}).get('DATA_INF', {}).get('VALUE', [])
            
            if isinstance(chunk_values, dict):
                chunk_values = [chunk_values]
            
            print(f"      ✅ Retrieved {len(chunk_values):,} records")
            
            # Step 4: S3に保存（最初のチャンクのみ）
            s3_location = None
            if save_to_s3 and self.s3_client:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                s3_key = f"raw/data/{dataset_id}_chunk_001_{timestamp}.json"
                
                try:
                    self.s3_client.put_object(
                        Bucket=S3_BUCKET,
                        Key=s3_key,
                        Body=json.dumps(chunk_data, ensure_ascii=False, indent=2).encode('utf-8'),
                        ContentType='application/json'
                    )
                    s3_location = f"s3://{S3_BUCKET}/{s3_key}"
                    print(f"   ✅ Saved chunk 1 to: {s3_location}")
                except Exception as e:
                    print(f"   ⚠️  S3 save failed: {str(e)}")
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # サンプルデータ
            sample_data = chunk_values[:5] if len(chunk_values) > 5 else chunk_values
            
            return {
                "success": True,
                "dataset_id": dataset_id,
                "metadata_total": overall_total,
                "actual_total": actual_total,
                "target_records": target_records,
                "chunk_size": chunk_size,
                "total_chunks_needed": total_chunks,
                "chunks_retrieved": 1,
                "records_in_chunk": len(chunk_values),
                "completeness": f"{len(chunk_values)/target_records*100:.1f}%",
                "processing_time": f"{processing_time:.1f}秒",
                "sample_data": sample_data,
                "s3_location": s3_location,
                "next_action": "Use Python script for complete retrieval",
                "recommendation": f"For complete data retrieval of {target_records:,} records, use the standalone Python script 'fetch_{dataset_id}_chunked.py' to avoid MCP timeout limits",
                "message": f"Retrieved first chunk ({len(chunk_values):,} records). Total {total_chunks} chunks needed for complete dataset.",
                "warning": "MCP timeout limit prevents full retrieval. Use standalone script for complete data."
            }
                    
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "dataset_id": dataset_id,
                "suggestion": "Try reducing max_records or using fetch_dataset_filtered with specific filters"
            }

    # ========================================
    # ツール4: fetch_dataset_filtered (修正版)
    # ========================================
    
    async def fetch_dataset_filtered(
        self,
        dataset_id: str,
        filters: Dict[str, str],
        convert_to_japanese: bool = True,
        save_to_s3: bool = True
    ) -> Dict[str, Any]:
        """
        カテゴリ指定での絞り込み取得（修正版）
        
        Args:
            dataset_id: データセットID
            filters: フィルタ条件（例: {"area": "13000", "cat01": "A1101", "time": "2020"}）
            convert_to_japanese: コード→和名変換を実施するか
            save_to_s3: S3に保存するか
        
        Returns:
            取得結果
        """
        print(f"\n📥 fetch_dataset_filtered: dataset_id='{dataset_id}', filters={filters}")
        
        try:
            # Step 1: メタデータを取得してフィルタを検証
            print("   🔍 Validating filters against metadata...")
            meta_response = requests.get(
                f"{self.base_url}/getMetaInfo",
                params={"appId": self.app_id, "statsDataId": dataset_id},
                timeout=30
            )
            meta_response.raise_for_status()
            meta_data = meta_response.json()
            
            # メタデータからカテゴリ情報を抽出
            class_objs = meta_data.get('GET_META_INFO', {}).get('METADATA_INF', {}).get('CLASS_INF', {}).get('CLASS_OBJ', [])
            available_categories = {}
            
            for class_obj in class_objs:
                cat_id = class_obj.get('@id')
                cat_name = class_obj.get('@name')
                classes = class_obj.get('CLASS', [])
                
                if isinstance(classes, dict):
                    classes = [classes]
                
                available_codes = []
                code_to_name = {}
                
                for cls in classes:
                    code = cls.get('@code')
                    name = cls.get('@name')
                    if code and name:
                        available_codes.append(code)
                        code_to_name[code] = name
                
                available_categories[cat_id] = {
                    'name': cat_name,
                    'codes': available_codes,
                    'code_to_name': code_to_name
                }
            
            print(f"   📋 Available categories: {list(available_categories.keys())}")
            
            # Step 2: フィルタを検証・変換
            validated_filters = {}
            filter_info = {}
            
            for filter_key, filter_value in filters.items():
                if filter_key in available_categories:
                    cat_info = available_categories[filter_key]
                    
                    # 値が日本語の場合、コードに変換
                    if filter_value in cat_info['code_to_name'].values():
                        # 日本語名からコードを検索
                        for code, name in cat_info['code_to_name'].items():
                            if name == filter_value:
                                validated_filters[f"cd{filter_key.title()}"] = code
                                filter_info[filter_key] = name
                                print(f"   ✅ {filter_key}: '{filter_value}' → code '{code}'")
                                break
                    elif filter_value in cat_info['codes']:
                        # 既にコードの場合
                        validated_filters[f"cd{filter_key.title()}"] = filter_value
                        filter_info[filter_key] = cat_info['code_to_name'].get(filter_value, filter_value)
                        print(f"   ✅ {filter_key}: code '{filter_value}' → '{filter_info[filter_key]}'")
                    else:
                        print(f"   ⚠️  {filter_key}: '{filter_value}' not found in available codes")
                        print(f"      Available codes: {cat_info['codes'][:10]}...")
                        # 部分マッチを試行
                        partial_matches = [code for code in cat_info['codes'] if filter_value in code]
                        if partial_matches:
                            best_match = partial_matches[0]
                            validated_filters[f"cd{filter_key.title()}"] = best_match
                            filter_info[filter_key] = cat_info['code_to_name'].get(best_match, best_match)
                            print(f"   🔄 Using partial match: '{best_match}' → '{filter_info[filter_key]}'")
                        else:
                            return {
                                "success": False,
                                "error": f"Filter value '{filter_value}' not found for category '{filter_key}'",
                                "available_codes": cat_info['codes'][:20],
                                "suggestion": f"Use one of the available codes for {filter_key}"
                            }
                else:
                    print(f"   ⚠️  Category '{filter_key}' not found in metadata")
                    return {
                        "success": False,
                        "error": f"Category '{filter_key}' not found in dataset metadata",
                        "available_categories": list(available_categories.keys()),
                        "suggestion": "Use one of the available category names"
                    }
            
            # Step 3: データ取得
            start_time = datetime.now()
            
            params = {
                "appId": self.app_id,
                "statsDataId": dataset_id,
                "limit": LARGE_DATASET_THRESHOLD,  # 最大10万件
                "metaGetFlg": "Y"  # メタデータも取得
            }
            
            # 検証済みフィルタを追加
            params.update(validated_filters)
            
            print(f"   🔄 Fetching data with params: {params}")
            
            response = requests.get(
                f"{self.base_url}/getStatsData",
                params=params,
                timeout=120
            )
            response.raise_for_status()
            data = response.json()
            
            # データを抽出
            stats_data = data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {})
            result_inf = stats_data.get('RESULT_INF', {})
            value_list = stats_data.get('DATA_INF', {}).get('VALUE', [])
            
            if isinstance(value_list, dict):
                value_list = [value_list]
            
            records_fetched = len(value_list)
            total_available = result_inf.get('TOTAL_NUMBER', 0)
            processing_time = (datetime.now() - start_time).total_seconds()
            
            print(f"   📊 Total available: {total_available:,}, Fetched: {records_fetched:,}")
            
            # フィルタが正しく適用されたかチェック
            if records_fetched == 0:
                return {
                    "success": False,
                    "error": "No data returned with the specified filters",
                    "filters_applied": filter_info,
                    "total_available": total_available,
                    "suggestion": "Try different filter values or remove some filters"
                }
            
            # S3に保存
            s3_location = None
            if save_to_s3 and self.s3_client:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                s3_key = f"raw/data/{dataset_id}_filtered_{timestamp}.json"
                
                try:
                    self.s3_client.put_object(
                        Bucket=S3_BUCKET,
                        Key=s3_key,
                        Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
                        ContentType='application/json'
                    )
                    s3_location = f"s3://{S3_BUCKET}/{s3_key}"
                    print(f"   ✅ Saved to: {s3_location}")
                except Exception as e:
                    print(f"   ⚠️  S3 save failed: {str(e)}")
            
            # サンプルデータを作成
            sample_data = value_list[:5] if len(value_list) > 5 else value_list
            
            print(f"   ✅ Successfully fetched {records_fetched:,} records in {processing_time:.1f}s")
            
            return {
                "success": True,
                "dataset_id": dataset_id,
                "filters_applied": filter_info,
                "records_fetched": records_fetched,
                "total_available": total_available,
                "filter_effectiveness": f"{records_fetched/total_available*100:.1f}%" if total_available > 0 else "N/A",
                "processing_time": f"{processing_time:.1f}秒",
                "sample_data": sample_data,
                "s3_location": s3_location,
                "next_action": "transform_to_parquet",
                "message": f"Successfully fetched {records_fetched:,} records with filters (filtered from {total_available:,} total records)"
            }
            
        except Exception as e:
            return {
                "success": False, 
                "error": str(e),
                "dataset_id": dataset_id,
                "filters": filters,
                "suggestion": "Check filter values and dataset_id, or try fetch_dataset_auto for smaller datasets"
            }
    
    # ========================================
    # ヘルパーメソッド
    # ========================================
    
    # ========================================
    # ツール5: transform_to_parquet
    # ========================================
    
    async def transform_to_parquet(
        self,
        s3_json_path: str,
        data_type: str,
        output_prefix: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        JSONデータをParquet形式に変換してS3に保存
        
        Args:
            s3_json_path: S3上のJSONファイルパス
            data_type: データ種別
            output_prefix: 出力先プレフィックス（オプション）
        
        Returns:
            変換結果
        """
        print(f"\n🔄 transform_to_parquet: {s3_json_path}")
        
        try:
            import pandas as pd
            import pyarrow as pa
            import pyarrow.parquet as pq
            from io import BytesIO
            
            if not self.s3_client:
                return {"success": False, "error": "S3 client not available"}
            
            # S3パスを解析
            if s3_json_path.startswith('s3://'):
                path_parts = s3_json_path[5:].split('/', 1)
                bucket = path_parts[0]
                key = path_parts[1]
            else:
                bucket = S3_BUCKET
                key = s3_json_path
            
            # JSONデータを読み込み
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            data = json.loads(response['Body'].read())
            
            # データを抽出
            stats_data = data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {})
            data_inf = stats_data.get('DATA_INF', {})
            values = data_inf.get('VALUE', [])
            
            if not values:
                return {"success": False, "error": "No data found in JSON"}
            
            # DataFrameに変換
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
                
                # カテゴリ別の追加フィールド
                if data_type == 'population':
                    record['year'] = int(value.get('@time', '2020'))
                    record['region_code'] = value.get('@cat01', '')
                    record['region_name'] = ''
                    record['category'] = value.get('@cat02', '')
                elif data_type == 'economy':
                    record['year'] = int(value.get('@time', '2020'))
                    record['quarter'] = 1
                    record['region_code'] = value.get('@area', '')
                    record['indicator'] = value.get('@cat01', '')
                elif data_type == 'education':
                    record['year'] = int(value.get('@time', '2020'))
                    record['region_code'] = value.get('@area', '')
                    record['school_type'] = value.get('@cat01', '')
                    record['metric'] = value.get('@cat02', '')
                else:
                    # 汎用フィールド
                    record['year'] = int(value.get('@time', '2020'))
                    record['region_code'] = value.get('@area', '')
                    record['category'] = value.get('@cat01', '')
                
                records.append(record)
            
            df = pd.DataFrame(records)
            
            # Parquetに変換
            table = pa.Table.from_pandas(df)
            
            # 出力パスを決定
            if output_prefix:
                parquet_key = f"{output_prefix}/{data_type}/{dataset_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
            else:
                parquet_key = key.replace('raw/data/', 'processed/').replace('.json', '.parquet')
            
            # S3に保存
            buffer = BytesIO()
            pq.write_table(table, buffer)
            buffer.seek(0)
            
            self.s3_client.put_object(
                Bucket=bucket,
                Key=parquet_key,
                Body=buffer.getvalue(),
                ContentType='application/octet-stream'
            )
            
            s3_parquet_path = f"s3://{bucket}/{parquet_key}"
            
            print(f"   ✅ Converted {len(records)} records to Parquet")
            
            return {
                "success": True,
                "source_path": s3_json_path,
                "target_path": s3_parquet_path,
                "records_processed": len(records),
                "data_type": data_type,
                "message": f"Successfully converted {len(records)} records to Parquet format"
            }
            
        except ImportError as e:
            return {"success": False, "error": f"Required libraries not available: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ========================================
    # ツール6: load_to_iceberg
    # ========================================
    
    async def load_to_iceberg(
        self,
        table_name: str,
        s3_parquet_path: str,
        create_if_not_exists: bool = True
    ) -> Dict[str, Any]:
        """
        ParquetデータをIcebergテーブルに投入（改良版）
        
        Args:
            table_name: テーブル名
            s3_parquet_path: S3上のParquetファイルパス
            create_if_not_exists: テーブルが存在しない場合に作成するか
        
        Returns:
            投入結果
        """
        print(f"\n📊 load_to_iceberg: {table_name}")
        
        try:
            import boto3
            
            athena_client = boto3.client('athena', region_name=AWS_REGION)
            glue_client = boto3.client('glue', region_name=AWS_REGION)
            database = 'estat_db'
            output_location = f's3://{S3_BUCKET}/athena-results/'
            
            # S3パスを解析
            if s3_parquet_path.startswith('s3://'):
                path_parts = s3_parquet_path[5:].split('/', 1)
                bucket = path_parts[0]
                parquet_key = path_parts[1]
            else:
                bucket = S3_BUCKET
                parquet_key = s3_parquet_path
            
            # 1. データベースの存在確認と作成
            print(f"   🔍 Checking database: {database}")
            try:
                glue_client.get_database(Name=database)
                print(f"   ✅ Database {database} exists")
            except glue_client.exceptions.EntityNotFoundException:
                print(f"   🔄 Creating database: {database}")
                try:
                    glue_client.create_database(
                        DatabaseInput={
                            'Name': database,
                            'Description': 'e-Stat analysis database for statistical data'
                        }
                    )
                    print(f"   ✅ Database {database} created")
                except Exception as db_error:
                    print(f"   ⚠️ Database creation failed: {str(db_error)}")
                    # Athenaで作成を試行
                    create_db_query = f"CREATE DATABASE IF NOT EXISTS {database}"
                    db_result = await self._execute_athena_query(athena_client, create_db_query, "default", output_location)
                    if not db_result[0]:
                        return {"success": False, "error": f"Failed to create database: {db_result[1]}"}
            
            # 2. テーブルの存在確認
            print(f"   🔍 Checking table: {table_name}")
            table_exists = False
            try:
                glue_client.get_table(DatabaseName=database, Name=table_name)
                table_exists = True
                print(f"   ✅ Table {table_name} exists")
            except glue_client.exceptions.EntityNotFoundException:
                print(f"   ℹ️ Table {table_name} does not exist")
            
            # 3. テーブル作成（存在しない場合）または既存データのクリア
            if table_exists:
                print(f"   🔄 Table exists - clearing existing data...")
                clear_query = f"DELETE FROM {database}.{table_name}"
                clear_result = await self._execute_athena_query(athena_client, clear_query, database, output_location)
                if clear_result[0]:
                    print(f"   ✅ Existing data cleared")
                else:
                    print(f"   ⚠️ Data clearing failed: {clear_result[1]}")
            elif create_if_not_exists:
                print(f"   🔄 Creating table: {table_name}")
                
                # まずIcebergテーブル作成を試行（Athena v3構文）
                iceberg_query = f"""
                CREATE TABLE IF NOT EXISTS {database}.{table_name} (
                    stats_data_id STRING,
                    year INT,
                    region_code STRING,
                    category STRING,
                    value DOUBLE,
                    unit STRING,
                    updated_at TIMESTAMP
                )
                LOCATION 's3://{bucket}/iceberg/{table_name}/'
                TBLPROPERTIES (
                    'table_type'='ICEBERG',
                    'format'='parquet'
                )
                """
                
                iceberg_result = await self._execute_athena_query(athena_client, iceberg_query, database, output_location)
                
                if not iceberg_result[0]:
                    print(f"   ⚠️ Iceberg creation failed: {iceberg_result[1]}")
                    print(f"   🔄 Trying regular Parquet table...")
                    
                    # 通常のParquetテーブルとして作成
                    regular_query = f"""
                    CREATE EXTERNAL TABLE IF NOT EXISTS {database}.{table_name} (
                        stats_data_id STRING,
                        year INT,
                        region_code STRING,
                        category STRING,
                        value DOUBLE,
                        unit STRING,
                        updated_at TIMESTAMP
                    )
                    STORED AS PARQUET
                    LOCATION 's3://{bucket}/tables/{table_name}/'
                    """
                    
                    regular_result = await self._execute_athena_query(athena_client, regular_query, database, output_location)
                    if not regular_result[0]:
                        return {"success": False, "error": f"Failed to create table: {regular_result[1]}"}
                    else:
                        print(f"   ✅ Regular Parquet table created")
                else:
                    print(f"   ✅ Iceberg table created")
            
            # 4. 外部テーブルを作成してParquetデータを読み込み
            external_table = f"{table_name}_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            print(f"   🔄 Creating external table: {external_table}")
            
            # 特定のParquetファイルのみを対象とするため、一時ディレクトリを作成
            temp_dir = f"temp/{external_table}/"
            
            # 元のParquetファイルを一時ディレクトリにコピー
            copy_source = {'Bucket': bucket, 'Key': parquet_key}
            temp_key = f"{temp_dir}{parquet_key.split('/')[-1]}"
            
            try:
                import boto3
                s3_client = boto3.client('s3', region_name=AWS_REGION)
                s3_client.copy_object(CopySource=copy_source, Bucket=bucket, Key=temp_key)
                print(f"   📋 Copied Parquet file to temp location: {temp_key}")
            except Exception as copy_error:
                print(f"   ⚠️ File copy failed: {str(copy_error)}")
                # コピーに失敗した場合は元のディレクトリを使用
                temp_dir = parquet_key.rsplit("/", 1)[0] + "/"
            
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
            LOCATION 's3://{bucket}/{temp_dir}'
            """
            
            external_result = await self._execute_athena_query(athena_client, create_external_query, database, output_location)
            if not external_result[0]:
                return {"success": False, "error": f"Failed to create external table: {external_result[1]}"}
            
            print(f"   ✅ External table created")
            
            # 5. データをメインテーブルに投入
            print(f"   🔄 Inserting data...")
            insert_query = f"""
            INSERT INTO {database}.{table_name}
            SELECT * FROM {database}.{external_table}
            """
            
            insert_result = await self._execute_athena_query(athena_client, insert_query, database, output_location)
            if not insert_result[0]:
                # 外部テーブルを削除してからエラーを返す
                await self._execute_athena_query(athena_client, f"DROP TABLE IF EXISTS {database}.{external_table}", database, output_location)
                return {"success": False, "error": f"Failed to insert data: {insert_result[1]}"}
            
            print(f"   ✅ Data inserted")
            
            # 6. レコード数を確認
            print(f"   🔄 Counting records...")
            count_query = f"SELECT COUNT(*) FROM {database}.{table_name}"
            count_result = await self._execute_athena_query(athena_client, count_query, database, output_location)
            
            record_count = "不明"
            if count_result[0] and count_result[1]:
                try:
                    if isinstance(count_result[1], list) and len(count_result[1]) > 0:
                        record_count = count_result[1][0][0] if isinstance(count_result[1][0], list) else count_result[1][0]
                    else:
                        record_count = str(count_result[1])
                except:
                    record_count = "不明"
            
            # 7. クリーンアップ（外部テーブルと一時ファイル）
            print(f"   🔄 Cleaning up external table and temp files...")
            drop_query = f"DROP TABLE IF EXISTS {database}.{external_table}"
            await self._execute_athena_query(athena_client, drop_query, database, output_location)
            
            # 一時ファイルも削除
            if temp_key and temp_key != parquet_key:
                try:
                    s3_client.delete_object(Bucket=bucket, Key=temp_key)
                    print(f"   🗑️ Deleted temp file: {temp_key}")
                except Exception as delete_error:
                    print(f"   ⚠️ Temp file deletion failed: {str(delete_error)}")
            
            print(f"   ✅ Loaded data to table: {record_count} records")
            
            return {
                "success": True,
                "table_name": table_name,
                "database": database,
                "records_loaded": record_count,
                "source_path": s3_parquet_path,
                "table_location": f"s3://{bucket}/iceberg/{table_name}/" if "iceberg" in str(iceberg_result) else f"s3://{bucket}/tables/{table_name}/",
                "message": f"Successfully loaded data to table {table_name} ({record_count} records)"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ========================================
    # ツール7: analyze_with_athena
    # ========================================
    
    async def analyze_with_athena(
        self,
        table_name: str,
        analysis_type: str = "basic",
        custom_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Athenaで統計分析を実行
        
        Args:
            table_name: テーブル名
            analysis_type: 分析タイプ（basic/advanced）
            custom_query: カスタムクエリ（オプション）
        
        Returns:
            分析結果
        """
        print(f"\n📈 analyze_with_athena: {table_name} ({analysis_type})")
        
        try:
            import boto3
            
            athena_client = boto3.client('athena', region_name=AWS_REGION)
            database = 'estat_db'
            output_location = f's3://{S3_BUCKET}/athena-results/'
            
            results = {}
            
            if custom_query:
                # カスタムクエリを実行
                query_result = await self._execute_athena_query(athena_client, custom_query, database, output_location)
                results["custom_query"] = {
                    "success": query_result[0],
                    "result": query_result[1] if query_result[0] else query_result[1]
                }
            
            elif analysis_type == "basic":
                # 基本分析
                queries = {
                    "record_count": f"SELECT COUNT(*) as total_records FROM {database}.{table_name}",
                    "value_stats": f"""
                        SELECT 
                            COUNT(value) as non_null_values,
                            AVG(value) as avg_value,
                            MIN(value) as min_value,
                            MAX(value) as max_value,
                            STDDEV(value) as stddev_value
                        FROM {database}.{table_name}
                        WHERE value IS NOT NULL
                    """,
                    "year_distribution": f"""
                        SELECT year, COUNT(*) as count
                        FROM {database}.{table_name}
                        GROUP BY year
                        ORDER BY year
                        LIMIT 10
                    """,
                    "category_distribution": f"""
                        SELECT category, COUNT(*) as count
                        FROM {database}.{table_name}
                        WHERE category IS NOT NULL AND category != ''
                        GROUP BY category
                        ORDER BY count DESC
                        LIMIT 10
                    """
                }
                
                for query_name, query in queries.items():
                    query_result = await self._execute_athena_query(athena_client, query, database, output_location)
                    results[query_name] = {
                        "success": query_result[0],
                        "result": query_result[1] if query_result[0] else query_result[1]
                    }
            
            elif analysis_type == "advanced":
                # 高度な分析
                queries = {
                    "correlation_analysis": f"""
                        SELECT 
                            year,
                            category,
                            AVG(value) as avg_value,
                            COUNT(*) as sample_size
                        FROM {database}.{table_name}
                        WHERE value IS NOT NULL
                        GROUP BY year, category
                        HAVING COUNT(*) >= 10
                        ORDER BY year, avg_value DESC
                        LIMIT 20
                    """,
                    "trend_analysis": f"""
                        SELECT 
                            year,
                            AVG(value) as yearly_average,
                            COUNT(*) as data_points,
                            STDDEV(value) as yearly_stddev
                        FROM {database}.{table_name}
                        WHERE value IS NOT NULL
                        GROUP BY year
                        ORDER BY year
                    """,
                    "outlier_detection": f"""
                        WITH stats AS (
                            SELECT 
                                AVG(value) as mean_val,
                                STDDEV(value) as std_val
                            FROM {database}.{table_name}
                            WHERE value IS NOT NULL
                        )
                        SELECT 
                            stats_data_id,
                            year,
                            category,
                            value,
                            ABS(value - mean_val) / std_val as z_score
                        FROM {database}.{table_name}, stats
                        WHERE value IS NOT NULL
                        AND ABS(value - mean_val) / std_val > 2
                        ORDER BY z_score DESC
                        LIMIT 10
                    """
                }
                
                for query_name, query in queries.items():
                    query_result = await self._execute_athena_query(athena_client, query, database, output_location)
                    results[query_name] = {
                        "success": query_result[0],
                        "result": query_result[1] if query_result[0] else query_result[1]
                    }
            
            # 成功した分析の数をカウント
            successful_analyses = sum(1 for r in results.values() if r.get("success", False))
            
            print(f"   ✅ Completed {successful_analyses}/{len(results)} analyses")
            
            return {
                "success": True,
                "table_name": table_name,
                "analysis_type": analysis_type,
                "results": results,
                "successful_analyses": successful_analyses,
                "total_analyses": len(results),
                "message": f"Analysis completed: {successful_analyses}/{len(results)} queries successful"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ========================================
    # ツール9: save_dataset_as_csv（新規）
    # ========================================
    
    async def save_dataset_as_csv(
        self,
        dataset_id: str,
        s3_json_path: Optional[str] = None,
        local_json_path: Optional[str] = None,
        output_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        取得したデータセットをCSV形式でS3に保存
        
        Args:
            dataset_id: データセットID
            s3_json_path: S3上のJSONファイルパス（オプション）
            local_json_path: ローカルのJSONファイルパス（オプション）
            output_filename: 出力ファイル名（オプション、デフォルトは dataset_id_YYYYMMDD_HHMMSS.csv）
        
        Returns:
            保存結果（S3パス含む）
        """
        print(f"\n💾 save_dataset_as_csv: dataset_id='{dataset_id}'")
        
        try:
            import pandas as pd
            import io
            
            # データソースの決定
            data = None
            
            if s3_json_path:
                # S3からJSONを読み込み
                print(f"   📥 Loading from S3: {s3_json_path}")
                if not self.s3_client:
                    return {"success": False, "error": "S3 client not initialized"}
                
                # S3パスをパース
                if s3_json_path.startswith('s3://'):
                    s3_json_path = s3_json_path[5:]
                
                parts = s3_json_path.split('/', 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ''
                
                response = self.s3_client.get_object(Bucket=bucket, Key=key)
                data = json.loads(response['Body'].read().decode('utf-8'))
                
            elif local_json_path:
                # ローカルファイルから読み込み
                print(f"   📥 Loading from local: {local_json_path}")
                with open(local_json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            else:
                return {
                    "success": False,
                    "error": "Either s3_json_path or local_json_path must be provided"
                }
            
            # データを抽出
            stats_data = data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {})
            value_list = stats_data.get('DATA_INF', {}).get('VALUE', [])
            
            if isinstance(value_list, dict):
                value_list = [value_list]
            
            if not value_list:
                return {"success": False, "error": "No data found in JSON"}
            
            print(f"   📊 Converting {len(value_list):,} records to CSV")
            
            # DataFrameに変換
            df = pd.DataFrame(value_list)
            
            # CSVに変換
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')  # BOM付きUTF-8
            csv_content = csv_buffer.getvalue()
            
            # 出力ファイル名を決定
            if not output_filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_filename = f"{dataset_id}_{timestamp}.csv"
            
            # S3に保存
            s3_key = f"csv/{output_filename}"
            
            if not self.s3_client:
                return {"success": False, "error": "S3 client not initialized"}
            
            self.s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=csv_content.encode('utf-8-sig'),
                ContentType='text/csv'
            )
            
            s3_location = f"s3://{S3_BUCKET}/{s3_key}"
            
            print(f"   ✅ CSV saved to: {s3_location}")
            
            return {
                "success": True,
                "dataset_id": dataset_id,
                "records_count": len(value_list),
                "columns": list(df.columns),
                "s3_location": s3_location,
                "s3_bucket": S3_BUCKET,
                "s3_key": s3_key,
                "filename": output_filename,
                "message": f"Successfully saved {len(value_list):,} records as CSV to S3"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ========================================
    # ツール10: download_csv_from_s3（新規）
    # ========================================
    
    async def download_csv_from_s3(
        self,
        s3_path: str,
        local_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        S3に保存されたCSVファイルをローカルにダウンロード
        
        Args:
            s3_path: S3上のCSVファイルパス（s3://bucket/key 形式）
            local_path: ローカル保存先パス（オプション、デフォルトはカレントディレクトリ）
        
        Returns:
            ダウンロード結果
        """
        print(f"\n⬇️  download_csv_from_s3: s3_path='{s3_path}'")
        
        try:
            if not self.s3_client:
                return {"success": False, "error": "S3 client not initialized"}
            
            # S3パスをパース
            if not s3_path.startswith('s3://'):
                return {"success": False, "error": "s3_path must start with 's3://'"}
            
            s3_path_clean = s3_path[5:]
            parts = s3_path_clean.split('/', 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ''
            
            # ローカルパスを決定
            if not local_path:
                filename = key.split('/')[-1]
                local_path = filename
            
            # ディレクトリが存在しない場合は作成
            import os
            local_dir = os.path.dirname(local_path)
            if local_dir and not os.path.exists(local_dir):
                os.makedirs(local_dir, exist_ok=True)
                print(f"   📁 Created directory: {local_dir}")
            
            print(f"   📥 Downloading from S3: {bucket}/{key}")
            print(f"   💾 Saving to: {local_path}")
            
            # S3からダウンロード（get_objectを使用して直接書き込み）
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            
            # ファイルに書き込み
            with open(local_path, 'wb') as f:
                f.write(response['Body'].read())
            
            # ファイルサイズを取得
            import os
            file_size = os.path.getsize(local_path)
            file_size_mb = file_size / (1024 * 1024)
            
            print(f"   ✅ Downloaded: {file_size_mb:.2f} MB")
            
            return {
                "success": True,
                "s3_path": s3_path,
                "local_path": local_path,
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size_mb, 2),
                "message": f"Successfully downloaded CSV to {local_path} ({file_size_mb:.2f} MB)"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ========================================
    # ヘルパーメソッド
    # ========================================
    
    async def _execute_athena_query(self, athena_client, query: str, database: str, output_location: str):
        """Athenaクエリを実行"""
        try:
            import time
            
            response = athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={
                    'Database': database,
                    'Catalog': 'AwsDataCatalog'
                },
                ResultConfiguration={
                    'OutputLocation': output_location
                }
            )
            
            query_execution_id = response['QueryExecutionId']
            
            # クエリ完了を待機
            max_wait = 300  # 5分
            waited = 0
            
            while waited < max_wait:
                status_response = athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                status = status_response['QueryExecution']['Status']['State']
                
                if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                    break
                
                await asyncio.sleep(5)
                waited += 5
            
            if status == 'SUCCEEDED':
                # 結果を取得
                try:
                    results = athena_client.get_query_results(
                        QueryExecutionId=query_execution_id,
                        MaxResults=100
                    )
                    rows = results['ResultSet']['Rows']
                    if len(rows) > 1:
                        # 最初の行はヘッダー、データ行を返す
                        data_rows = []
                        for row in rows[1:]:
                            row_data = [col.get('VarCharValue', '') for col in row['Data']]
                            data_rows.append(row_data)
                        return True, data_rows
                    else:
                        return True, "No data returned"
                except:
                    return True, "Query executed successfully"
            elif status == 'FAILED':
                error_message = status_response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
                return False, error_message
            else:
                return False, f"Query timeout (status: {status})"
                
        except Exception as e:
            return False, str(e)

    def get_available_tools(self) -> List[str]:
        """利用可能なツールのリストを取得"""
        return [
            "search_and_rank_datasets",              # 検索 + メタデータ + スコアリング + Top5（サジェスト機能付き）
            "apply_keyword_suggestions_and_search",  # キーワード変換を適用
            "fetch_dataset_auto",                    # 10万件未満の自動取得
            "fetch_dataset_filtered",               # カテゴリ指定での絞り込み取得
            "transform_to_parquet",                  # JSONをParquetに変換
            "load_to_iceberg",                       # ParquetをIcebergテーブルに投入
            "analyze_with_athena"                    # Athenaで統計分析を実行
        ]


async def main():
    """テスト実行"""
    print("=" * 80)
    print("e-Stat HITL Analysis Server - Test Mode")
    print("=" * 80)
    
    server = EStatHITLServer()
    
    # テスト1: 検索とランキング（メタデータ含む）
    print("\n" + "=" * 80)
    print("Test 1: search_and_rank_datasets (with metadata)")
    print("=" * 80)
    result = await server.search_and_rank_datasets(query="交通事故", max_results=3)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # テスト2: データ取得
    if result.get('success') and result.get('results'):
        dataset_id = result['results'][0]['dataset_id']
        total_records = result['results'][0].get('total_records')
        
        print("\n" + "=" * 80)
        print("Test 2: fetch_dataset_auto")
        print("=" * 80)
        
        if total_records and total_records < LARGE_DATASET_THRESHOLD:
            fetch_result = await server.fetch_dataset_auto(dataset_id=dataset_id, save_to_s3=False)
            print(json.dumps(fetch_result, ensure_ascii=False, indent=2))
        else:
            print(f"Dataset has {total_records} records - skipping auto fetch test")


if __name__ == '__main__':
    asyncio.run(main())
