#!/usr/bin/env python3
"""
MCP CSV機能のテストスクリプト
save_dataset_as_csv と download_csv_from_s3 の動作確認
"""

import asyncio
import json
import sys
import os

# パスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), 'mcp_servers'))

from estat_analysis_hitl import EStatHITLServer


async def test_save_csv_from_local():
    """ローカルJSONからCSV保存のテスト"""
    print("=" * 80)
    print("Test 1: save_dataset_as_csv (from local JSON)")
    print("=" * 80)
    
    server = EStatHITLServer()
    
    # 既存のJSONファイルを使用
    json_file = "0000010209_complete_20260108_101506.json"
    
    if not os.path.exists(json_file):
        print(f"❌ Test file not found: {json_file}")
        return None
    
    print(f"📁 Using test file: {json_file}")
    
    result = await server.save_dataset_as_csv(
        dataset_id="0000010209",
        local_json_path=json_file,
        output_filename="test_medical_data.csv"
    )
    
    print("\n📊 Result:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    return result


async def test_save_csv_from_s3():
    """S3のJSONからCSV保存のテスト"""
    print("\n" + "=" * 80)
    print("Test 2: save_dataset_as_csv (from S3 JSON)")
    print("=" * 80)
    
    server = EStatHITLServer()
    
    s3_path = "s3://estat-data-lake/raw/data/0000010209_complete_20260108_101506.json"
    
    print(f"☁️  Using S3 file: {s3_path}")
    
    result = await server.save_dataset_as_csv(
        dataset_id="0000010209",
        s3_json_path=s3_path,
        output_filename="test_medical_data_from_s3.csv"
    )
    
    print("\n📊 Result:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    return result


async def test_download_csv():
    """S3からCSVダウンロードのテスト"""
    print("\n" + "=" * 80)
    print("Test 3: download_csv_from_s3")
    print("=" * 80)
    
    server = EStatHITLServer()
    
    # 既にアップロードされているCSVファイル
    s3_path = "s3://estat-data-lake/csv/medical_health_statistics_complete.csv"
    local_path = "downloaded_medical_health_statistics.csv"
    
    print(f"☁️  S3 path: {s3_path}")
    print(f"💾 Local path: {local_path}")
    
    result = await server.download_csv_from_s3(
        s3_path=s3_path,
        local_path=local_path
    )
    
    print("\n📊 Result:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    if result.get('success'):
        # ダウンロードしたファイルの最初の数行を表示
        print("\n📋 First 5 lines of downloaded CSV:")
        with open(local_path, 'r', encoding='utf-8-sig') as f:
            for i, line in enumerate(f):
                if i >= 5:
                    break
                print(f"  {line.rstrip()}")
    
    return result


async def main():
    """全テストを実行"""
    print("=" * 80)
    print("MCP CSV Functions Test Suite")
    print("=" * 80)
    print()
    
    # Test 1: ローカルJSONからCSV保存
    result1 = await test_save_csv_from_local()
    
    if result1 and result1.get('success'):
        print("\n✅ Test 1 PASSED")
    else:
        print("\n❌ Test 1 FAILED")
    
    # Test 2: S3のJSONからCSV保存
    result2 = await test_save_csv_from_s3()
    
    if result2 and result2.get('success'):
        print("\n✅ Test 2 PASSED")
    else:
        print("\n❌ Test 2 FAILED")
    
    # Test 3: S3からCSVダウンロード
    result3 = await test_download_csv()
    
    if result3 and result3.get('success'):
        print("\n✅ Test 3 PASSED")
    else:
        print("\n❌ Test 3 FAILED")
    
    # サマリー
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    
    tests_passed = sum([
        result1 and result1.get('success', False),
        result2 and result2.get('success', False),
        result3 and result3.get('success', False)
    ])
    
    print(f"Tests Passed: {tests_passed}/3")
    
    if tests_passed == 3:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed")


if __name__ == '__main__':
    asyncio.run(main())
