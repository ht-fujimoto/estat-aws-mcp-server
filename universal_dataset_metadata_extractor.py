#!/usr/bin/env python3
"""
汎用的なe-Statデータセットメタデータ抽出スクリプト
任意のデータセットIDから指定されたフィールドを取得
"""

import requests
import json
import sys
import time
import argparse
from typing import Dict, Any, Optional

class EstatMetadataExtractor:
    def __init__(self, api_key: str = "320dd2fbff6974743e3f95505c9f346650ab635e"):
        self.api_key = api_key
        self.base_url = "https://api.e-stat.go.jp/rest/3.0/app/json"
    
    def get_dataset_metadata(self, dataset_id: str, timeout: int = 60) -> Optional[Dict[str, Any]]:
        """
        指定されたデータセットIDのメタデータを取得
        """
        url = f"{self.base_url}/getMetaInfo"
        
        params = {
            'appId': self.api_key,
            'statsDataId': dataset_id,
            'lang': 'J'
        }
        
        try:
            print(f"データセット {dataset_id} のメタデータを取得中...")
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            
            data = response.json()
            
            # エラーチェック
            if 'GET_META_INFO' in data and 'RESULT' in data['GET_META_INFO']:
                result = data['GET_META_INFO']['RESULT']
                if result.get('STATUS') != 0:
                    print(f"APIエラー: {result.get('ERROR_MSG', 'Unknown error')}")
                    return None
            
            return data
            
        except requests.exceptions.Timeout:
            print(f"タイムアウト: データセット {dataset_id} の取得に失敗しました")
            return None
        except requests.exceptions.RequestException as e:
            print(f"API呼び出しエラー: {e}")
            return None
        except Exception as e:
            print(f"処理エラー: {e}")
            return None
    
    def extract_required_fields(self, metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        メタデータから必要なフィールドを抽出
        """
        try:
            if 'GET_META_INFO' not in metadata or 'METADATA_INF' not in metadata['GET_META_INFO']:
                print("メタデータの構造が期待されたものと異なります")
                return None
            
            table_inf = metadata['GET_META_INFO']['METADATA_INF']['TABLE_INF']
            
            # 必要なフィールドを抽出
            extracted_fields = {
                # 要求されたフィールド
                'statsCode': self._safe_get_nested(table_inf, ['STAT_NAME', '@code'], 'N/A'),
                'limit': 'N/A',  # メタデータAPIでは取得できない
                'updatedDate': table_inf.get('UPDATED_DATE', 'N/A'),
                'SURVEY_YEARS': table_inf.get('SURVEY_DATE', 'N/A'),
                'OPEN_YEARS': table_inf.get('OPEN_DATE', 'N/A'),
                'MAIN_CATEGORY': self._safe_get_nested(table_inf, ['MAIN_CATEGORY', '$'], 
                                                     table_inf.get('MAIN_CATEGORY', 'N/A')),
                'SUB_CATEGORY': self._safe_get_nested(table_inf, ['SUB_CATEGORY', '$'], 
                                                    table_inf.get('SUB_CATEGORY', 'N/A')),
                'OVERALL_TOTAL_NUMBER': table_inf.get('OVERALL_TOTAL_NUMBER', 'N/A'),
                'UPDATED_DATE': table_inf.get('UPDATED_DATE', 'N/A'),
                'STATISTICS_NAME_SPEC': table_inf.get('STATISTICS_NAME_SPEC', {}),
                'TABULATION_CATEGORY': self._safe_get_nested(table_inf, 
                                                           ['STATISTICS_NAME_SPEC', 'TABULATION_CATEGORY'], 'N/A'),
                'TABULATION_SUB_CATEGORY1': self._safe_get_nested(table_inf, 
                                                                ['STATISTICS_NAME_SPEC', 'TABULATION_SUB_CATEGORY1'], 'N/A'),
                'TABULATION_SUB_CATEGORY2': self._safe_get_nested(table_inf, 
                                                                ['STATISTICS_NAME_SPEC', 'TABULATION_SUB_CATEGORY2'], 'N/A'),
                'TABULATION_SUB_CATEGORY3': self._safe_get_nested(table_inf, 
                                                                ['STATISTICS_NAME_SPEC', 'TABULATION_SUB_CATEGORY3'], 'N/A'),
                'TABULATION_SUB_CATEGORY4': self._safe_get_nested(table_inf, 
                                                                ['STATISTICS_NAME_SPEC', 'TABULATION_SUB_CATEGORY4'], 'N/A'),
                'TABULATION_SUB_CATEGORY5': self._safe_get_nested(table_inf, 
                                                                ['STATISTICS_NAME_SPEC', 'TABULATION_SUB_CATEGORY5'], 'N/A'),
                
                # 追加の参考情報
                'datasetId': table_inf.get('@id', 'N/A'),
                'STAT_NAME': self._safe_get_nested(table_inf, ['STAT_NAME', '$'], 'N/A'),
                'GOV_ORG': self._safe_get_nested(table_inf, ['GOV_ORG', '$'], 'N/A'),
                'STATISTICS_NAME': table_inf.get('STATISTICS_NAME', 'N/A'),
                'TITLE': self._safe_get_nested(table_inf, ['TITLE', '$'], 'N/A'),
                'CYCLE': table_inf.get('CYCLE', 'N/A'),
                'COLLECT_AREA': table_inf.get('COLLECT_AREA', 'N/A'),
                'DESCRIPTION': table_inf.get('DESCRIPTION', 'N/A')
            }
            
            return extracted_fields
            
        except Exception as e:
            print(f"フィールド抽出エラー: {e}")
            return None
    
    def _safe_get_nested(self, data: Dict[str, Any], keys: list, default: Any = 'N/A') -> Any:
        """
        ネストされた辞書から安全に値を取得
        """
        try:
            current = data
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return default
            return current if current is not None else default
        except:
            return default
    
    def process_dataset(self, dataset_id: str, save_files: bool = True) -> Optional[Dict[str, Any]]:
        """
        データセットを処理してフィールドを抽出
        """
        # メタデータを取得
        metadata = self.get_dataset_metadata(dataset_id)
        if not metadata:
            return None
        
        # フィールドを抽出
        extracted_fields = self.extract_required_fields(metadata)
        if not extracted_fields:
            return None
        
        # ファイル保存
        if save_files:
            # 抽出フィールドを保存
            extracted_file = f"extracted_fields_{dataset_id}.json"
            with open(extracted_file, 'w', encoding='utf-8') as f:
                json.dump(extracted_fields, f, ensure_ascii=False, indent=2)
            print(f"抽出フィールドを {extracted_file} に保存しました")
            
            # 完全なメタデータも保存
            metadata_file = f"metadata_{dataset_id}.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            print(f"完全なメタデータを {metadata_file} に保存しました")
        
        return extracted_fields
    
    def display_results(self, fields: Dict[str, Any], dataset_id: str):
        """
        結果を表示
        """
        print(f"\n=== データセット {dataset_id} の抽出フィールド ===\n")
        
        # 要求されたフィールドを順番に表示
        required_fields = [
            'statsCode', 'limit', 'updatedDate', 'SURVEY_YEARS', 'OPEN_YEARS',
            'MAIN_CATEGORY', 'SUB_CATEGORY', 'OVERALL_TOTAL_NUMBER', 'UPDATED_DATE',
            'STATISTICS_NAME_SPEC', 'TABULATION_CATEGORY', 'TABULATION_SUB_CATEGORY1',
            'TABULATION_SUB_CATEGORY2', 'TABULATION_SUB_CATEGORY3', 'TABULATION_SUB_CATEGORY4',
            'TABULATION_SUB_CATEGORY5'
        ]
        
        print("【要求されたフィールド】")
        for field in required_fields:
            value = fields.get(field, 'N/A')
            if isinstance(value, dict):
                print(f"{field}: {json.dumps(value, ensure_ascii=False)}")
            else:
                print(f"{field}: {value}")
        
        print("\n【追加の参考情報】")
        additional_fields = [
            'datasetId', 'STAT_NAME', 'GOV_ORG', 'STATISTICS_NAME', 
            'TITLE', 'CYCLE', 'COLLECT_AREA', 'DESCRIPTION'
        ]
        
        for field in additional_fields:
            value = fields.get(field, 'N/A')
            if len(str(value)) > 100:  # 長い値は省略
                print(f"{field}: {str(value)[:100]}...")
            else:
                print(f"{field}: {value}")

def main():
    parser = argparse.ArgumentParser(description='e-Statデータセットメタデータ抽出ツール')
    parser.add_argument('dataset_id', help='データセットID (例: 0004019302)')
    parser.add_argument('--no-save', action='store_true', help='ファイル保存をスキップ')
    parser.add_argument('--timeout', type=int, default=60, help='APIタイムアウト秒数 (デフォルト: 60)')
    
    args = parser.parse_args()
    
    # 抽出器を初期化
    extractor = EstatMetadataExtractor()
    
    # データセットを処理
    fields = extractor.process_dataset(args.dataset_id, save_files=not args.no_save)
    
    if fields:
        extractor.display_results(fields, args.dataset_id)
        print(f"\n✅ データセット {args.dataset_id} の処理が完了しました")
    else:
        print(f"❌ データセット {args.dataset_id} の処理に失敗しました")
        sys.exit(1)

if __name__ == "__main__":
    # コマンドライン引数がない場合はテスト実行
    if len(sys.argv) == 1:
        print("テストモード: データセット 0004019302 で実行します")
        extractor = EstatMetadataExtractor()
        fields = extractor.process_dataset("0004019302")
        if fields:
            extractor.display_results(fields, "0004019302")
    else:
        main()