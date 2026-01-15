#!/usr/bin/env python3
"""
取得したデータをS3にアップロードし、Parquet変換とIceberg投入を実行
"""

import boto3
import json
import os
from datetime import datetime

# 設定
S3_BUCKET = "estat-data-lake"
AWS_REGION = "ap-northeast-1"
DATASET_ID = "0004040079"

def upload_to_s3(local_file, s3_key):
    """ファイルをS3にアップロード"""
    try:
        s3_client = boto3.client('s3', region_name=AWS_REGION)
        
        print(f"📤 Uploading {local_file} to s3://{S3_BUCKET}/{s3_key}")
        
        with open(local_file, 'rb') as f:
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=f,
                ContentType='application/json'
            )
        
        s3_location = f"s3://{S3_BUCKET}/{s3_key}"
        print(f"✅ Successfully uploaded to: {s3_location}")
        return s3_location
        
    except Exception as e:
        print(f"❌ Upload failed: {str(e)}")
        return None

def main():
    # 最新のJSONファイルを探す
    json_files = [f for f in os.listdir('.') if f.startswith(f'{DATASET_ID}_complete_') and f.endswith('.json')]
    
    if not json_files:
        print(f"❌ No JSON files found for dataset {DATASET_ID}")
        return
    
    # 最新のファイルを選択
    latest_file = sorted(json_files)[-1]
    print(f"📁 Found file: {latest_file}")
    
    # ファイルサイズを確認
    file_size = os.path.getsize(latest_file)
    print(f"📊 File size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
    
    # S3キーを生成
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    s3_key = f"raw/data/{DATASET_ID}_complete_{timestamp}.json"
    
    # S3にアップロード
    s3_location = upload_to_s3(latest_file, s3_key)
    
    if s3_location:
        print(f"\n🎉 Upload completed!")
        print(f"📍 S3 Location: {s3_location}")
        print(f"\n📋 Next steps:")
        print(f"1. Transform to Parquet: mcp_estat_enhanced_transform_to_parquet")
        print(f"2. Load to Iceberg: mcp_estat_enhanced_load_to_iceberg")
        print(f"3. Analyze with Athena: mcp_estat_enhanced_analyze_with_athena")
        
        return {
            "success": True,
            "local_file": latest_file,
            "s3_location": s3_location,
            "file_size_mb": file_size/1024/1024
        }
    else:
        return {"success": False, "error": "Upload failed"}

if __name__ == "__main__":
    result = main()
    print(f"\n📊 Result: {result}")