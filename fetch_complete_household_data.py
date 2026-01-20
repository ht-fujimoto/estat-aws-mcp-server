#!/usr/bin/env python3
"""
家計調査データ（0002070002）の完全取得スクリプト
103,629レコードを分割取得してS3に保存
"""
import os
import json
import time
import boto3
import requests
from datetime import datetime

# 環境変数から直接読み込み
ESTAT_API_KEY = os.environ.get('ESTAT_APP_ID')
if not ESTAT_API_KEY:
    # .envファイルから手動で読み込み
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('ESTAT_APP_ID='):
                    ESTAT_API_KEY = line.strip().split('=', 1)[1].strip('"').strip("'")
                    break
    except:
        pass

# デフォルトのAPIキー（MCPサーバーと同じ）
if not ESTAT_API_KEY:
    ESTAT_API_KEY = '320dd2fbff6974743e3f95505c9f346650ab635e'
DATASET_ID = '0002070002'
CHUNK_SIZE = 100000
S3_BUCKET = 'estat-data-lake'

def fetch_chunk(dataset_id, start_position, limit):
    """E-stat APIからデータチャンクを取得"""
    url = 'https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData'
    params = {
        'appId': ESTAT_API_KEY,
        'statsDataId': dataset_id,
        'startPosition': start_position,
        'limit': limit
    }
    
    print(f"Fetching records {start_position} to {start_position + limit - 1}...")
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()
    
    # デバッグ: レスポンス構造を確認
    if start_position == 1:
        print(f"Response keys: {list(data.keys())}")
        if 'GET_STATS_DATA' in data:
            print(f"GET_STATS_DATA keys: {list(data['GET_STATS_DATA'].keys())}")
    
    return data

def save_to_s3(data, chunk_num):
    """データをS3に保存"""
    s3 = boto3.client('s3')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    key = f'raw/data/{DATASET_ID}_chunk_{chunk_num:03d}_{timestamp}.json'
    
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(data, ensure_ascii=False, indent=2),
        ContentType='application/json'
    )
    
    return f's3://{S3_BUCKET}/{key}'

def main():
    """メイン処理"""
    print(f"Starting complete data fetch for dataset {DATASET_ID}")
    print(f"Target: 103,629 records")
    print(f"Chunk size: {CHUNK_SIZE:,} records")
    print("-" * 60)
    
    all_data = []
    chunk_num = 1
    start_position = 1
    total_fetched = 0
    
    while True:
        try:
            # チャンク取得
            result = fetch_chunk(DATASET_ID, start_position, CHUNK_SIZE)
            
            # データ抽出
            if 'GET_STATS_DATA' in result:
                # エラーチェック
                if 'RESULT' in result['GET_STATS_DATA']:
                    result_info = result['GET_STATS_DATA']['RESULT']
                    if start_position == 1:
                        print(f"API Result: {result_info}")
                    if result_info.get('STATUS') != 0:
                        print(f"API Error: {result_info.get('ERROR_MSG', 'Unknown error')}")
                        break
                
                if 'STATISTICAL_DATA' not in result['GET_STATS_DATA']:
                    print("No STATISTICAL_DATA in response")
                    break
                    
                data_list = result['GET_STATS_DATA']['STATISTICAL_DATA']['DATA_INF']['VALUE']
                
                if not data_list:
                    print("No more data to fetch")
                    break
                
                records_in_chunk = len(data_list)
                total_fetched += records_in_chunk
                all_data.extend(data_list)
                
                print(f"✓ Chunk {chunk_num}: {records_in_chunk:,} records (Total: {total_fetched:,})")
                
                # S3に保存
                s3_path = save_to_s3(data_list, chunk_num)
                print(f"  Saved to: {s3_path}")
                
                # 次のチャンク
                if records_in_chunk < CHUNK_SIZE:
                    print("\nReached end of dataset")
                    break
                
                start_position += CHUNK_SIZE
                chunk_num += 1
                
                # API制限対策
                time.sleep(1)
            else:
                print("Unexpected response format")
                break
                
        except Exception as e:
            print(f"Error fetching chunk {chunk_num}: {e}")
            break
    
    # 統合データを保存
    print("\n" + "=" * 60)
    print(f"Fetch complete!")
    print(f"Total records fetched: {total_fetched:,}")
    print(f"Total chunks: {chunk_num}")
    
    if all_data:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        combined_s3_path = save_to_s3(all_data, 999)  # 999 = combined
        print(f"\nCombined data saved to: {combined_s3_path}")
        print(f"Records in combined file: {len(all_data):,}")
        
        return combined_s3_path
    
    return None

if __name__ == '__main__':
    result = main()
    if result:
        print(f"\n✓ SUCCESS: Complete dataset available at {result}")
    else:
        print("\n✗ FAILED: Could not fetch complete dataset")
