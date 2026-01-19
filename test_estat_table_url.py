#!/usr/bin/env python3
"""
e-Stat統計表URLツールのテスト
"""

import sys
import os

# パスを追加
sys.path.append(os.path.dirname(__file__))

from mcp_servers.estat_aws.server import EStatAWSServer

def test_get_estat_table_url():
    """統計表URL生成ツールのテスト"""
    print("=" * 60)
    print("e-Stat統計表URL生成ツールのテスト")
    print("=" * 60)
    
    # サーバーインスタンスを作成
    server = EStatAWSServer()
    
    # テストケース
    test_cases = [
        {
            "name": "正常なID（数字のみ）",
            "dataset_id": "0002112323",
            "expected_url": "https://www.e-stat.go.jp/dbview?sid=0002112323"
        },
        {
            "name": "正常なID（別の例）",
            "dataset_id": "0003410379",
            "expected_url": "https://www.e-stat.go.jp/dbview?sid=0003410379"
        },
        {
            "name": "数字以外の文字を含むID",
            "dataset_id": "ID-0002112323",
            "expected_url": "https://www.e-stat.go.jp/dbview?sid=0002112323"
        },
        {
            "name": "空のID",
            "dataset_id": "",
            "expected_error": True
        },
        {
            "name": "数字を含まないID",
            "dataset_id": "INVALID",
            "expected_error": True
        }
    ]
    
    # テスト実行
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nテスト {i}: {test_case['name']}")
        print(f"入力: dataset_id='{test_case['dataset_id']}'")
        
        result = server.get_estat_table_url(test_case['dataset_id'])
        
        if test_case.get('expected_error'):
            if not result.get('success'):
                print(f"✓ 期待通りエラーが返されました")
                print(f"  エラー: {result.get('error')}")
                passed += 1
            else:
                print(f"✗ エラーが期待されましたが成功しました")
                failed += 1
        else:
            if result.get('success'):
                actual_url = result.get('table_url')
                expected_url = test_case['expected_url']
                
                if actual_url == expected_url:
                    print(f"✓ 正しいURLが生成されました")
                    print(f"  URL: {actual_url}")
                    passed += 1
                else:
                    print(f"✗ URLが一致しません")
                    print(f"  期待: {expected_url}")
                    print(f"  実際: {actual_url}")
                    failed += 1
            else:
                print(f"✗ エラーが発生しました: {result.get('error')}")
                failed += 1
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print(f"テスト結果: {passed}件成功 / {failed}件失敗 / 合計{len(test_cases)}件")
    print("=" * 60)
    
    return failed == 0

if __name__ == "__main__":
    success = test_get_estat_table_url()
    sys.exit(0 if success else 1)
