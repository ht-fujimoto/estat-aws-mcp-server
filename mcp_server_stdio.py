#!/usr/bin/env python3
"""
MCP Stdio Server for e-Stat AWS
標準入出力を使用したMCPサーバー（Kiro互換性重視）
"""

import os
import sys
import json
import asyncio
from datetime import datetime

# MCPサーバーのインポート
sys.path.append(os.path.dirname(__file__))
from mcp_servers.estat_aws.server import EStatAWSServer

print(f"[{datetime.now()}] Starting e-Stat AWS MCP Server (Stdio)", file=sys.stderr)

# e-Stat AWSサーバーのインスタンス
estat_server = None

def init_estat_server():
    """e-Stat AWSサーバーを初期化"""
    global estat_server
    try:
        estat_server = EStatAWSServer()
        print(f"[{datetime.now()}] e-Stat AWS Server initialized successfully", file=sys.stderr)
    except Exception as e:
        print(f"[{datetime.now()}] Error initializing e-Stat AWS Server: {e}", file=sys.stderr)
        raise

# ツールマッピング
TOOLS = {
    "search_estat_data": {
        "handler": lambda **kwargs: estat_server.search_estat_data(**kwargs),
        "description": "自然言語でe-Statデータを検索し、キーワードサジェスト機能付きで最適なデータセットを提案",
        "parameters": {
            "query": {"type": "string", "required": True},
            "max_results": {"type": "integer", "default": 5},
            "auto_suggest": {"type": "boolean", "default": True},
            "scoring_method": {"type": "string", "default": "enhanced"}
        }
    },
    "apply_keyword_suggestions": {
        "handler": lambda **kwargs: estat_server.apply_keyword_suggestions_tool(**kwargs),
        "description": "ユーザーが承認したキーワード変換を適用して新しい検索クエリを生成",
        "parameters": {
            "original_query": {"type": "string", "required": True},
            "accepted_keywords": {"type": "object", "required": True}
        }
    },
    "fetch_dataset_auto": {
        "handler": lambda **kwargs: estat_server.fetch_dataset_auto(**kwargs),
        "description": "データセットを自動取得（デフォルトで全データ取得、大規模データは自動分割）",
        "parameters": {
            "dataset_id": {"type": "string", "required": True},
            "save_to_s3": {"type": "boolean", "default": True},
            "convert_to_japanese": {"type": "boolean", "default": True}
        }
    },
    "fetch_large_dataset_complete": {
        "handler": lambda **kwargs: estat_server.fetch_large_dataset_complete(**kwargs),
        "description": "大規模データセットの完全取得（分割取得対応、最大100万件）",
        "parameters": {
            "dataset_id": {"type": "string", "required": True},
            "max_records": {"type": "integer", "default": 1000000},
            "chunk_size": {"type": "integer", "default": 100000},
            "save_to_s3": {"type": "boolean", "default": True},
            "convert_to_japanese": {"type": "boolean", "default": True}
        }
    },
    "fetch_dataset_filtered": {
        "handler": lambda **kwargs: estat_server.fetch_dataset_filtered(**kwargs),
        "description": "10万件以上のデータセットをカテゴリ指定で絞り込み取得",
        "parameters": {
            "dataset_id": {"type": "string", "required": True},
            "filters": {"type": "object", "required": True},
            "save_to_s3": {"type": "boolean", "default": True},
            "convert_to_japanese": {"type": "boolean", "default": True}
        }
    },
    "transform_to_parquet": {
        "handler": lambda **kwargs: estat_server.transform_to_parquet(**kwargs),
        "description": "JSONデータをParquet形式に変換してS3に保存",
        "parameters": {
            "s3_json_path": {"type": "string", "required": True},
            "data_type": {"type": "string", "required": True},
            "output_prefix": {"type": "string", "required": False}
        }
    },
    "load_to_iceberg": {
        "handler": lambda **kwargs: estat_server.load_to_iceberg(**kwargs),
        "description": "ParquetデータをIcebergテーブルに投入",
        "parameters": {
            "table_name": {"type": "string", "required": True},
            "s3_parquet_path": {"type": "string", "required": True},
            "create_if_not_exists": {"type": "boolean", "default": True}
        }
    },
    "analyze_with_athena": {
        "handler": lambda **kwargs: estat_server.analyze_with_athena(**kwargs),
        "description": "Athenaで統計分析を実行",
        "parameters": {
            "table_name": {"type": "string", "required": True},
            "analysis_type": {"type": "string", "default": "basic"},
            "custom_query": {"type": "string", "required": False}
        }
    },
    "save_dataset_as_csv": {
        "handler": lambda **kwargs: estat_server.save_dataset_as_csv(**kwargs),
        "description": "取得したデータセットをCSV形式でS3に保存",
        "parameters": {
            "dataset_id": {"type": "string", "required": True},
            "s3_json_path": {"type": "string", "required": False},
            "local_json_path": {"type": "string", "required": False},
            "output_filename": {"type": "string", "required": False}
        }
    },
    "download_csv_from_s3": {
        "handler": lambda **kwargs: estat_server.download_csv_from_s3(**kwargs),
        "description": "S3に保存されたCSVファイルをローカルにダウンロード",
        "parameters": {
            "s3_path": {"type": "string", "required": True},
            "local_path": {"type": "string", "required": False}
        }
    }
}

async def handle_jsonrpc_message(data):
    """JSON-RPCメッセージを処理"""
    method = data.get('method')
    params = data.get('params', {})
    request_id = data.get('id')
    
    print(f"[{datetime.now()}] JSONRPC Request: method={method}, id={request_id}", file=sys.stderr)
    
    # 通知メッセージ（idがない）は無視
    if request_id is None:
        print(f"[{datetime.now()}] Notification received (no response needed): {method}", file=sys.stderr)
        return None
    
    # initialize メソッド
    if method == 'initialize':
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "estat-aws",
                    "version": "1.0.0"
                }
            }
        }
    
    # tools/list メソッド
    elif method == 'tools/list':
        tools_list = []
        for tool_name, tool_info in TOOLS.items():
            tools_list.append({
                "name": tool_name,
                "description": tool_info["description"],
                "inputSchema": {
                    "type": "object",
                    "properties": tool_info["parameters"]
                }
            })
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": tools_list
            }
        }
    
    # tools/call メソッド
    elif method == 'tools/call':
        tool_name = params.get('name')
        arguments = params.get('arguments', {})
        
        if tool_name not in TOOLS:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool not found: {tool_name}"
                }
            }
        
        # ツールを実行
        tool_handler = TOOLS[tool_name]["handler"]
        try:
            result = await tool_handler(**arguments)
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False)
                        }
                    ]
                }
            }
        
        except Exception as e:
            print(f"[{datetime.now()}] Tool execution error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Tool execution failed: {str(e)}"
                }
            }
    
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }

async def main():
    """メインループ"""
    # e-Stat AWSサーバーの初期化
    init_estat_server()
    
    print(f"[{datetime.now()}] MCP Server ready (stdio)", file=sys.stderr)
    
    # 標準入力からJSON-RPCメッセージを読み取り
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue
            
            # JSON-RPCメッセージをパース
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[{datetime.now()}] JSON parse error: {e}", file=sys.stderr)
                continue
            
            # メッセージを処理
            response = await handle_jsonrpc_message(data)
            
            # レスポンスを送信（通知メッセージの場合はNone）
            if response is not None:
                print(json.dumps(response, ensure_ascii=False))
                sys.stdout.flush()
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[{datetime.now()}] Unexpected error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)

if __name__ == '__main__':
    asyncio.run(main())