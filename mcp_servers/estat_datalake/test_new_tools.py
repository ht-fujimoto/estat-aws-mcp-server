#!/usr/bin/env python3
"""
新しく追加したMCPツールのテストスクリプト

テスト対象:
- fetch_dataset_filtered
- fetch_large_dataset_complete
- analyze_with_athena
"""

import json
import subprocess
import sys


def test_mcp_tool(tool_name: str, arguments: dict):
    """MCPツールをテスト"""
    print(f"\n{'='*60}")
    print(f"Testing: {tool_name}")
    print(f"Arguments: {json.dumps(arguments, ensure_ascii=False, indent=2)}")
    print(f"{'='*60}\n")
    
    # tools/call リクエストを作成
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    
    # MCPサーバーを起動してリクエストを送信
    try:
        process = subprocess.Popen(
            ["python3", "mcp_servers/estat_datalake/server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # リクエストを送信
        stdout, stderr = process.communicate(
            input=json.dumps(request) + "\n",
            timeout=120
        )
        
        # レスポンスを解析
        lines = stdout.strip().split('\n')
        for line in lines:
            if line.strip():
                try:
                    response = json.loads(line)
                    if "result" in response:
                        result_text = response["result"]["content"][0]["text"]
                        result = json.loads(result_text)
                        
                        print("✅ Success!")
                        print(f"Result: {json.dumps(result, ensure_ascii=False, indent=2)}")
                        return result
                    elif "error" in response:
                        print(f"❌ Error: {response['error']}")
                        return None
                except json.JSONDecodeError:
                    continue
        
        if stderr:
            print(f"⚠️  Stderr: {stderr}")
        
        return None
        
    except subprocess.TimeoutExpired:
        print("❌ Timeout: テストがタイムアウトしました")
        process.kill()
        return None
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None


def main():
    """メインテスト"""
    print("🧪 E-stat Data Lake MCP Server - 新ツールテスト")
    print("=" * 60)
    
    # テスト1: fetch_dataset_filtered
    print("\n📋 Test 1: fetch_dataset_filtered")
    print("小規模データセットをフィルタ付きで取得")
    test_mcp_tool("fetch_dataset_filtered", {
        "dataset_id": "0003410379",  # 経済センサス
        "filters": {
            "area": "13000",  # 東京都
            "time": "2021"    # 2021年
        },
        "save_to_s3": False  # テストなのでS3保存はスキップ
    })
    
    # テスト2: fetch_large_dataset_complete
    print("\n📋 Test 2: fetch_large_dataset_complete")
    print("大規模データセットを分割取得（テスト用に最大10万件）")
    test_mcp_tool("fetch_large_dataset_complete", {
        "dataset_id": "0003410379",
        "chunk_size": 50000,
        "max_records": 100000,
        "save_to_s3": False  # テストなのでS3保存はスキップ
    })
    
    # テスト3: analyze_with_athena (basic)
    print("\n📋 Test 3: analyze_with_athena (basic)")
    print("基本統計分析を実行")
    test_mcp_tool("analyze_with_athena", {
        "table_name": "population_data",
        "analysis_type": "basic"
    })
    
    # テスト4: analyze_with_athena (advanced)
    print("\n📋 Test 4: analyze_with_athena (advanced)")
    print("高度な統計分析を実行")
    test_mcp_tool("analyze_with_athena", {
        "table_name": "population_data",
        "analysis_type": "advanced"
    })
    
    # テスト5: analyze_with_athena (custom)
    print("\n📋 Test 5: analyze_with_athena (custom)")
    print("カスタムクエリで分析を実行")
    test_mcp_tool("analyze_with_athena", {
        "table_name": "population_data",
        "analysis_type": "custom",
        "custom_query": """
            SELECT year, COUNT(*) as count
            FROM estat_iceberg_db.population_data
            GROUP BY year
            ORDER BY year DESC
            LIMIT 10
        """
    })
    
    print("\n" + "=" * 60)
    print("✅ 全テスト完了")


if __name__ == "__main__":
    main()
