#!/usr/bin/env python3
"""
JSONデータをCSVに変換するスクリプト
"""

import json
import pandas as pd
import sys
from datetime import datetime

def convert_json_to_csv(json_file, csv_file=None):
    """JSONファイルをCSVに変換"""
    print(f"📥 Loading JSON file: {json_file}")
    
    # JSONファイルを読み込み
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # データを抽出
    stats_data = data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {})
    value_list = stats_data.get('DATA_INF', {}).get('VALUE', [])
    
    if isinstance(value_list, dict):
        value_list = [value_list]
    
    print(f"📊 Total records: {len(value_list):,}")
    
    # DataFrameに変換
    df = pd.DataFrame(value_list)
    
    print(f"📋 Columns: {list(df.columns)}")
    print(f"📏 Shape: {df.shape}")
    
    # CSV出力ファイル名を決定
    if not csv_file:
        csv_file = json_file.replace('.json', '.csv')
    
    # CSVに保存（BOM付きUTF-8でExcel互換）
    print(f"💾 Saving to CSV: {csv_file}")
    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
    
    # ファイルサイズを確認
    import os
    file_size = os.path.getsize(csv_file)
    file_size_mb = file_size / (1024 * 1024)
    
    print(f"✅ CSV saved successfully!")
    print(f"📁 File: {csv_file}")
    print(f"📦 Size: {file_size_mb:.2f} MB")
    
    # サンプルデータを表示
    print(f"\n📋 Sample data (first 5 rows):")
    print(df.head().to_string())
    
    return csv_file

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 convert_to_csv.py <json_file> [csv_file]")
        sys.exit(1)
    
    json_file = sys.argv[1]
    csv_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    convert_json_to_csv(json_file, csv_file)
