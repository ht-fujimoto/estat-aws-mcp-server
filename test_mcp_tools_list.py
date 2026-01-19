#!/usr/bin/env python3
"""
MCPサーバーのツール一覧を確認するテスト
"""

import sys
import os

# パスを追加
sys.path.append(os.path.dirname(__file__))

# server_http_mcp.pyからTOOLSをインポート
from server_http_mcp import TOOLS

def test_tools_list():
    """ツール一覧を表示"""
    print("=" * 80)
    print("estat-aws-remote MCPサーバー - ツール一覧")
    print("=" * 80)
    print(f"\n合計ツール数: {len(TOOLS)}\n")
    
    for i, (tool_name, tool_info) in enumerate(TOOLS.items(), 1):
        print(f"{i}. {tool_name}")
        print(f"   説明: {tool_info['description']}")
        
        # パラメータを表示
        params = tool_info['parameters']
        required_params = [k for k, v in params.items() if v.get('required', False)]
        optional_params = [k for k, v in params.items() if not v.get('required', False)]
        
        if required_params:
            print(f"   必須パラメータ: {', '.join(required_params)}")
        if optional_params:
            print(f"   オプション: {', '.join(optional_params)}")
        print()
    
    print("=" * 80)
    
    # 新しいツールが含まれているか確認
    expected_tools = [
        'search_estat_data',
        'apply_keyword_suggestions',
        'fetch_dataset_auto',
        'fetch_large_dataset_complete',
        'fetch_dataset_filtered',
        'save_dataset_as_csv',
        'get_estat_table_url',  # 新しいツール
        'get_csv_download_url',
        'download_csv_from_s3',
        'transform_to_parquet',
        'load_to_iceberg',
        'analyze_with_athena'
    ]
    
    print("\n✓ 期待されるツールの確認:")
    all_present = True
    for tool in expected_tools:
        if tool in TOOLS:
            print(f"  ✓ {tool}")
        else:
            print(f"  ✗ {tool} (見つかりません)")
            all_present = False
    
    if all_present:
        print(f"\n✓ 全ての期待されるツール（{len(expected_tools)}個）が登録されています！")
    else:
        print(f"\n✗ 一部のツールが見つかりません")
    
    return all_present

if __name__ == "__main__":
    success = test_tools_list()
    sys.exit(0 if success else 1)
