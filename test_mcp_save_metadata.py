#!/usr/bin/env python3
"""
MCP save_metadata_as_csv ツールのテストスクリプト
"""

import requests
import json

# MCP over HTTP エンドポイント
MCP_URL = "http://estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com/mcp"

def call_mcp_tool(tool_name, arguments):
    """MCPツールを呼び出す"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    
    print(f"\n📡 Calling MCP tool: {tool_name}")
    print(f"📝 Arguments: {json.dumps(arguments, ensure_ascii=False, indent=2)}")
    
    response = requests.post(MCP_URL, json=payload, timeout=120)
    response.raise_for_status()
    
    result = response.json()
    
    # MCPレスポンスから実際の結果を抽出
    mcp_result = result.get('result', {})
    
    # contentフィールドがある場合、その中のtextをパース
    if 'content' in mcp_result and isinstance(mcp_result['content'], list):
        for item in mcp_result['content']:
            if item.get('type') == 'text':
                try:
                    return json.loads(item.get('text', '{}'))
                except json.JSONDecodeError:
                    return {'error': 'Failed to parse response', 'raw': item.get('text')}
    
    return mcp_result

def main():
    """メインテスト"""
    print("=" * 80)
    print("MCP save_metadata_as_csv ツールのテスト")
    print("=" * 80)
    
    dataset_id = "0004019324"
    
    # 1. メタデータCSVを保存
    print(f"\n📊 Step 1: データセット {dataset_id} のメタデータをCSVとして保存")
    metadata_result = call_mcp_tool("save_metadata_as_csv", {
        "dataset_id": dataset_id
    })
    
    print("\n✅ Result:")
    print(json.dumps(metadata_result, ensure_ascii=False, indent=2))
    
    if metadata_result.get('success'):
        s3_location = metadata_result.get('s3_location')
        print(f"\n📁 S3 Location: {s3_location}")
        print(f"📋 カテゴリ数: {metadata_result.get('categories_count')}")
        print(f"📝 カテゴリレコード数: {metadata_result.get('category_records_count')}")
        
        # 2. ダウンロードURLを取得
        print(f"\n📊 Step 2: メタデータCSVのダウンロードURLを取得")
        url_result = call_mcp_tool("get_csv_download_url", {
            "s3_path": s3_location,
            "expires_in": 3600
        })
        
        print("\n✅ Result:")
        print(json.dumps(url_result, ensure_ascii=False, indent=2))
        
        if url_result.get('success'):
            download_url = url_result.get('download_url')
            print(f"\n🔗 メタデータCSVのダウンロードURL:")
            print(f"   {download_url}")
            print(f"\n⏰ 有効期限: {url_result.get('expires_in_seconds')}秒")
            print(f"📄 ファイル名: {url_result.get('filename')}")
            print(f"📦 ファイルサイズ: {url_result.get('file_size_mb')} MB")
    
    # 3. データCSVも保存してURLを取得
    print(f"\n\n📊 Step 3: データCSVも保存してURLを取得")
    data_result = call_mcp_tool("save_dataset_as_csv", {
        "dataset_id": dataset_id
    })
    
    print("\n✅ Result:")
    print(json.dumps(data_result, ensure_ascii=False, indent=2))
    
    if data_result.get('success'):
        s3_location = data_result.get('s3_location')
        print(f"\n📁 S3 Location: {s3_location}")
        
        # データCSVのダウンロードURLを取得
        print(f"\n📊 Step 4: データCSVのダウンロードURLを取得")
        data_url_result = call_mcp_tool("get_csv_download_url", {
            "s3_path": s3_location,
            "expires_in": 3600
        })
        
        if data_url_result.get('success'):
            download_url = data_url_result.get('download_url')
            print(f"\n🔗 データCSVのダウンロードURL:")
            print(f"   {download_url}")
    
    # 4. まとめ
    print("\n" + "=" * 80)
    print("まとめ")
    print("=" * 80)
    print(f"\n✅ 2つのCSVファイルが作成されました:")
    print(f"\n1️⃣ データCSV:")
    print(f"   - ファイル名: {data_result.get('filename', 'N/A')}")
    print(f"   - レコード数: {data_result.get('records_count', 0):,}件")
    print(f"   - S3パス: {data_result.get('s3_location', 'N/A')}")
    
    print(f"\n2️⃣ メタデータCSV:")
    print(f"   - ファイル名: {metadata_result.get('filename', 'N/A')}")
    print(f"   - カテゴリレコード数: {metadata_result.get('category_records_count', 0):,}件")
    print(f"   - カテゴリ数: {metadata_result.get('categories_count', 0)}")
    print(f"   - S3パス: {metadata_result.get('s3_location', 'N/A')}")
    
    print("\n✅ テスト完了!")

if __name__ == "__main__":
    main()
