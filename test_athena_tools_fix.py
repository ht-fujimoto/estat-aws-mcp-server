#!/usr/bin/env python3
"""
Athenaツール修正のテストスクリプト
load_to_icebergとanalyze_with_athenaの修正を検証
"""

import asyncio
import json
import sys
import os

# ローカルモジュールをインポート
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mcp_servers'))

from estat_aws.server import EStatAWSServer


async def test_athena_tools():
    """Athenaツールのテスト"""
    
    print("=" * 60)
    print("Athenaツール修正テスト")
    print("=" * 60)
    
    # サーバーインスタンスを作成
    server = EStatAWSServer()
    
    # AWS クライアントの確認
    print("\n1. AWS クライアントの確認")
    print("-" * 60)
    if server.s3_client:
        print("✓ S3 client: 利用可能")
    else:
        print("✗ S3 client: 利用不可")
        return False
    
    if server.athena_client:
        print("✓ Athena client: 利用可能")
    else:
        print("✗ Athena client: 利用不可")
        return False
    
    # S3バケットの確認
    print("\n2. S3バケットの確認")
    print("-" * 60)
    bucket_name = os.environ.get('S3_BUCKET', 'estat-data-lake')
    print(f"バケット名: {bucket_name}")
    
    try:
        response = server.s3_client.head_bucket(Bucket=bucket_name)
        print(f"✓ バケット '{bucket_name}' にアクセス可能")
    except Exception as e:
        print(f"✗ バケット '{bucket_name}' にアクセスできません: {e}")
        return False
    
    # Athena出力ディレクトリの作成テスト
    print("\n3. Athena出力ディレクトリの作成テスト")
    print("-" * 60)
    try:
        server.s3_client.put_object(
            Bucket=bucket_name,
            Key='athena-results/.keep',
            Body=b''
        )
        print(f"✓ athena-resultsディレクトリを作成しました")
    except Exception as e:
        print(f"✗ athena-resultsディレクトリの作成に失敗: {e}")
        return False
    
    # analyze_with_athenaのテスト（テーブルが存在しない場合のエラーハンドリング）
    print("\n4. analyze_with_athena のエラーハンドリングテスト")
    print("-" * 60)
    print("存在しないテーブルでテスト...")
    
    result = await server.analyze_with_athena(
        table_name="test_nonexistent_table",
        analysis_type="basic"
    )
    
    print(f"結果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get('success') == False:
        if 'error' in result:
            print("✓ エラーが適切に処理されました")
        else:
            print("✗ エラーメッセージが不足しています")
            return False
    else:
        print("⚠ テーブルが存在しないはずですが、成功として返されました")
    
    # load_to_icebergのテスト（パスが存在しない場合のエラーハンドリング）
    print("\n5. load_to_iceberg のエラーハンドリングテスト")
    print("-" * 60)
    print("存在しないS3パスでテスト...")
    
    result = await server.load_to_iceberg(
        table_name="test_table",
        s3_parquet_path="s3://nonexistent-bucket/nonexistent-path/data.parquet",
        create_if_not_exists=True
    )
    
    print(f"結果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get('success') == False:
        if 'error' in result:
            print("✓ エラーが適切に処理されました")
        else:
            print("✗ エラーメッセージが不足しています")
            return False
    else:
        print("⚠ パスが存在しないはずですが、成功として返されました")
    
    print("\n" + "=" * 60)
    print("テスト完了")
    print("=" * 60)
    
    return True


async def main():
    """メイン関数"""
    try:
        success = await test_athena_tools()
        if success:
            print("\n✓ すべてのテストが完了しました")
            sys.exit(0)
        else:
            print("\n✗ テストに失敗しました")
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
