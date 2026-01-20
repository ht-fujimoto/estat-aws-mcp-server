#!/usr/bin/env python3
"""
正しいデータのみをIcebergテーブルに投入するスクリプト
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'datalake'))

from iceberg_table_manager import IcebergTableManager
import boto3

def main():
    print("=" * 80)
    print("正しいデータをIcebergテーブルに投入")
    print("=" * 80)
    print()
    
    # IcebergTableManagerを初期化
    athena_client = boto3.client('athena', region_name='ap-northeast-1')
    manager = IcebergTableManager(
        athena_client=athena_client,
        database='estat_db',
        s3_bucket='estat-data-lake'
    )
    
    # 1. 家計調査データを投入
    print("1. 家計調査データ（0002070002）を投入")
    print("-" * 80)
    parquet_path1 = 's3://estat-data-lake/processed/0002070002_chunk_999_20260120_090056.parquet'
    
    try:
        result = manager.load_parquet_to_iceberg(
            table_name='economy_data',
            parquet_s3_path=parquet_path1,
            create_if_not_exists=False
        )
        print(f"  ✓ 投入完了")
        print(f"  レコード数: {result.get('records_loaded', 'N/A')}")
        print()
    except Exception as e:
        print(f"  エラー: {e}")
        print()
    
    # 2. 労働力調査データを投入
    print("2. 労働力調査データ（0003217721）を投入")
    print("-" * 80)
    parquet_path2 = 's3://estat-data-lake/processed/0003217721_20260119_235415.parquet'
    
    try:
        result = manager.load_parquet_to_iceberg(
            table_name='economy_data',
            parquet_s3_path=parquet_path2,
            create_if_not_exists=False
        )
        print(f"  ✓ 投入完了")
        print(f"  レコード数: {result.get('records_loaded', 'N/A')}")
        print()
    except Exception as e:
        print(f"  エラー: {e}")
        print()
    
    # 3. 結果を確認
    print("3. 結果確認")
    print("-" * 80)
    
    import time
    
    def run_athena_query(query):
        """Athenaクエリを実行して結果を取得"""
        client = boto3.client('athena', region_name='ap-northeast-1')
        
        response = client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': 'estat_db'},
            ResultConfiguration={
                'OutputLocation': 's3://estat-data-lake/athena-results/'
            }
        )
        
        query_execution_id = response['QueryExecutionId']
        
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
        
        # 結果を取得
        results = client.get_query_results(QueryExecutionId=query_execution_id)
        return results
    
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
        results = run_athena_query(verify_query)
        rows = results['ResultSet']['Rows']
        
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
        results = run_athena_query(total_query)
        total = results['ResultSet']['Rows'][1]['Data'][0].get('VarCharValue', '0')
        
        print(f"  総レコード数: {total}")
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
