#!/usr/bin/env python3
"""
save_metadata_as_csv ツールのテストスクリプト
"""

import asyncio
import sys
import os

# MCPサーバーのインポート
sys.path.append(os.path.dirname(__file__))
from mcp_servers.estat_aws.server import EStatAWSServer

async def test_save_metadata_as_csv():
    """メタデータCSV保存のテスト"""
    print("=" * 80)
    print("Test: save_metadata_as_csv")
    print("=" * 80)
    
    # サーバーインスタンスを作成
    server = EStatAWSServer()
    
    # テスト対象のデータセットID
    dataset_id = "0004019324"
    
    print(f"\n📊 Dataset ID: {dataset_id}")
    print(f"📝 Saving metadata as CSV...")
    
    # メタデータをCSVとして保存
    result = await server.save_metadata_as_csv(
        dataset_id=dataset_id
    )
    
    print("\n" + "=" * 80)
    print("Result:")
    print("=" * 80)
    
    if result.get('success'):
        print(f"✅ Success!")
        print(f"📊 統計名: {result.get('stat_name')}")
        print(f"📅 調査年: {result.get('survey_date')}")
        print(f"📈 総レコード数: {result.get('total_records'):,}件")
        print(f"📋 カテゴリ数: {result.get('categories_count')}")
        print(f"📝 カテゴリレコード数: {result.get('category_records_count'):,}件")
        print(f"📁 S3 Location: {result.get('s3_location')}")
        print(f"📄 Filename: {result.get('filename')}")
        print(f"💬 Message: {result.get('message')}")
        
        # get_csv_download_urlでダウンロードURLを取得
        print("\n" + "=" * 80)
        print("Getting download URL for metadata CSV...")
        print("=" * 80)
        
        s3_location = result.get('s3_location')
        if s3_location:
            url_result = await server.get_csv_download_url(
                s3_path=s3_location,
                expires_in=3600
            )
            
            if url_result.get('success'):
                print(f"\n✅ Download URL generated!")
                print(f"🔗 URL: {url_result.get('download_url')}")
                print(f"📄 Filename: {url_result.get('filename')}")
                print(f"⏰ Expires in: {url_result.get('expires_in_seconds')}秒")
                print(f"💬 Message: {url_result.get('message')}")
                
                return {
                    'metadata_csv': result,
                    'download_url': url_result
                }
            else:
                print(f"\n❌ Failed to generate download URL")
                print(f"Error: {url_result.get('error')}")
        
        return result
    else:
        print(f"❌ Failed")
        print(f"Error: {result.get('error')}")
        return result

async def test_both_csvs():
    """データCSVとメタデータCSVの両方を保存してURLを取得"""
    print("\n" + "=" * 80)
    print("Test: Save both data CSV and metadata CSV")
    print("=" * 80)
    
    server = EStatAWSServer()
    dataset_id = "0004019324"
    
    # 1. データCSVを保存（既存のツール）
    print("\n📊 Step 1: Saving data CSV...")
    data_csv_result = await server.save_dataset_as_csv(
        dataset_id=dataset_id
    )
    
    # 2. メタデータCSVを保存（新しいツール）
    print("\n📊 Step 2: Saving metadata CSV...")
    metadata_csv_result = await server.save_metadata_as_csv(
        dataset_id=dataset_id
    )
    
    # 3. 両方のダウンロードURLを取得
    print("\n" + "=" * 80)
    print("Getting download URLs...")
    print("=" * 80)
    
    results = {}
    
    if data_csv_result.get('success'):
        print(f"\n✅ Data CSV saved: {data_csv_result.get('s3_location')}")
        data_url_result = await server.get_csv_download_url(
            s3_path=data_csv_result.get('s3_location'),
            expires_in=3600
        )
        if data_url_result.get('success'):
            results['data_csv_url'] = data_url_result.get('download_url')
            print(f"🔗 データCSVのダウンロードURL:")
            print(f"   {data_url_result.get('download_url')}")
    
    if metadata_csv_result.get('success'):
        print(f"\n✅ Metadata CSV saved: {metadata_csv_result.get('s3_location')}")
        metadata_url_result = await server.get_csv_download_url(
            s3_path=metadata_csv_result.get('s3_location'),
            expires_in=3600
        )
        if metadata_url_result.get('success'):
            results['metadata_csv_url'] = metadata_url_result.get('download_url')
            print(f"🔗 メタデータCSVのダウンロードURL:")
            print(f"   {metadata_url_result.get('download_url')}")
    
    print("\n" + "=" * 80)
    print("Summary:")
    print("=" * 80)
    print(f"📊 データCSV: {data_csv_result.get('filename', 'N/A')}")
    print(f"   レコード数: {data_csv_result.get('records_count', 0):,}件")
    print(f"\n📋 メタデータCSV: {metadata_csv_result.get('filename', 'N/A')}")
    print(f"   カテゴリレコード数: {metadata_csv_result.get('category_records_count', 0):,}件")
    print(f"   カテゴリ数: {metadata_csv_result.get('categories_count', 0)}")
    
    return results

if __name__ == "__main__":
    print("\n🚀 Starting save_metadata_as_csv test...\n")
    
    # テスト1: メタデータCSVのみ
    result1 = asyncio.run(test_save_metadata_as_csv())
    
    # テスト2: データCSVとメタデータCSVの両方
    print("\n\n")
    result2 = asyncio.run(test_both_csvs())
    
    print("\n✅ All tests completed!")
