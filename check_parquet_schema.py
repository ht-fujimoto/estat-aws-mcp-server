#!/usr/bin/env python3
"""
Parquetファイルのスキーマを確認するスクリプト
"""
import boto3
import pyarrow.parquet as pq
import io

def check_parquet_schema(bucket, key):
    """S3上のParquetファイルのスキーマを確認"""
    print(f"ファイル: s3://{bucket}/{key}")
    print("-" * 80)
    
    s3 = boto3.client('s3', region_name='ap-northeast-1')
    
    try:
        # S3からファイルを読み込む
        response = s3.get_object(Bucket=bucket, Key=key)
        parquet_data = response['Body'].read()
        
        # Parquetファイルを解析
        parquet_file = pq.ParquetFile(io.BytesIO(parquet_data))
        
        # スキーマを表示
        print("スキーマ:")
        print(parquet_file.schema)
        print()
        
        # メタデータを表示
        print("メタデータ:")
        print(f"  行数: {parquet_file.metadata.num_rows:,}")
        print(f"  列数: {parquet_file.metadata.num_columns}")
        print(f"  行グループ数: {parquet_file.metadata.num_row_groups}")
        print()
        
        # 最初の数行を表示
        print("サンプルデータ（最初の5行）:")
        table = parquet_file.read()
        df = table.to_pandas()
        print(df.head())
        print()
        
    except Exception as e:
        print(f"エラー: {e}")
        print()

def main():
    print("=" * 80)
    print("Parquetファイルのスキーマ確認")
    print("=" * 80)
    print()
    
    bucket = 'estat-data-lake'
    
    # 家計調査データ
    print("1. 家計調査データ（0002070002）")
    print("=" * 80)
    check_parquet_schema(bucket, 'processed/0002070002_chunk_999_20260120_090056.parquet')
    
    # 労働力調査データ
    print("2. 労働力調査データ（0003217721）")
    print("=" * 80)
    check_parquet_schema(bucket, 'processed/0003217721_20260119_235415.parquet')

if __name__ == '__main__':
    main()
