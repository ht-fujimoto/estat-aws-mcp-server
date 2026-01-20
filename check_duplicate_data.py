#!/usr/bin/env python3
"""
Icebergテーブルの重複データを確認するスクリプト
"""
import boto3
import time
from datetime import datetime

def run_athena_query(query, database='estat_db'):
    """Athenaクエリを実行して結果を取得"""
    client = boto3.client('athena', region_name='ap-northeast-1')
    
    # クエリ実行
    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={
            'OutputLocation': 's3://estat-data-lake/athena-results/'
        }
    )
    
    query_execution_id = response['QueryExecutionId']
    print(f"クエリ実行ID: {query_execution_id}")
    
    # クエリ完了を待つ
    while True:
        response = client.get_query_execution(QueryExecutionId=query_execution_id)
        status = response['QueryExecution']['Status']['State']
        
        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        
        print(f"ステータス: {status}... 待機中")
        time.sleep(2)
    
    if status != 'SUCCEEDED':
        error = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
        raise Exception(f"クエリ失敗: {error}")
    
    # 結果を取得
    results = client.get_query_results(QueryExecutionId=query_execution_id)
    return results

def main():
    print("=" * 80)
    print("Icebergテーブル重複データ確認")
    print("=" * 80)
    print()
    
    # 1. データセットID別のレコード数を確認
    print("1. データセットID別のレコード数")
    print("-" * 80)
    query1 = """
    SELECT 
        stats_data_id,
        COUNT(*) as record_count
    FROM estat_db.economy_data
    GROUP BY stats_data_id
    ORDER BY record_count DESC
    """
    
    try:
        results = run_athena_query(query1)
        rows = results['ResultSet']['Rows']
        
        # ヘッダーをスキップして結果を表示
        for row in rows[1:]:
            cols = row['Data']
            stats_id = cols[0].get('VarCharValue', 'NULL')
            count = cols[1].get('VarCharValue', '0')
            print(f"  {stats_id}: {count:>10} レコード")
        
        print()
    except Exception as e:
        print(f"エラー: {e}")
        print()
    
    # 2. 総レコード数を確認
    print("2. 総レコード数")
    print("-" * 80)
    query2 = "SELECT COUNT(*) as total FROM estat_db.economy_data"
    
    try:
        results = run_athena_query(query2)
        total = results['ResultSet']['Rows'][1]['Data'][0].get('VarCharValue', '0')
        print(f"  総レコード数: {total}")
        print()
    except Exception as e:
        print(f"エラー: {e}")
        print()
    
    # 3. 年次別のレコード数（上位10件）
    print("3. 年次別のレコード数（上位10件）")
    print("-" * 80)
    query3 = """
    SELECT 
        year,
        COUNT(*) as record_count
    FROM estat_db.economy_data
    WHERE year IS NOT NULL
    GROUP BY year
    ORDER BY record_count DESC
    LIMIT 10
    """
    
    try:
        results = run_athena_query(query3)
        rows = results['ResultSet']['Rows']
        
        for row in rows[1:]:
            cols = row['Data']
            year = cols[0].get('VarCharValue', 'NULL')
            count = cols[1].get('VarCharValue', '0')
            print(f"  {year}: {count:>10} レコード")
        
        print()
    except Exception as e:
        print(f"エラー: {e}")
        print()
    
    # 4. S3上のParquetファイルを確認
    print("4. S3上のParquetファイル")
    print("-" * 80)
    s3 = boto3.client('s3', region_name='ap-northeast-1')
    
    try:
        response = s3.list_objects_v2(
            Bucket='estat-data-lake',
            Prefix='processed/'
        )
        
        if 'Contents' in response:
            for obj in response['Contents']:
                key = obj['Key']
                size = obj['Size']
                modified = obj['LastModified']
                print(f"  {key}")
                print(f"    サイズ: {size:,} bytes")
                print(f"    更新日時: {modified}")
                print()
        else:
            print("  Parquetファイルが見つかりません")
    except Exception as e:
        print(f"エラー: {e}")
    
    print("=" * 80)
    print("確認完了")
    print("=" * 80)

if __name__ == '__main__':
    main()
