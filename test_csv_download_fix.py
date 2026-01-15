#!/usr/bin/env python3
"""
CSVダウンロード機能のテストスクリプト
"""

import asyncio
import sys
import os

# パスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mcp_servers'))

from estat_aws.server import EStatAWSServer

async def test_download():
    """CSVダウンロード機能をテスト"""
    
    print("=" * 80)
    print("CSVダウンロード機能テスト")
    print("=" * 80)
    print()
    
    # サーバーインスタンス作成
    server = EStatAWSServer()
    
    # テスト1: 既存のCSVファイルをダウンロード
    print("【テスト1】既存のCSVファイルをダウンロード")
    result = await server.download_csv_from_s3(
        s3_path="s3://estat-data-lake/csv/hokkaido_population_2005.csv",
        local_path="test_download_1.csv"
    )
    print(f"結果: {result}")
    print()
    
    # テスト2: local_pathを省略（カレントディレクトリに保存）
    print("【テスト2】local_pathを省略")
    result = await server.download_csv_from_s3(
        s3_path="s3://estat-data-lake/csv/hokkaido_population_2005.csv"
    )
    print(f"結果: {result}")
    print()
    
    # テスト3: 存在しないファイル
    print("【テスト3】存在しないファイル")
    result = await server.download_csv_from_s3(
        s3_path="s3://estat-data-lake/csv/nonexistent_file.csv",
        local_path="test_download_3.csv"
    )
    print(f"結果: {result}")
    print()
    
    # テスト4: 無効なS3パス
    print("【テスト4】無効なS3パス")
    result = await server.download_csv_from_s3(
        s3_path="invalid_path",
        local_path="test_download_4.csv"
    )
    print(f"結果: {result}")
    print()
    
    # テスト5: サブディレクトリに保存
    print("【テスト5】サブディレクトリに保存")
    result = await server.download_csv_from_s3(
        s3_path="s3://estat-data-lake/csv/hokkaido_population_2005.csv",
        local_path="test_downloads/hokkaido_test.csv"
    )
    print(f"結果: {result}")
    print()
    
    print("=" * 80)
    print("テスト完了")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_download())
