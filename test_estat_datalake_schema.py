#!/usr/bin/env python3
"""
estat-datalakeのスキーマ確認テスト
"""

import boto3
import pandas as pd
from io import BytesIO

# S3からParquetファイルを読み込む
s3_client = boto3.client('s3', region_name='ap-northeast-1')
response = s3_client.get_object(
    Bucket='estat-iceberg-datalake',
    Key='parquet/labor/0003217721_test.parquet'
)

# Parquetファイルを読み込む
df = pd.read_parquet(BytesIO(response['Body'].read()))

print("=== Parquetファイルのスキーマ ===")
print(f"カラム数: {len(df.columns)}")
print(f"カラム名: {list(df.columns)}")
print(f"\nデータ型:")
print(df.dtypes)
print(f"\nサンプルデータ（最初の3行）:")
print(df.head(3))
print(f"\n総レコード数: {len(df)}")
