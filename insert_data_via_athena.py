#!/usr/bin/env python3
"""
AthenaのCTAS（Create Table As Select）を使ってParquetデータをIcebergテーブルに投入
"""
import boto3
import time

def run_athena_query(query, database='estat_db'):
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
    
    # クエリ完了を待つ
    while True:
        response = client.get_query_execution(QueryExecutionId=query_execution_id)
        status = response['QueryExecution']['Status']['State']
        
        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        
        print(f"  ステータス: {status}... 待機中")
        time.sleep(2)
    
    if status != 'SUCCEEDED':
        error = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
        raise Exception(f"クエリ失敗: {error}")
    
    print(f"  ✓ 完了")
    return query_execution_id

def main():
    print("=" * 80)
    print("ParquetデータをIcebergテーブルに投入")
    print("=" * 80)
    print()
    
    # 1. 一時的な外部テーブルを作成（家計調査データ）
    print("1. 家計調査データ用の一時テーブルを作成")
    print("-" * 80)
    
    create_temp1 = """
    CREATE EXTERNAL TABLE IF NOT EXISTS estat_db.temp_household_data (
        stats_data_id STRING,
        year STRING,
        month STRING,
        area STRING,
        category STRING,
        value DOUBLE,
        unit STRING,
        annotation STRING
    )
    STORED AS PARQUET
    LOCATION 's3://estat-data-lake/processed/household/'
    """
    
    try:
        run_athena_query(create_temp1)
        print()
    except Exception as e:
        print(f"  エラー: {e}")
        print()
    
    # 2. Parquetファイルを一時的な場所にコピー
    print("2. Parquetファイルをコピー")
    print("-" * 80)
    
    s3 = boto3.client('s3', region_name='ap-northeast-1')
    
    # 家計調査データ
    print("  2.1. 家計調査データ")
    try:
        s3.copy_object(
            Bucket='estat-data-lake',
            CopySource={'Bucket': 'estat-data-lake', 'Key': 'processed/0002070002_chunk_999_20260120_090056.parquet'},
            Key='processed/household/data.parquet'
        )
        print("    ✓ コピー完了")
    except Exception as e:
        print(f"    エラー: {e}")
    
    # 労働力調査データ
    print("  2.2. 労働力調査データ")
    try:
        s3.copy_object(
            Bucket='estat-data-lake',
            CopySource={'Bucket': 'estat-data-lake', 'Key': 'processed/0003217721_20260119_235415.parquet'},
            Key='processed/labor/data.parquet'
        )
        print("    ✓ コピー完了")
    except Exception as e:
        print(f"    エラー: {e}")
    
    print()
    
    # 3. 一時テーブルからIcebergテーブルにデータを投入
    print("3. 家計調査データを投入")
    print("-" * 80)
    
    insert1 = """
    INSERT INTO estat_db.economy_data
    SELECT * FROM estat_db.temp_household_data
    """
    
    try:
        run_athena_query(insert1)
        print()
    except Exception as e:
        print(f"  エラー: {e}")
        print()
    
    # 4. 労働力調査データ用の一時テーブルを作成
    print("4. 労働力調査データ用の一時テーブルを作成")
    print("-" * 80)
    
    create_temp2 = """
    CREATE EXTERNAL TABLE IF NOT EXISTS estat_db.temp_labor_data (
        stats_data_id STRING,
        year STRING,
        month STRING,
        area STRING,
        category STRING,
        value DOUBLE,
        unit STRING,
        annotation STRING
    )
    STORED AS PARQUET
    LOCATION 's3://estat-data-lake/processed/labor/'
    """
    
    try:
        run_athena_query(create_temp2)
        print()
    except Exception as e:
        print(f"  エラー: {e}")
        print()
    
    # 5. 労働力調査データを投入
    print("5. 労働力調査データを投入")
    print("-" * 80)
    
    insert2 = """
    INSERT INTO estat_db.economy_data
    SELECT * FROM estat_db.temp_labor_data
    """
    
    try:
        run_athena_query(insert2)
        print()
    except Exception as e:
        print(f"  エラー: {e}")
        print()
    
    # 6. 結果を確認
    print("6. 結果確認")
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
    
    # 7. 一時テーブルを削除
    print("7. 一時テーブルを削除")
    print("-" * 80)
    
    try:
        run_athena_query("DROP TABLE IF EXISTS estat_db.temp_household_data")
        run_athena_query("DROP TABLE IF EXISTS estat_db.temp_labor_data")
        print()
    except Exception as e:
        print(f"  エラー: {e}")
        print()
    
    print("=" * 80)
    print("投入完了")
    print("=" * 80)
    print()
    print("期待値:")
    print("  0002070002（家計調査）: 103,629レコード")
    print("  0003217721（労働力調査）: 38,944レコード")
    print("  総レコード数: 142,573レコード")

if __name__ == '__main__':
    main()
