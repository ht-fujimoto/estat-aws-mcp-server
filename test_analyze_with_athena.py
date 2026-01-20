#!/usr/bin/env python3
"""
analyze_with_athenaツールのテスト
"""
import requests
import json

# MCPエンドポイント
MCP_URL = "https://estat-mcp.snowmole.co.jp"

def test_analyze_with_athena():
    """analyze_with_athenaツールをテスト"""
    print("=" * 80)
    print("analyze_with_athenaツールのテスト")
    print("=" * 80)
    print()
    
    # 1. ツール一覧を取得
    print("1. ツール一覧を取得")
    print("-" * 80)
    
    try:
        response = requests.get(f"{MCP_URL}/tools", timeout=10)
        print(f"ステータスコード: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"レスポンス: {json.dumps(data, ensure_ascii=False, indent=2)}")
            
            # analyze_with_athenaツールを探す
            tools = data.get("tools", [])
            analyze_tool = None
            for tool in tools:
                if tool.get("name") == "analyze_with_athena":
                    analyze_tool = tool
                    break
            
            if analyze_tool:
                print()
                print("✓ analyze_with_athenaツールが見つかりました")
                print(f"説明: {analyze_tool.get('description')}")
                print(f"パラメータ: {json.dumps(analyze_tool.get('parameters', {}), ensure_ascii=False, indent=2)}")
            else:
                print()
                print("✗ analyze_with_athenaツールが見つかりません")
                print(f"利用可能なツール: {[t.get('name') for t in tools]}")
        else:
            print(f"エラー: {response.text}")
    except Exception as e:
        print(f"エラー: {e}")
    
    print()
    
    # 2. analyze_with_athenaツールを実行
    print("2. analyze_with_athenaツールを実行")
    print("-" * 80)
    
    try:
        payload = {
            "tool_name": "analyze_with_athena",
            "arguments": {
                "table_name": "economy_data",
                "analysis_type": "basic"
            }
        }
        
        print(f"リクエスト: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        print()
        
        response = requests.post(
            f"{MCP_URL}/execute",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"ステータスコード: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"レスポンス: {json.dumps(data, ensure_ascii=False, indent=2)}")
            
            if data.get("success"):
                print()
                print("✓ ツール実行成功")
            else:
                print()
                print(f"✗ ツール実行失敗: {data.get('error')}")
        else:
            print(f"エラー: {response.text}")
    except Exception as e:
        print(f"エラー: {e}")
    
    print()
    print("=" * 80)

if __name__ == '__main__':
    test_analyze_with_athena()
