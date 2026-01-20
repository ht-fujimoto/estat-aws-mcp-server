#!/usr/bin/env python3
"""
取得した家計調査データをParquet形式に変換してIcebergテーブルに投入
"""
import json
import boto3
import pandas as pd
from datetime import datetime

S3_BUCKET = 'estat-data-lake'
DATASET_ID = '0002070002'

def load_from_s3(s3_path):
    """S3からJSONデータを読み込み"""
    s3 = boto3.client('s3')
    bucket = s3_path.split('/')[2]
    key = '/'.join(s3_path.split('/')[3:])
    
    print(f"Loading from S3: {s3_path}")
    response = s3.get_object(Bucket=bucket, Key=key)
    data = json.loads(response['Body'].read())
    
    return data

def save_parquet_to_s3(df, dataset_id):
    """DataFrameをParquet形式でS3に保存"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    key = f'processed/{dataset_id}_complete_{timestamp}.parquet'
    s3_path = f's3://{S3_BUCKET}/{key}'
    
    # 一時ファイルに保存
    temp_file = f'/tmp/{dataset_id}_temp.parquet'
    df.to_parquet(temp_file, engine='pyarrow', compression='snappy', index=False)
    
    # S3にアップロード
    s3 = boto3.client('s3')
    with open(temp_file, 'rb') as f:
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=f)
    
    print(f"Saved Parquet to: {s3_path}")
    return s3_path

def main():
    """メイン処理"""
    print("=" * 70)
    print("家計調査データ Parquet変換")
    print("=" * 70)
    print()
    
    # 完全なデータセットを読み込み
    s3_json_path = f's3://{S3_BUCKET}/raw/data/{DATASET_ID}_chunk_999_20260120_090056.json'
    
    try:
        data = load_from_s3(s3_json_path)
        print(f"✓ Loaded {len(data):,} records")
        print()
        
        # DataFrameに変換
        print("Converting to DataFrame...")
        df = pd.DataFrame(data)
        print(f"✓ DataFrame shape: {df.shape}")
        print(f"  Columns: {list(df.columns)}")
        print()
        
        # Parquet形式で保存
        print("Saving as Parquet...")
        parquet_path = save_parquet_to_s3(df, DATASET_ID)
        print()
        
        print("=" * 70)
        print("✓ SUCCESS")
        print("=" * 70)
        print(f"Records: {len(df):,}")
        print(f"Parquet: {parquet_path}")
        print()
        print("次のステップ:")
        print(f"  Icebergテーブルに投入: mcp_estat_aws_remote_load_to_iceberg")
        print(f"    - table_name: economy_data")
        print(f"    - s3_parquet_path: {parquet_path}")
        print()
        
        return parquet_path
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    result = main()
    if not result:
        exit(1)
