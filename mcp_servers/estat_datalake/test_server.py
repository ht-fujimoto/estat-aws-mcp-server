#!/usr/bin/env python3
"""
E-stat Data Lake MCP Server テストスクリプト
"""

import asyncio
import json
from server import EStatDataLakeServer


async def test_complete_ingestion():
    """完全取り込みのテスト"""
    print("=" * 60)
    print("E-stat Data Lake MCP Server テスト")
    print("=" * 60)
    print()
    
    # サーバーインスタンス
    server = EStatDataLakeServer()
    
    # テストデータ
    s3_input_path = "s3://estat-data-lake/raw/data/0004021107_20260119_052606.json"
    dataset_id = "0004021107"
    dataset_name = "年齢（各歳），男女別人口及び人口性比"
    domain = "population"
    
    print(f"テストデータ:")
    print(f"  S3パス: {s3_input_path}")
    print(f"  データセットID: {dataset_id}")
    print(f"  データセット名: {dataset_name}")
    print(f"  ドメイン: {domain}")
    print()
    
    # テスト1: データ読み込み
    print("テスト1: データ読み込み")
    print("-" * 60)
    result1 = await server.load_data_from_s3(s3_input_path)
    print(json.dumps(result1, ensure_ascii=False, indent=2))
    print()
    
    if not result1["success"]:
        print("❌ データ読み込みに失敗しました")
        return
    
    # テスト2: データ変換
    print("テスト2: データ変換")
    print("-" * 60)
    result2 = await server.transform_data(s3_input_path, domain, dataset_id)
    print(json.dumps(result2, ensure_ascii=False, indent=2))
    print()
    
    if not result2["success"]:
        print("❌ データ変換に失敗しました")
        return
    
    # テスト3: データ品質検証
    print("テスト3: データ品質検証")
    print("-" * 60)
    result3 = await server.validate_data_quality(s3_input_path, domain, dataset_id)
    print(json.dumps(result3, ensure_ascii=False, indent=2))
    print()
    
    if not result3["success"] or not result3["is_valid"]:
        print("❌ データ品質検証に失敗しました")
        return
    
    # テスト4: Parquet保存
    print("テスト4: Parquet保存")
    print("-" * 60)
    s3_output_path = f"s3://estat-iceberg-datalake/parquet/{domain}/{dataset_id}.parquet"
    result4 = await server.save_to_parquet(s3_input_path, s3_output_path, domain, dataset_id)
    print(json.dumps(result4, ensure_ascii=False, indent=2))
    print()
    
    if not result4["success"]:
        print("❌ Parquet保存に失敗しました")
        return
    
    # テスト5: Icebergテーブル作成
    print("テスト5: Icebergテーブル作成")
    print("-" * 60)
    result5 = await server.create_iceberg_table(domain)
    print(json.dumps(result5, ensure_ascii=False, indent=2))
    print()
    
    # テスト6: 完全取り込み
    print("テスト6: 完全取り込み")
    print("-" * 60)
    result6 = await server.ingest_dataset_complete(
        s3_input_path,
        dataset_id,
        dataset_name,
        domain
    )
    print(json.dumps(result6, ensure_ascii=False, indent=2))
    print()
    
    if result6["success"]:
        print("=" * 60)
        print("✅ 全てのテストが成功しました！")
        print("=" * 60)
    else:
        print("=" * 60)
        print("❌ 完全取り込みに失敗しました")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_complete_ingestion())
