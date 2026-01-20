#!/usr/bin/env python3
"""
Icebergテーブルを再作成して、正しいデータのみを投入するスクリプト
"""
import boto3
import time
from datetime import datetime

def run_athena_query(query, database='estat_db', wait=True):
    """Athenaクエリを実行"""
    client = boto3.client('athena', region_name='ap-northeast-1')
    
    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={
            'OutputLocation': 's3://estat-data-lake/athena-results/'
        }
    )
    
    query_execution_id = response['QueryExecutionId']
    print(f"  クエリ実行ID: {query_execution_id}")
    
    if not wait:
        return query_execution_id
    
    # クエリ完了を待つ
    while True:
        response = client.get_query_execution(QueryExecutionId=query_execution_id)
        status = response['QueryExecution']['Status']['State']
        
        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        
        time.sleep(2)
    
    if status != 'SUCCEEDED':
        error = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
        raise Exception(f"クエリ失敗: {error}")
    
    print(f"  ✓ 完了")
    return query_execution_id

def main():
    print("=" * 80)
    print("Icebergテーブル再作成")
    print("=" * 80)
    print()
    
    # 1. 既存のテーブルを削除
    print("1. 既存のeconomy_dataテーブルを削除")
    print("-" * 80)
    drop_query = "DROP TABLE IF EXISTS estat_db.economy_data"
    
    try:
        run_athena_query(drop_query)
        print()
    except Exception as e:
        print(f"  エラー: {e}")
        print()
        return
    
    # 2. 新しいテーブルを作成
    print("2. 新しいeconomy_dataテーブルを作成")
    print("-" * 80)
    create_query = """
    CREATE TABLE estat_db.economy_data (
        stats_data_id STRING,
        year STRING,
        month STRING,
        area STRING,
        category STRING,
        value DOUBLE,
        unit STRING,
        annotation STRING
    )
    LOCATION 's3://estat-data-lake/iceberg-tables/economy_data/'
    TBLPROPERTIES (
        'table_type'='ICEBERG',
        'format'='parquet',
        'write_compression'='snappy'
    )
    """
    
    try:
        run_athena_query(create_query)
        print()
    except Exception as e:
        print(f"  エラー: {e}")
        print()
        return
    
    # 3. 正しいデータのみを投入
    print("3. 正しいデータを投入")
    print("-" * 80)
    
    # 家計調査データ（統合ファイル）
    print("  3.1. 家計調査データ（0002070002）")
    insert_query1 = """
    INSERT INTO estat_db.economy_data
    SELECT 
        stats_data_id,
        year,
        month,
        area,
        category,
        value,
        unit,
        annotation
    FROM parquet_scan('s3://estat-data-lake/processed/0002070002_chunk_999_20260120_090056.parquet')
    """
    
    try:
        run_athena_query(insert_query1)
        print()
    except Exception as e:
        print(f"    エラー: {e}")
        print()
    
    # 労働力調査データ
    print("  3.2. 労働力調査データ（0003217721）")
    insert_query2 = """
    INSERT INTO estat_db.economy_data
    SELECT 
        stats_data_id,
        year,
        month,
        area,
        category,
        value,
        unit,
        annotation
    FROM parquet_scan('s3://estat-data-lake/processed/0003217721_20260119_235415.parquet')
    """
    
    try:
        run_athena_query(insert_query2)
        print()
    except Exception as e:
        print(f"    エラー: {e}")
        print()
    
    # 4. 結果を確認
    print("4. 結果確認")
    print("-" * 80)
    
    # データセットID別のレコード数
    verify_query = """
    SELECT 
        stats_data_id,
        COUNT(*) as record_count
    FROM estat_db.economy_data
    GROUP BY stats_data_id
    ORDER BY stats_data_id
    """
    
    try:
        query_id = run_athena_query(verify_query)
        
        # 結果を取得
        client = boto3.client('athena', region_name='ap-northeast-1')
        results = client.get_query_results(QueryExecutionId=query_id)
        rows = results['ResultSet']['Rows']
        
        print()
        print("  データセットID別のレコード数:")
        for row in rows[1:]:
            cols = row['Data']
            stats_id = cols[0].get('VarCharValue', 'NULL')
            count = cols[1].get('VarCharValue', '0')
            print(f"    {stats_id}: {count:>10} レコード")
        
        print()
    except Exception as e:
        print(f"  エラー: {e}")
        print()
    
    # 総レコード数
    total_query = "SELECT COUNT(*) as total FROM estat_db.economy_data"
    
    try:
        query_id = run_athena_query(total_query)
        
        client = boto3.client('athena', region_name='ap-northeast-1')
        results = client.get_query_results(QueryExecutionId=query_id)
        total = results['ResultSet']['Rows'][1]['Data'][0].get('VarCharValue', '0')
        
        print(f"  総レコード数: {total}")
        print()
    except Exception as e:
        print(f"  エラー: {e}")
        print()
    
    print("=" * 80)
    print("再作成完了")
    print("=" * 80)
    print()
    print("期待値:")
    print("  0002070002（家計調査）: 103,629レコード")
    print("  0003217721（労働力調査）: 38,944レコード")
    print("  総レコード数: 142,573レコード")

if __name__ == '__main__':
    main()
