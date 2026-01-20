"""
e-Stat AWS MCP Server
AWS ECS Fargate上で動作するe-Stat MCPサーバーのメイン実装
"""

import os
import json
import asyncio
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from functools import lru_cache

# ローカルインポート
from .keyword_dictionary import get_keyword_suggestions, apply_keyword_suggestions, format_suggestion_message
from .utils.error_handler import format_error_response, EStatError, AWSError, DataTransformError
from .utils.retry import retry_with_backoff, RetryableError
from .utils.logger import setup_logger, log_tool_call, log_tool_result
from .utils.response_formatter import format_success_response, format_dataset_info

# 環境変数
ESTAT_APP_ID = os.environ.get('ESTAT_APP_ID', '320dd2fbff6974743e3f95505c9f346650ab635e')
S3_BUCKET = os.environ.get('S3_BUCKET', 'estat-data-lake')
AWS_REGION = os.environ.get('AWS_REGION', 'ap-northeast-1')

# 定数
LARGE_DATASET_THRESHOLD = 100000  # 10万件

# ロガー設定
logger = setup_logger(__name__, os.environ.get('LOG_LEVEL', 'INFO'))


class EStatAWSServer:
    """e-Stat AWS MCPサーバーのメイン実装"""
    
    def __init__(self):
        self.app_id = ESTAT_APP_ID
        self.base_url = "https://api.e-stat.go.jp/rest/3.0/app/json"
        
        # HTTPセッション（コネクションプーリング）
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=3
        )
        self.session.mount('https://', adapter)
        
        # AWSクライアント（必要に応じて初期化）
        try:
            import boto3
            self.s3_client = boto3.client('s3', region_name=AWS_REGION)
            self.athena_client = boto3.client('athena', region_name=AWS_REGION)
            logger.info("AWS clients initialized successfully")
        except ImportError:
            self.s3_client = None
            self.athena_client = None
            logger.warning("boto3 not available, AWS features disabled")
        except Exception as e:
            self.s3_client = None
            self.athena_client = None
            logger.error(f"Failed to initialize AWS clients: {e}")
    
    # ========================================
    # ツール1: search_estat_data
    # ========================================
    
    async def search_estat_data(
        self,
        query: str,
        max_results: int = 5,
        auto_suggest: bool = True,
        scoring_method: str = "enhanced"
    ) -> Dict[str, Any]:
        """
        自然言語検索 + キーワードサジェスト + スコアリング
        
        Args:
            query: 検索クエリ
            max_results: 返却する最大件数
            auto_suggest: キーワードサジェストを有効にするか
            scoring_method: スコアリング方法（"enhanced" or "basic"）
        
        Returns:
            検索結果
        """
        start_time = datetime.now()
        log_tool_call(logger, "search_estat_data", {
            "query": query,
            "max_results": max_results,
            "auto_suggest": auto_suggest,
            "scoring_method": scoring_method
        })
        
        try:
            # ステップ0: キーワードサジェスト
            if auto_suggest:
                keyword_suggestions = get_keyword_suggestions(query)
                if keyword_suggestions:
                    logger.info(f"Found {len(keyword_suggestions)} keyword suggestions")
                    
                    suggestion_message = format_suggestion_message(keyword_suggestions)
                    
                    return {
                        "success": True,
                        "has_suggestions": True,
                        "suggestions": {
                            "original_query": query,
                            "suggestions": keyword_suggestions,
                            "message": suggestion_message
                        },
                        "message": "キーワード変換の提案があります。apply_keyword_suggestionsツールで変換を適用してください。"
                    }
            
            # ステップ1: e-Stat API呼び出し（検索）
            params = {
                "appId": self.app_id,
                "searchWord": query,
                "limit": 100
            }
            
            response = await self._call_estat_api("getStatsList", params)
            
            # 統計表リストを取得
            table_list = response.get('GET_STATS_LIST', {}).get('DATALIST_INF', {}).get('TABLE_INF', [])
            
            if isinstance(table_list, dict):
                table_list = [table_list]
            elif not table_list:
                return {
                    "success": True,
                    "query": query,
                    "results": [],
                    "message": f"No datasets found for query '{query}'"
                }
            
            logger.info(f"Found {len(table_list)} datasets from search")
            
            # ステップ2: 初期スコアリング
            scored_datasets = []
            for table in table_list:
                basic_score = self._calculate_basic_score(query, table)
                scored_datasets.append({
                    "table": table,
                    "basic_score": basic_score
                })
            
            # ステップ3: Top 20を選択
            scored_datasets.sort(key=lambda x: x['basic_score'], reverse=True)
            top_20 = scored_datasets[:min(20, len(scored_datasets))]
            
            logger.info(f"Selected top {len(top_20)} for metadata retrieval")
            
            # ステップ4: Top 20のメタデータを並列取得
            if scoring_method == "enhanced":
                logger.info(f"Fetching metadata for top {len(top_20)} datasets...")
                
                tasks = [
                    self._get_metadata_quick(item['table'].get('@id'))
                    for item in top_20
                ]
                metadata_list = await asyncio.gather(*tasks, return_exceptions=True)
                
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
            
            # ステップ6: Top Nを返却
            top_20.sort(key=lambda x: x['final_score'], reverse=True)
            top_results = top_20[:max_results]
            
            # 結果をフォーマット
            formatted_results = []
            for i, item in enumerate(top_results, 1):
                table = item['table']
                metadata = item.get('metadata', {})
                
                result = format_dataset_info(table, rank=i, score=item['final_score'])
                
                # メタデータ情報を追加
                if metadata:
                    result["total_records"] = metadata.get('total_records')
                    result["total_records_formatted"] = metadata.get('total_records_formatted', '不明')
                    result["requires_filtering"] = metadata.get('requires_filtering')
                    
                    if 'categories' in metadata:
                        categories = metadata['categories']
                        result["categories"] = {}
                        for cat_id, cat_info in categories.items():
                            if isinstance(cat_info, dict):
                                result["categories"][cat_id] = {
                                    'name': cat_info.get('name', cat_id),
                                    'count': len(cat_info.get('values', [])),
                                    'sample': cat_info.get('values', [])[:5]
                                }
                
                formatted_results.append(result)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            log_tool_result(logger, "search_estat_data", True, execution_time)
            
            logger.info(f"Returning top {len(formatted_results)} datasets with metadata")
            
            return {
                "success": True,
                "query": query,
                "total_found": len(table_list),
                "results": formatted_results,
                "message": f"Found {len(formatted_results)} relevant datasets with metadata."
            }
            
        except Exception as e:
            logger.error(f"Error in search_estat_data: {e}", exc_info=True)
            return format_error_response(e, "search_estat_data", {"query": query})
    
    # ========================================
    # ツール2: apply_keyword_suggestions
    # ========================================
    
    def apply_keyword_suggestions_tool(
        self,
        original_query: str,
        accepted_keywords: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        キーワード変換を適用して新しいクエリを生成
        
        Args:
            original_query: 元のクエリ
            accepted_keywords: 承認されたキーワード変換
        
        Returns:
            変換後のクエリ
        """
        log_tool_call(logger, "apply_keyword_suggestions", {
            "original_query": original_query,
            "accepted_keywords": accepted_keywords
        })
        
        try:
            new_query = apply_keyword_suggestions(original_query, accepted_keywords)
            logger.info(f"Query transformed: '{original_query}' → '{new_query}'")
            
            return {
                "success": True,
                "original_query": original_query,
                "transformed_query": new_query,
                "accepted_keywords": accepted_keywords,
                "message": f"クエリを変換しました。新しいクエリ: '{new_query}'"
            }
            
        except Exception as e:
            logger.error(f"Error in apply_keyword_suggestions: {e}", exc_info=True)
            return format_error_response(e, "apply_keyword_suggestions", {
                "original_query": original_query
            })
    
    # ========================================
    # ツール3: fetch_dataset_auto
    # ========================================
    
    async def fetch_dataset_auto(
        self,
        dataset_id: str,
        save_to_s3: bool = True,
        convert_to_japanese: bool = True
    ) -> Dict[str, Any]:
        """
        データセットを自動取得（サイズに応じて自動切り替え）
        
        Args:
            dataset_id: データセットID
            save_to_s3: S3に保存するか
            convert_to_japanese: コード→和名変換を実施するか
        
        Returns:
            取得結果
        """
        start_time = datetime.now()
        log_tool_call(logger, "fetch_dataset_auto", {
            "dataset_id": dataset_id,
            "save_to_s3": save_to_s3
        })
        
        try:
            # Step 1: データサイズを事前確認
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
            
            # Step 2: データサイズに応じた取得方法の自動選択
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
            
        except Exception as e:
            logger.error(f"Error in fetch_dataset_auto: {e}", exc_info=True)
            return format_error_response(e, "fetch_dataset_auto", {"dataset_id": dataset_id})
    
    # ========================================
    # ヘルパーメソッド
    # ========================================
    
    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def _call_estat_api(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        e-Stat APIを呼び出す（リトライ付き）
        
        Args:
            endpoint: APIエンドポイント
            params: パラメータ
        
        Returns:
            APIレスポンス
        """
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
    
    async def _get_metadata_quick(self, dataset_id: str) -> Dict[str, Any]:
        """
        メタデータを高速取得
        
        Args:
            dataset_id: データセットID
        
        Returns:
            メタデータ情報
        """
        try:
            params = {
                "appId": self.app_id,
                "statsDataId": dataset_id
            }
            
            meta_data = await self._call_estat_api("getMetaInfo", params)
            
            meta_info = meta_data.get('GET_META_INFO', {})
            metadata_inf = meta_info.get('METADATA_INF', {})
            table_inf = metadata_inf.get('TABLE_INF', {})
            
            class_inf = metadata_inf.get('CLASS_INF', {})
            class_obj_list = class_inf.get('CLASS_OBJ', [])
            if not isinstance(class_obj_list, list):
                class_obj_list = [class_obj_list] if class_obj_list else []
            
            # 総データ件数を計算
            total_records = 0
            
            if 'TOTAL_NUMBER' in table_inf:
                try:
                    total_records = int(table_inf.get('TOTAL_NUMBER', 0))
                except (ValueError, TypeError):
                    total_records = 0
            
            # 次元の組み合わせから計算
            if total_records == 0 and class_obj_list:
                calculated_total = 1
                for class_obj in class_obj_list:
                    class_values = class_obj.get('CLASS', [])
                    if not isinstance(class_values, list):
                        class_values = [class_values] if class_values else []
                    calculated_total *= len(class_values)
                
                if calculated_total > 0:
                    total_records = calculated_total
            
            # カテゴリ情報を取得
            categories = {}
            for class_obj in class_obj_list:
                class_name = class_obj.get('@name', 'unknown')
                class_id = class_obj.get('@id', 'unknown')
                class_values = class_obj.get('CLASS', [])
                
                if not isinstance(class_values, list):
                    class_values = [class_values] if class_values else []
                
                category_names = [cv.get('@name', '') for cv in class_values]
                
                categories[class_id] = {
                    'name': class_name,
                    'values': category_names
                }
            
            # 10万件判定
            if total_records > 0:
                requires_filtering = total_records >= LARGE_DATASET_THRESHOLD
                formatted = f"{total_records:,}件"
            else:
                requires_filtering = None
                formatted = "不明"
            
            return {
                "total_records": total_records if total_records > 0 else None,
                "total_records_formatted": formatted,
                "requires_filtering": requires_filtering,
                "categories": categories
            }
            
        except Exception as e:
            logger.warning(f"Metadata fetch error: {e}")
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
        title = self._extract_value(dataset.get('TITLE', ''))
        if query_keywords:
            matches = sum(1 for keyword in query_keywords if keyword in title)
            score += 0.25 * (matches / len(query_keywords))
        
        # 2. 統計名・分類マッチ（15%）
        stats_name = dataset.get('STATISTICS_NAME', '')
        main_cat = self._extract_value(dataset.get('MAIN_CATEGORY', ''))
        sub_cat = self._extract_value(dataset.get('SUB_CATEGORY', ''))
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
        gov_org = self._extract_value(dataset.get('GOV_ORG', ''))
        
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
        # 基本スコア（80%）
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
        """カテゴリマッチスコアを計算"""
        query_keywords = [k for k in query.split() if len(k) > 1]
        if not query_keywords:
            return 0.0
        
        categories = metadata.get('categories', {})
        if not categories:
            return 0.0
        
        total_matches = 0
        for category_info in categories.values():
            if isinstance(category_info, dict):
                category_values = category_info.get('values', [])
            else:
                category_values = category_info if isinstance(category_info, list) else []
            
            category_text = ' '.join(category_values)
            matches = sum(1 for keyword in query_keywords if keyword in category_text)
            total_matches += matches
        
        score = min(total_matches / len(query_keywords), 1.0)
        return score
    
    def _calculate_data_size_score(self, total_records: Optional[int]) -> float:
        """データ規模の適切性スコアを計算"""
        if total_records is None:
            return 0.5
        
        if total_records >= 10000:
            return 1.0
        elif total_records >= 1000:
            return 0.9
        elif total_records >= 100:
            return 0.7
        elif total_records >= 10:
            return 0.5
        else:
            return 0.3
    
    def _extract_value(self, field: Any) -> str:
        """フィールドから値を抽出"""
        if isinstance(field, dict):
            return field.get('$', '')
        elif isinstance(field, str):
            return field
        else:
            return ''
    
    async def _fetch_single_request(
        self,
        dataset_id: str,
        convert_to_japanese: bool = True,
        save_to_s3: bool = True
    ) -> Dict[str, Any]:
        """単一リクエストでのデータ取得"""
        try:
            start_time = datetime.now()
            
            params = {
                "appId": self.app_id,
                "statsDataId": dataset_id,
                "limit": LARGE_DATASET_THRESHOLD
            }
            
            data = await self._call_estat_api("getStatsData", params)
            
            stats_data = data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {})
            result_inf = stats_data.get('RESULT_INF', {})
            value_list = stats_data.get('DATA_INF', {}).get('VALUE', [])
            
            if isinstance(value_list, dict):
                value_list = [value_list]
            
            total_number = result_inf.get('TOTAL_NUMBER', 0)
            records_fetched = len(value_list)
            processing_time = (datetime.now() - start_time).total_seconds()
            
            completeness_ratio = records_fetched / total_number if total_number > 0 else 0
            
            logger.info(f"Total: {total_number:,}, Fetched: {records_fetched:,} ({completeness_ratio*100:.1f}%)")
            
            # S3に保存
            s3_location = None
            if save_to_s3 and self.s3_client:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                s3_key = f"raw/data/{dataset_id}_{timestamp}.json"
                
                try:
                    logger.info(f"Saving to S3: s3://{S3_BUCKET}/{s3_key}")
                    self.s3_client.put_object(
                        Bucket=S3_BUCKET,
                        Key=s3_key,
                        Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
                        ContentType='application/json'
                    )
                    s3_location = f"s3://{S3_BUCKET}/{s3_key}"
                    logger.info(f"Successfully saved to: {s3_location}")
                except Exception as e:
                    logger.error(f"S3 save failed: {e}")
                    # S3保存に失敗してもデータ取得は成功として扱う
                    s3_location = f"S3 save failed: {str(e)}"
            elif save_to_s3 and not self.s3_client:
                logger.warning("S3 save requested but S3 client not available")
                s3_location = "S3 client not available"
            
            sample_data = value_list[:5] if len(value_list) > 5 else value_list
            
            logger.info(f"Fetched {records_fetched:,} records in {processing_time:.1f}s")
            
            return {
                "success": True,
                "dataset_id": dataset_id,
                "records_fetched": records_fetched,
                "expected_records": total_number,
                "completeness_ratio": completeness_ratio,
                "processing_time": f"{processing_time:.1f}秒",
                "sample_data": sample_data,
                "s3_location": s3_location,
                "message": f"Successfully fetched {records_fetched:,} records (100.0% complete)"
            }
            
        except Exception as e:
            raise EStatError(f"Failed to fetch dataset: {e}")
    
    # ========================================
    # ツール4: fetch_large_dataset_complete
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
        大規模データセットの完全取得（最初のチャンクのみ）
        
        Args:
            dataset_id: データセットID
            max_records: 取得する最大レコード数
            chunk_size: 1回あたりの取得件数
            save_to_s3: S3に保存するか
            convert_to_japanese: コード→和名変換を実施するか
        
        Returns:
            取得結果
        """
        start_time = datetime.now()
        log_tool_call(logger, "fetch_large_dataset_complete", {
            "dataset_id": dataset_id,
            "max_records": max_records,
            "chunk_size": chunk_size
        })
        
        try:
            # Step 1: メタデータを取得して総レコード数を確認
            logger.info("Getting metadata...")
            meta_params = {"appId": self.app_id, "statsDataId": dataset_id}
            meta_data = await self._call_estat_api("getMetaInfo", meta_params)
            
            overall_total = meta_data.get('GET_META_INFO', {}).get(
                'METADATA_INF', {}
            ).get('TABLE_INF', {}).get('OVERALL_TOTAL_NUMBER', 0)
            
            # Step 2: 実際の総数をAPIで確認
            test_params = {
                "appId": self.app_id,
                "statsDataId": dataset_id,
                "limit": 1,
                "metaGetFlg": "Y"
            }
            test_data = await self._call_estat_api("getStatsData", test_params)
            
            actual_total = test_data.get('GET_STATS_DATA', {}).get(
                'STATISTICAL_DATA', {}
            ).get('RESULT_INF', {}).get('TOTAL_NUMBER', 0)
            
            logger.info(f"Metadata total: {overall_total:,}, Actual total: {actual_total:,}")
            
            # 取得対象レコード数を決定
            target_records = min(actual_total, max_records)
            
            if target_records <= chunk_size:
                logger.info(f"Small dataset ({target_records:,} records) - using single request")
                return await self.fetch_dataset_auto(dataset_id, save_to_s3, convert_to_japanese)
            
            # Step 3: 最初のチャンクのみ取得（タイムアウト対策）
            total_chunks = (target_records + chunk_size - 1) // chunk_size
            logger.info(f"Fetching first chunk: {chunk_size:,} records")
            logger.warning(f"Note: Due to MCP timeout limits, only first chunk will be retrieved")
            logger.info(f"Total chunks needed: {total_chunks}")
            
            # 最初のチャンクを取得
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
            
            if isinstance(chunk_values, dict):
                chunk_values = [chunk_values]
            
            logger.info(f"Retrieved {len(chunk_values):,} records")
            
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
                    logger.info(f"Saved chunk 1 to: {s3_location}")
                except Exception as e:
                    logger.warning(f"S3 save failed: {e}")
            
            processing_time = (datetime.now() - start_time).total_seconds()
            log_tool_result(logger, "fetch_large_dataset_complete", True, processing_time)
            
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
            logger.error(f"Error in fetch_large_dataset_complete: {e}", exc_info=True)
            return format_error_response(e, "fetch_large_dataset_complete", {
                "dataset_id": dataset_id,
                "suggestion": "Try reducing max_records or using fetch_dataset_filtered with specific filters"
            })
    
    # ========================================
    # ツール5: fetch_dataset_filtered
    # ========================================
    
    async def fetch_dataset_filtered(
        self,
        dataset_id: str,
        filters: Dict[str, str],
        save_to_s3: bool = True,
        convert_to_japanese: bool = True
    ) -> Dict[str, Any]:
        """
        カテゴリ指定での絞り込み取得
        
        Args:
            dataset_id: データセットID
            filters: フィルタ条件（例: {"area": "13000", "cat01": "A1101", "time": "2020"}）
            save_to_s3: S3に保存するか
            convert_to_japanese: コード→和名変換を実施するか
        
        Returns:
            取得結果
        """
        start_time = datetime.now()
        log_tool_call(logger, "fetch_dataset_filtered", {
            "dataset_id": dataset_id,
            "filters": filters
        })
        
        try:
            # Step 1: メタデータを取得してフィルタを検証
            logger.info("Validating filters against metadata...")
            meta_params = {"appId": self.app_id, "statsDataId": dataset_id}
            meta_data = await self._call_estat_api("getMetaInfo", meta_params)
            
            # メタデータからカテゴリ情報を抽出
            class_objs = meta_data.get('GET_META_INFO', {}).get(
                'METADATA_INF', {}
            ).get('CLASS_INF', {}).get('CLASS_OBJ', [])
            
            if not isinstance(class_objs, list):
                class_objs = [class_objs] if class_objs else []
            
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
            
            logger.info(f"Available categories: {list(available_categories.keys())}")
            
            # Step 2: フィルタを検証・変換
            validated_filters = {}
            filter_info = {}
            
            for filter_key, filter_value in filters.items():
                if filter_key in available_categories:
                    cat_info = available_categories[filter_key]
                    
                    # 値が日本語の場合、コードに変換
                    if filter_value in cat_info['code_to_name'].values():
                        for code, name in cat_info['code_to_name'].items():
                            if name == filter_value:
                                validated_filters[f"cd{filter_key.title()}"] = code
                                filter_info[filter_key] = name
                                logger.info(f"{filter_key}: '{filter_value}' → code '{code}'")
                                break
                    elif filter_value in cat_info['codes']:
                        validated_filters[f"cd{filter_key.title()}"] = filter_value
                        filter_info[filter_key] = cat_info['code_to_name'].get(filter_value, filter_value)
                        logger.info(f"{filter_key}: code '{filter_value}' → '{filter_info[filter_key]}'")
                    else:
                        logger.warning(f"{filter_key}: '{filter_value}' not found in available codes")
                        # 部分マッチを試行
                        partial_matches = [code for code in cat_info['codes'] if filter_value in code]
                        if partial_matches:
                            best_match = partial_matches[0]
                            validated_filters[f"cd{filter_key.title()}"] = best_match
                            filter_info[filter_key] = cat_info['code_to_name'].get(best_match, best_match)
                            logger.info(f"Using partial match: '{best_match}' → '{filter_info[filter_key]}'")
                        else:
                            return {
                                "success": False,
                                "error": f"Filter value '{filter_value}' not found for category '{filter_key}'",
                                "available_codes": cat_info['codes'][:20],
                                "suggestion": f"Use one of the available codes for {filter_key}"
                            }
                else:
                    logger.warning(f"Category '{filter_key}' not found in metadata")
                    return {
                        "success": False,
                        "error": f"Category '{filter_key}' not found in dataset metadata",
                        "available_categories": list(available_categories.keys()),
                        "suggestion": "Use one of the available category names"
                    }
            
            # Step 3: データ取得
            params = {
                "appId": self.app_id,
                "statsDataId": dataset_id,
                "limit": LARGE_DATASET_THRESHOLD,
                "metaGetFlg": "Y"
            }
            
            # 検証済みフィルタを追加
            params.update(validated_filters)
            
            logger.info(f"Fetching data with filters: {validated_filters}")
            
            data = await self._call_estat_api("getStatsData", params)
            
            # データを抽出
            stats_data = data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {})
            result_inf = stats_data.get('RESULT_INF', {})
            value_list = stats_data.get('DATA_INF', {}).get('VALUE', [])
            
            if isinstance(value_list, dict):
                value_list = [value_list]
            
            records_fetched = len(value_list)
            total_available = result_inf.get('TOTAL_NUMBER', 0)
            processing_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"Total available: {total_available:,}, Fetched: {records_fetched:,}")
            
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
                    logger.info(f"Saved to: {s3_location}")
                except Exception as e:
                    logger.warning(f"S3 save failed: {e}")
            
            sample_data = value_list[:5] if len(value_list) > 5 else value_list
            
            log_tool_result(logger, "fetch_dataset_filtered", True, processing_time)
            
            logger.info(f"Successfully fetched {records_fetched:,} records in {processing_time:.1f}s")
            
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
            logger.error(f"Error in fetch_dataset_filtered: {e}", exc_info=True)
            return format_error_response(e, "fetch_dataset_filtered", {
                "dataset_id": dataset_id,
                "filters": filters,
                "suggestion": "Check filter values and dataset_id, or try fetch_dataset_auto for smaller datasets"
            })
    
    # ========================================
    # ツール6: transform_to_parquet
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
        start_time = datetime.now()
        log_tool_call(logger, "transform_to_parquet", {
            "s3_json_path": s3_json_path,
            "data_type": data_type
        })
        
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
            
            logger.info(f"Reading JSON from s3://{bucket}/{key}")
            
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
            
            if not values:
                return {"success": False, "error": "No data found in JSON"}
            
            if isinstance(values, dict):
                values = [values]
            
            # DataFrameに変換
            records = []
            dataset_id = key.split('/')[-1].split('_')[0]
            
            for value in values:
                # 辞書でない場合はスキップ
                if not isinstance(value, dict):
                    logger.warning(f"Skipping non-dict value: {type(value)}")
                    continue
                
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
            
            logger.info(f"Converting {len(records)} records to DataFrame")
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
            
            processing_time = (datetime.now() - start_time).total_seconds()
            log_tool_result(logger, "transform_to_parquet", True, processing_time)
            
            logger.info(f"Converted {len(records)} records to Parquet: {s3_parquet_path}")
            
            return {
                "success": True,
                "source_path": s3_json_path,
                "target_path": s3_parquet_path,
                "records_processed": len(records),
                "data_type": data_type,
                "message": f"Successfully converted {len(records)} records to Parquet format"
            }
            
        except ImportError as e:
            logger.error(f"Required libraries not available: {e}")
            return {"success": False, "error": f"Required libraries not available: {str(e)}"}
        except Exception as e:
            logger.error(f"Error in transform_to_parquet: {e}", exc_info=True)
            return format_error_response(e, "transform_to_parquet", {
                "s3_json_path": s3_json_path
            })
    
    # ========================================
    # ツール7: load_to_iceberg
    # ========================================
    
    async def load_to_iceberg(
        self,
        table_name: str,
        s3_parquet_path: str,
        create_if_not_exists: bool = True
    ) -> Dict[str, Any]:
        """
        ParquetデータをIcebergテーブルに投入
        
        Args:
            table_name: テーブル名
            s3_parquet_path: S3上のParquetファイルパス
            create_if_not_exists: テーブルが存在しない場合に作成するか
        
        Returns:
            投入結果
        """
        start_time = datetime.now()
        log_tool_call(logger, "load_to_iceberg", {
            "table_name": table_name,
            "s3_parquet_path": s3_parquet_path
        })
        
        try:
            if not self.athena_client:
                return {"success": False, "error": "Athena client not available"}
            
            if not self.s3_client:
                return {"success": False, "error": "S3 client not available"}
            
            database = 'estat_db'
            # Athenaの出力場所を既存のバケットに設定
            output_location = f's3://{S3_BUCKET}/athena-results/'
            
            # 出力ディレクトリが存在することを確認
            try:
                self.s3_client.put_object(
                    Bucket=S3_BUCKET,
                    Key='athena-results/.keep',
                    Body=b''
                )
                logger.info(f"Athena output location ready: {output_location}")
            except Exception as e:
                logger.error(f"Failed to create athena-results directory: {e}")
                return {
                    "success": False,
                    "error": f"Failed to setup Athena output location: {str(e)}",
                    "message": f"S3バケット '{S3_BUCKET}' にathena-resultsディレクトリを作成できませんでした。バケットのアクセス権限を確認してください。"
                }
            
            # S3パスを解析
            if s3_parquet_path.startswith('s3://'):
                path_parts = s3_parquet_path[5:].split('/', 1)
                bucket = path_parts[0]
                parquet_key = path_parts[1]
            else:
                bucket = S3_BUCKET
                parquet_key = s3_parquet_path
            
            logger.info(f"Loading Parquet data to table: {table_name}")
            
            # 1. データベースの存在確認と作成
            logger.info(f"Checking database: {database}")
            try:
                import boto3
                glue_client = boto3.client('glue', region_name=AWS_REGION)
                glue_client.get_database(Name=database)
                logger.info(f"Database {database} exists")
            except Exception:
                logger.info(f"Creating database: {database}")
                create_db_query = f"CREATE DATABASE IF NOT EXISTS {database}"
                db_result = await self._execute_athena_query(create_db_query, database="default", output_location=output_location)
                if not db_result[0]:
                    return {"success": False, "error": f"Failed to create database: {db_result[1]}"}
            
            # 2. Icebergテーブル作成（存在しない場合）
            if create_if_not_exists:
                logger.info(f"Creating Iceberg table: {table_name}")
                
                # Athena Iceberg形式のテーブルとして作成
                # TBLPROPERTIES で 'table_type'='ICEBERG' を指定
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
                
                table_result = await self._execute_athena_query(create_table_query, database=database, output_location=output_location)
                if not table_result[0]:
                    return {"success": False, "error": f"Failed to create Iceberg table: {table_result[1]}"}
                
                logger.info(f"Iceberg table {table_name} created successfully")
            
            # 3. 外部テーブルを作成してParquetデータを読み込み
            external_table = f"{table_name}_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"Creating external table: {external_table}")
            
            # Parquetファイルのディレクトリを取得
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
            
            external_result = await self._execute_athena_query(create_external_query, database=database, output_location=output_location)
            if not external_result[0]:
                return {"success": False, "error": f"Failed to create external table: {external_result[1]}"}
            
            logger.info(f"External table created")
            
            # 4. データをメインテーブルに投入
            logger.info(f"Inserting data...")
            insert_query = f"""
            INSERT INTO {database}.{table_name}
            SELECT * FROM {database}.{external_table}
            """
            
            insert_result = await self._execute_athena_query(insert_query, database=database, output_location=output_location)
            if not insert_result[0]:
                # 外部テーブルを削除してからエラーを返す
                await self._execute_athena_query(f"DROP TABLE IF EXISTS {database}.{external_table}", database=database, output_location=output_location)
                return {"success": False, "error": f"Failed to insert data: {insert_result[1]}"}
            
            logger.info(f"Data inserted")
            
            # 5. レコード数を確認
            logger.info(f"Counting records...")
            count_query = f"SELECT COUNT(*) FROM {database}.{table_name}"
            count_result = await self._execute_athena_query(count_query, database=database, output_location=output_location)
            
            record_count = "不明"
            if count_result[0] and count_result[1]:
                try:
                    if isinstance(count_result[1], list) and len(count_result[1]) > 0:
                        record_count = count_result[1][0][0] if isinstance(count_result[1][0], list) else count_result[1][0]
                    else:
                        record_count = str(count_result[1])
                except:
                    record_count = "不明"
            
            # 6. クリーンアップ（外部テーブル）
            logger.info(f"Cleaning up external table...")
            drop_query = f"DROP TABLE IF EXISTS {database}.{external_table}"
            await self._execute_athena_query(drop_query, database=database, output_location=output_location)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            log_tool_result(logger, "load_to_iceberg", True, processing_time)
            
            logger.info(f"Loaded data to table: {record_count} records")
            
            return {
                "success": True,
                "table_name": table_name,
                "database": database,
                "records_loaded": record_count,
                "source_path": s3_parquet_path,
                "table_location": f"s3://{bucket}/iceberg-tables/{table_name}/",
                "message": f"Successfully loaded data to table {table_name} ({record_count} records)"
            }
            
        except Exception as e:
            logger.error(f"Error in load_to_iceberg: {e}", exc_info=True)
            return format_error_response(e, "load_to_iceberg", {
                "table_name": table_name
            })
    
    # ========================================
    # ツール8: analyze_with_athena
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
        start_time = datetime.now()
        log_tool_call(logger, "analyze_with_athena", {
            "table_name": table_name,
            "analysis_type": analysis_type
        })
        
        try:
            if not self.athena_client:
                return {"success": False, "error": "Athena client not available"}
            
            if not self.s3_client:
                return {"success": False, "error": "S3 client not available"}
            
            database = 'estat_db'
            # Athenaの出力場所を既存のバケットに設定
            output_location = f's3://{S3_BUCKET}/athena-results/'
            
            # 出力ディレクトリが存在することを確認
            try:
                self.s3_client.put_object(
                    Bucket=S3_BUCKET,
                    Key='athena-results/.keep',
                    Body=b''
                )
                logger.info(f"Athena output location ready: {output_location}")
            except Exception as e:
                logger.error(f"Failed to create athena-results directory: {e}")
                return {
                    "success": False,
                    "error": f"Failed to setup Athena output location: {str(e)}",
                    "message": f"S3バケット '{S3_BUCKET}' にathena-resultsディレクトリを作成できませんでした。バケットのアクセス権限を確認してください。"
                }
            
            results = {}
            
            if custom_query:
                # カスタムクエリを実行
                logger.info("Executing custom query")
                query_result = await self._execute_athena_query(custom_query, database=database, output_location=output_location)
                results["custom_query"] = {
                    "success": query_result[0],
                    "result": query_result[1] if query_result[0] else None,
                    "error": query_result[1] if not query_result[0] else None
                }
            
            elif analysis_type == "basic":
                # 基本分析
                logger.info("Executing basic analysis")
                
                # 1. レコード数
                count_query = f"SELECT COUNT(*) as total_records FROM {database}.{table_name}"
                count_result = await self._execute_athena_query(count_query, database=database, output_location=output_location)
                if count_result[0] and count_result[1]:
                    try:
                        results["total_records"] = int(count_result[1][0][0]) if count_result[1] else 0
                    except:
                        results["total_records"] = count_result[1]
                else:
                    results["total_records"] = None
                
                # 2. 基本統計
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
                stats_result = await self._execute_athena_query(stats_query, database=database, output_location=output_location)
                if stats_result[0] and stats_result[1]:
                    try:
                        row = stats_result[1][0]
                        results["statistics"] = {
                            "count": int(row[0]) if row[0] else 0,
                            "avg_value": float(row[1]) if row[1] else 0.0,
                            "min_value": float(row[2]) if row[2] else 0.0,
                            "max_value": float(row[3]) if row[3] else 0.0,
                            "sum_value": float(row[4]) if row[4] else 0.0
                        }
                    except Exception as e:
                        logger.warning(f"Failed to parse statistics: {e}")
                        results["statistics"] = stats_result[1]
                else:
                    results["statistics"] = None
                
                # 3. 年別集計
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
                year_result = await self._execute_athena_query(year_query, database=database, output_location=output_location)
                if year_result[0] and year_result[1]:
                    try:
                        results["by_year"] = [
                            {
                                "year": int(row[0]) if row[0] else 0,
                                "count": int(row[1]) if row[1] else 0,
                                "avg_value": float(row[2]) if row[2] else 0.0
                            }
                            for row in year_result[1]
                        ]
                    except Exception as e:
                        logger.warning(f"Failed to parse year data: {e}")
                        results["by_year"] = year_result[1]
                else:
                    results["by_year"] = None
                
            elif analysis_type == "advanced":
                # 高度分析
                logger.info("Executing advanced analysis")
                
                # 1. 地域別集計
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
                region_result = await self._execute_athena_query(region_query, database=database, output_location=output_location)
                results["by_region"] = region_result[1] if region_result[0] else None
                
                # 2. カテゴリ別集計
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
                category_result = await self._execute_athena_query(category_query, database=database, output_location=output_location)
                results["by_category"] = category_result[1] if category_result[0] else None
                
                # 3. 時系列トレンド
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
                trend_result = await self._execute_athena_query(trend_query, database=database, output_location=output_location)
                results["trend"] = trend_result[1] if trend_result[0] else None
            
            processing_time = (datetime.now() - start_time).total_seconds()
            log_tool_result(logger, "analyze_with_athena", True, processing_time)
            
            logger.info(f"Analysis completed in {processing_time:.1f}s")
            
            return {
                "success": True,
                "table_name": table_name,
                "database": database,
                "analysis_type": analysis_type,
                "results": results,
                "message": f"Successfully analyzed table {table_name}"
            }
            
        except Exception as e:
            logger.error(f"Error in analyze_with_athena: {e}", exc_info=True)
            return format_error_response(e, "analyze_with_athena", {
                "table_name": table_name
            })
    
    # ========================================
    # Athenaヘルパーメソッド
    # ========================================
    
    async def _execute_athena_query(
        self,
        query: str,
        database: str,
        output_location: str
    ) -> tuple:
        """
        Athenaクエリを実行
        
        Args:
            query: SQLクエリ
            database: データベース名
            output_location: 結果の出力先
        
        Returns:
            (success, result/error)
        """
        try:
            import time
            
            # クエリを実行（estat-mcp-workgroupを使用）
            # WorkGroupを明示的に指定することで、正しい出力場所を使用
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
            
            # クエリの完了を待機
            max_wait = 60  # 最大60秒
            wait_interval = 2
            elapsed = 0
            
            while elapsed < max_wait:
                response = self.athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                
                status = response['QueryExecution']['Status']['State']
                
                if status == 'SUCCEEDED':
                    # 結果を取得
                    result_response = self.athena_client.get_query_results(
                        QueryExecutionId=query_execution_id
                    )
                    
                    # 結果を解析
                    rows = result_response['ResultSet']['Rows']
                    if len(rows) > 1:
                        # ヘッダーを除く
                        data_rows = []
                        for row in rows[1:]:
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
            
        except Exception as e:
            return (False, str(e))
    
    # ========================================
    # ツール9: save_dataset_as_csv
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
            output_filename: 出力ファイル名（オプション）
        
        Returns:
            保存結果
        """
        start_time = datetime.now()
        log_tool_call(logger, "save_dataset_as_csv", {
            "dataset_id": dataset_id,
            "s3_json_path": s3_json_path,
            "local_json_path": local_json_path,
            "output_filename": output_filename
        })
        
        try:
            import pandas as pd
            import io
            
            # データソースの決定
            data = None
            
            if s3_json_path:
                # S3からJSONを読み込み
                logger.info(f"Loading from S3: {s3_json_path}")
                if not self.s3_client:
                    return {"success": False, "error": "S3 client not initialized"}
                
                # S3パスをパース
                if s3_json_path.startswith('s3://'):
                    s3_json_path = s3_json_path[5:]
                
                parts = s3_json_path.split('/', 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ''
                
                logger.info(f"Reading from S3 bucket: {bucket}, key: {key}")
                response = self.s3_client.get_object(Bucket=bucket, Key=key)
                data = json.loads(response['Body'].read().decode('utf-8'))
                
            elif local_json_path:
                # ローカルファイルから読み込み
                logger.info(f"Loading from local: {local_json_path}")
                with open(local_json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            else:
                # データソースが指定されていない場合、最新のデータを取得してS3に保存
                logger.info(f"No data source specified, fetching fresh data for dataset: {dataset_id}")
                fetch_result = await self.fetch_dataset_auto(dataset_id, save_to_s3=True, convert_to_japanese=True)
                
                if not fetch_result.get('success'):
                    return {
                        "success": False,
                        "error": "Failed to fetch dataset and no data source provided"
                    }
                
                # fetch_dataset_autoで保存されたS3パスを取得
                s3_location = fetch_result.get('s3_location')
                if not s3_location:
                    return {
                        "success": False,
                        "error": "Data was fetched but S3 location not available"
                    }
                
                logger.info(f"Data fetched and saved to: {s3_location}")
                logger.info(f"Now loading from S3 to convert to CSV...")
                
                # S3からJSONを読み込み
                if not self.s3_client:
                    return {"success": False, "error": "S3 client not initialized"}
                
                # S3パスをパース
                if s3_location.startswith('s3://'):
                    s3_location = s3_location[5:]
                
                parts = s3_location.split('/', 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ''
                
                logger.info(f"Reading from S3 bucket: {bucket}, key: {key}")
                response = self.s3_client.get_object(Bucket=bucket, Key=key)
                data = json.loads(response['Body'].read().decode('utf-8'))
                
                # データを抽出
                stats_data = data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {})
                value_list = stats_data.get('DATA_INF', {}).get('VALUE', [])
                
                if isinstance(value_list, dict):
                    value_list = [value_list]
                
                if not value_list:
                    return {"success": False, "error": "No data found in fetched JSON"}
                
                logger.info(f"Converting {len(value_list):,} records to CSV")
                
                # DataFrameに変換
                df = pd.DataFrame(value_list)
                
                # 出力ファイル名を決定
                if not output_filename:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    output_filename = f"{dataset_id}_{timestamp}.csv"
                
                # CSVに変換
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                csv_content = csv_buffer.getvalue()
                
                # S3に保存
                s3_key = f"csv/{output_filename}"
                
                if not self.s3_client:
                    return {"success": False, "error": "S3 client not initialized"}
                
                try:
                    logger.info(f"Saving CSV to S3: s3://{S3_BUCKET}/{s3_key}")
                    self.s3_client.put_object(
                        Bucket=S3_BUCKET,
                        Key=s3_key,
                        Body=csv_content.encode('utf-8-sig'),
                        ContentType='text/csv'
                    )
                    
                    s3_csv_location = f"s3://{S3_BUCKET}/{s3_key}"
                    
                    processing_time = (datetime.now() - start_time).total_seconds()
                    log_tool_result(logger, "save_dataset_as_csv", True, processing_time)
                    
                    logger.info(f"CSV saved to: {s3_csv_location}")
                    
                    return {
                        "success": True,
                        "dataset_id": dataset_id,
                        "records_count": len(value_list),
                        "columns": list(df.columns),
                        "s3_location": s3_csv_location,
                        "s3_bucket": S3_BUCKET,
                        "s3_key": s3_key,
                        "filename": output_filename,
                        "message": f"Successfully saved {len(value_list):,} records as CSV to S3"
                    }
                except Exception as s3_error:
                    logger.error(f"S3 save failed: {s3_error}")
                    return {
                        "success": False,
                        "error": f"Failed to save CSV to S3: {str(s3_error)}",
                        "dataset_id": dataset_id
                    }
            
            # 既存のJSONデータからCSV変換の処理
            if data:
                # データを抽出
                stats_data = data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {})
                value_list = stats_data.get('DATA_INF', {}).get('VALUE', [])
                
                if isinstance(value_list, dict):
                    value_list = [value_list]
                
                if not value_list:
                    return {"success": False, "error": "No data found in JSON"}
                
                logger.info(f"Converting {len(value_list):,} records to CSV")
                
                # DataFrameに変換
                df = pd.DataFrame(value_list)
                
                # CSVに変換
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                csv_content = csv_buffer.getvalue()
                
                # 出力ファイル名を決定
                if not output_filename:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    output_filename = f"{dataset_id}_{timestamp}.csv"
                
                # S3に保存
                s3_key = f"csv/{output_filename}"
                
                if not self.s3_client:
                    return {"success": False, "error": "S3 client not initialized"}
                
                try:
                    logger.info(f"Saving CSV to S3: s3://{S3_BUCKET}/{s3_key}")
                    self.s3_client.put_object(
                        Bucket=S3_BUCKET,
                        Key=s3_key,
                        Body=csv_content.encode('utf-8-sig'),
                        ContentType='text/csv'
                    )
                    
                    s3_location = f"s3://{S3_BUCKET}/{s3_key}"
                    
                    processing_time = (datetime.now() - start_time).total_seconds()
                    log_tool_result(logger, "save_dataset_as_csv", True, processing_time)
                    
                    logger.info(f"CSV saved to: {s3_location}")
                    
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
                except Exception as s3_error:
                    logger.error(f"S3 save failed: {s3_error}")
                    return {
                        "success": False,
                        "error": f"Failed to save CSV to S3: {str(s3_error)}",
                        "dataset_id": dataset_id
                    }
            
        except Exception as e:
            logger.error(f"Error in save_dataset_as_csv: {e}", exc_info=True)
            return format_error_response(e, "save_dataset_as_csv", {
                "dataset_id": dataset_id
            })
    
    # ========================================
    # ツール10: get_csv_download_url
    # ========================================
    
    async def get_csv_download_url(
        self,
        s3_path: str,
        expires_in: int = 3600,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        S3 CSVファイルの署名付きダウンロードURLを生成
        
        Args:
            s3_path: S3上のCSVファイルパス（s3://bucket/key 形式）
            expires_in: URL有効期限（秒）デフォルト3600秒（1時間）
            filename: ダウンロード時のファイル名（省略時はS3のキー名を使用）
        
        Returns:
            署名付きダウンロードURL
        """
        start_time = datetime.now()
        log_tool_call(logger, "get_csv_download_url", {
            "s3_path": s3_path,
            "expires_in": expires_in,
            "filename": filename
        })
        
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
            
            if not key:
                return {"success": False, "error": "Invalid S3 path: missing object key"}
            
            # ファイル名を決定
            if not filename:
                filename = key.split('/')[-1]
            
            logger.info(f"Generating presigned URL for: {bucket}/{key}")
            logger.info(f"Download filename: {filename}")
            logger.info(f"Expires in: {expires_in} seconds")
            
            # S3オブジェクトの存在確認
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
            except Exception as e:
                logger.warning(f"Could not verify S3 object: {e}")
                file_size = None
                file_size_mb = None
            
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
            
            processing_time = (datetime.now() - start_time).total_seconds()
            log_tool_result(logger, "get_csv_download_url", True, processing_time)
            
            logger.info(f"Generated presigned URL (expires in {expires_in}s)")
            
            result = {
                "success": True,
                "s3_path": s3_path,
                "s3_bucket": bucket,
                "s3_key": key,
                "download_url": presigned_url,
                "filename": filename,
                "expires_in_seconds": expires_in,
                "expires_at": (datetime.now().timestamp() + expires_in),
                "processing_time_seconds": round(processing_time, 2),
                "message": f"署名付きURLを生成しました。このURLをブラウザで開くか、curlでダウンロードしてください。有効期限: {expires_in}秒"
            }
            
            if file_size is not None:
                result["file_size_bytes"] = file_size
                result["file_size_mb"] = round(file_size_mb, 2)
            
            return result
            
        except self.s3_client.exceptions.NoSuchBucket as e:
            logger.error(f"S3 bucket not found: {e}")
            return {
                "success": False,
                "error": f"S3 bucket not found: {bucket}",
                "s3_path": s3_path
            }
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            processing_time = (datetime.now() - start_time).total_seconds()
            log_tool_result(logger, "get_csv_download_url", False, processing_time)
            return format_error_response(
                error=e,
                tool_name="get_csv_download_url",
                context={"s3_path": s3_path, "expires_in": expires_in}
            )
    
    # ========================================
    # ツール11: save_metadata_as_csv
    # ========================================
    
    async def save_metadata_as_csv(
        self,
        dataset_id: str,
        output_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        データセットのメタデータ情報（カテゴリー情報）をCSV形式でS3に保存
        
        Args:
            dataset_id: データセットID
            output_filename: 出力ファイル名（オプション）
        
        Returns:
            保存結果
        """
        start_time = datetime.now()
        log_tool_call(logger, "save_metadata_as_csv", {
            "dataset_id": dataset_id,
            "output_filename": output_filename
        })
        
        try:
            import pandas as pd
            import io
            
            # メタデータを取得
            logger.info(f"Fetching metadata for dataset: {dataset_id}")
            meta_params = {"appId": self.app_id, "statsDataId": dataset_id}
            meta_data = await self._call_estat_api("getMetaInfo", meta_params)
            
            # メタデータからカテゴリ情報を抽出
            metadata_inf = meta_data.get('GET_META_INFO', {}).get('METADATA_INF', {})
            table_inf = metadata_inf.get('TABLE_INF', {})
            class_inf = metadata_inf.get('CLASS_INF', {})
            class_obj_list = class_inf.get('CLASS_OBJ', [])
            
            if not isinstance(class_obj_list, list):
                class_obj_list = [class_obj_list] if class_obj_list else []
            
            if not class_obj_list:
                return {
                    "success": False,
                    "error": "No category information found in metadata",
                    "dataset_id": dataset_id
                }
            
            # 基本情報を取得
            stat_name = table_inf.get('STAT_NAME', {}).get('$', '不明')
            survey_date = table_inf.get('SURVEY_DATE', '不明')
            total_records = table_inf.get('OVERALL_TOTAL_NUMBER', 0)
            
            # カテゴリ情報をCSV用のレコードリストに変換
            records = []
            
            for class_obj in class_obj_list:
                category_id = class_obj.get('@id', '')
                category_name = class_obj.get('@name', '')
                class_values = class_obj.get('CLASS', [])
                
                if not isinstance(class_values, list):
                    class_values = [class_values] if class_values else []
                
                category_count = len(class_values)
                
                # 各カテゴリの値をレコードとして追加
                for class_value in class_values:
                    code = class_value.get('@code', '')
                    name = class_value.get('@name', '')
                    level = class_value.get('@level', '')
                    parent_code = class_value.get('@parentCode', '')
                    unit = class_value.get('@unit', '')
                    
                    records.append({
                        'カテゴリID': category_id,
                        'カテゴリ名': category_name,
                        'カテゴリ数': category_count,
                        'コード': code,
                        '名称': name,
                        'レベル': level,
                        '親コード': parent_code,
                        '単位': unit
                    })
            
            if not records:
                return {
                    "success": False,
                    "error": "No category data to save",
                    "dataset_id": dataset_id
                }
            
            logger.info(f"Converting {len(records)} category records to CSV")
            
            # DataFrameに変換
            df = pd.DataFrame(records)
            
            # CSVに変換
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
            csv_content = csv_buffer.getvalue()
            
            # 出力ファイル名を決定
            if not output_filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_filename = f"{dataset_id}_metadata_{timestamp}.csv"
            
            # S3に保存
            s3_key = f"csv/metadata/{output_filename}"
            
            if not self.s3_client:
                return {"success": False, "error": "S3 client not initialized"}
            
            try:
                logger.info(f"Saving metadata CSV to S3: s3://{S3_BUCKET}/{s3_key}")
                self.s3_client.put_object(
                    Bucket=S3_BUCKET,
                    Key=s3_key,
                    Body=csv_content.encode('utf-8-sig'),
                    ContentType='text/csv'
                )
                
                s3_location = f"s3://{S3_BUCKET}/{s3_key}"
                
                processing_time = (datetime.now() - start_time).total_seconds()
                log_tool_result(logger, "save_metadata_as_csv", True, processing_time)
                
                logger.info(f"Metadata CSV saved to: {s3_location}")
                
                return {
                    "success": True,
                    "dataset_id": dataset_id,
                    "stat_name": stat_name,
                    "survey_date": survey_date,
                    "total_records": total_records,
                    "category_records_count": len(records),
                    "categories_count": len(class_obj_list),
                    "columns": list(df.columns),
                    "s3_location": s3_location,
                    "s3_bucket": S3_BUCKET,
                    "s3_key": s3_key,
                    "filename": output_filename,
                    "message": f"Successfully saved {len(records):,} category records as CSV to S3"
                }
            except Exception as s3_error:
                logger.error(f"S3 save failed: {s3_error}")
                return {
                    "success": False,
                    "error": f"Failed to save metadata CSV to S3: {str(s3_error)}",
                    "dataset_id": dataset_id
                }
            
        except Exception as e:
            logger.error(f"Error in save_metadata_as_csv: {e}", exc_info=True)
            return format_error_response(e, "save_metadata_as_csv", {
                "dataset_id": dataset_id
            })
    
    # ========================================
    # ツール12: get_estat_table_url
    # ========================================
    
    def get_estat_table_url(
        self,
        dataset_id: str
    ) -> Dict[str, Any]:
        """
        統計表IDからe-Statホームページのリンクを生成
        
        Args:
            dataset_id: 統計表ID（例: 0002112323）
        
        Returns:
            e-Statホームページのリンク情報
        """
        start_time = datetime.now()
        log_tool_call(logger, "get_estat_table_url", {
            "dataset_id": dataset_id
        })
        
        try:
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
            
            # e-StatホームページのURLを生成
            table_url = f"https://www.e-stat.go.jp/dbview?sid={clean_id}"
            
            processing_time = (datetime.now() - start_time).total_seconds()
            log_tool_result(logger, "get_estat_table_url", True, processing_time)
            
            logger.info(f"Generated e-Stat URL for dataset {clean_id}")
            
            return {
                "success": True,
                "dataset_id": clean_id,
                "original_dataset_id": dataset_id,
                "table_url": table_url,
                "processing_time_seconds": round(processing_time, 4),
                "message": f"統計表のホームページURL: {table_url}"
            }
            
        except Exception as e:
            logger.error(f"Error in get_estat_table_url: {e}", exc_info=True)
            return format_error_response(e, "get_estat_table_url", {
                "dataset_id": dataset_id
            })
    
    # ========================================
    # ツール13: download_csv_from_s3
    # ========================================
    
    async def download_csv_from_s3(
        self,
        s3_path: str,
        local_path: Optional[str] = None,
        return_content: bool = False
    ) -> Dict[str, Any]:
        """
        S3に保存されたCSVファイルをダウンロード
        
        Args:
            s3_path: S3上のCSVファイルパス（s3://bucket/key 形式）
            local_path: ローカル保存先パス（return_content=Falseの場合のみ使用）
            return_content: Trueの場合、CSV内容を直接返す（リモートサーバー向け）
        
        Returns:
            ダウンロード結果（return_content=Trueの場合はcontentフィールドにCSV内容を含む）
        """
        start_time = datetime.now()
        log_tool_call(logger, "download_csv_from_s3", {
            "s3_path": s3_path,
            "local_path": local_path
        })
        
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
            
            if not key:
                return {"success": False, "error": "Invalid S3 path: missing object key"}
            
            # ローカルパスを決定
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
                logger.info(f"Created directory: {local_dir}")
            
            logger.info(f"Downloading from S3: {bucket}/{key}")
            logger.info(f"Saving to: {local_path}")
            
            # S3オブジェクトの存在確認
            try:
                head_response = self.s3_client.head_object(Bucket=bucket, Key=key)
                s3_file_size = head_response.get('ContentLength', 0)
                logger.info(f"S3 file size: {s3_file_size / (1024*1024):.2f} MB")
            except self.s3_client.exceptions.NoSuchKey:
                return {
                    "success": False,
                    "error": f"File not found in S3: {s3_path}",
                    "bucket": bucket,
                    "key": key
                }
            except Exception as e:
                logger.warning(f"Could not verify S3 object: {e}")
            
            # S3からダウンロード
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read()
            
            # return_content=Trueの場合、内容を直接返す（リモートサーバー向け）
            if return_content:
                try:
                    csv_content = content.decode('utf-8')
                    line_count = len(csv_content.split('\n'))
                    
                    processing_time = (datetime.now() - start_time).total_seconds()
                    log_tool_result(logger, "download_csv_from_s3", True, processing_time)
                    
                    logger.info(f"Returning CSV content: {len(content)} bytes, {line_count} lines")
                    
                    return {
                        "success": True,
                        "s3_path": s3_path,
                        "s3_bucket": bucket,
                        "s3_key": key,
                        "content": csv_content,
                        "file_size_bytes": len(content),
                        "file_size_mb": round(len(content) / (1024 * 1024), 2),
                        "line_count": line_count,
                        "processing_time_seconds": round(processing_time, 2),
                        "message": f"Successfully retrieved CSV content ({len(content) / (1024*1024):.2f} MB, {line_count} lines)"
                    }
                except UnicodeDecodeError as e:
                    logger.error(f"Failed to decode CSV as UTF-8: {e}")
                    return {
                        "success": False,
                        "error": f"Failed to decode CSV as UTF-8: {e}",
                        "s3_path": s3_path
                    }
            
            # ファイルに書き込み（従来の動作）
            if not local_path:
                filename = key.split('/')[-1]
                local_path = filename
            
            # パスを正規化（絶対パスに変換）
            import os
            local_path = os.path.abspath(local_path)
            
            # ダウンロード後の検証
            if not os.path.exists(local_path):
                return {
                    "success": False,
                    "error": f"File was not created at {local_path}"
                }
            
            # ファイルサイズを取得
            file_size = os.path.getsize(local_path)
            
            # サイズ検証
            if file_size == 0:
                logger.warning(f"Downloaded file is empty: {local_path}")
            
            file_size_mb = file_size / (1024 * 1024)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            log_tool_result(logger, "download_csv_from_s3", True, processing_time)
            
            logger.info(f"Downloaded: {file_size_mb:.2f} MB in {processing_time:.2f}s")
            
            # CSVファイルの行数をカウント（オプション）
            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    line_count = sum(1 for _ in f)
                logger.info(f"CSV contains {line_count:,} lines")
            except Exception as e:
                logger.warning(f"Could not count lines: {e}")
                line_count = None
            
            result = {
                "success": True,
                "s3_path": s3_path,
                "s3_bucket": bucket,
                "s3_key": key,
                "local_path": local_path,
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size_mb, 2),
                "processing_time_seconds": round(processing_time, 2),
                "message": f"Successfully downloaded CSV to {local_path} ({file_size_mb:.2f} MB)"
            }
            
            if line_count is not None:
                result["line_count"] = line_count
            
            return result
            
        except self.s3_client.exceptions.NoSuchBucket as e:
            logger.error(f"S3 bucket not found: {e}")
            return {
                "success": False,
                "error": f"S3 bucket not found: {bucket}",
                "s3_path": s3_path
            }
        except PermissionError as e:
            logger.error(f"Permission denied writing to {local_path}: {e}")
            return {
                "success": False,
                "error": f"Permission denied: Cannot write to {local_path}",
                "local_path": local_path
            }
        except Exception as e:
            logger.error(f"Error in download_csv_from_s3: {e}", exc_info=True)
            return format_error_response(e, "download_csv_from_s3", {
                "s3_path": s3_path,
                "local_path": local_path
            })
