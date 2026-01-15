#!/usr/bin/env python3
"""
MCP Streamable HTTP Server for e-Stat AWS
MCPの公式streamable-http仕様に完全準拠
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from aiohttp import web
import traceback

# MCPサーバーのインポート
sys.path.append(os.path.dirname(__file__))
from mcp_servers.estat_aws.server import EStatAWSServer

# 環境変数
PORT = int(os.environ.get('PORT', 8080))
HOST = os.environ.get('TRANSPORT_HOST', '0.0.0.0')

print(f"[{datetime.now()}] Starting e-Stat AWS MCP Server (Streamable HTTP)")
print(f"[{datetime.now()}] Host: {HOST}:{PORT}")

# e-Stat AWSサーバーのインスタンス
estat_server = None

def init_estat_server():
    """e-Stat AWSサーバーを初期化"""
    global estat_server
    try:
        estat_server = EStatAWSServer()
        print(f"[{datetime.now()}] e-Stat AWS Server initialized successfully")
    except Exception as e:
        print(f"[{datetime.now()}] Error initializing e-Stat AWS Server: {e}")
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
    "get_csv_download_url": {
        "handler": lambda **kwargs: estat_server.get_csv_download_url(**kwargs),
        "description": "S3 CSVファイルの署名付きダウンロードURLを生成（ブラウザまたはcurlでダウンロード可能）",
        "parameters": {
            "s3_path": {"type": "string", "required": True},
            "expires_in": {"type": "integer", "default": 3600},
            "filename": {"type": "string", "required": False}
        }
    }
}

async def handle_mcp_endpoint(request):
    """統一されたMCPエンドポイント（GET/POST/DELETE対応）"""
    method = request.method
    client_ip = request.remote
    
    print(f"[{datetime.now()}] MCP Request: {method} from {client_ip}")
    
    if method == 'GET':
        # GETリクエスト - SSEストリームを開始
        accept_header = request.headers.get('Accept', '')
        print(f"[{datetime.now()}] GET request with Accept header: {accept_header}")
        
        if 'text/event-stream' in accept_header:
            print(f"[{datetime.now()}] Starting SSE stream for client: {client_ip}")
            return await handle_sse_stream(request)
        else:
            print(f"[{datetime.now()}] GET request without SSE Accept header - Method Not Allowed")
            return web.Response(status=405, text="Method Not Allowed: GET requests must include 'text/event-stream' in Accept header")
    
    elif method == 'POST':
        # POSTリクエスト - JSON-RPCメッセージを処理
        content_type = request.headers.get('Content-Type', '')
        print(f"[{datetime.now()}] POST request with Content-Type: {content_type}")
        
        try:
            data = await request.json()
            print(f"[{datetime.now()}] Received JSON-RPC data: {json.dumps(data, ensure_ascii=False)}")
            
            # JSON-RPCメッセージを処理
            response_data = await handle_jsonrpc_message(data)
            
            # 通知メッセージの場合はレスポンスを返さない
            if response_data is None:
                print(f"[{datetime.now()}] Notification processed - No Content response")
                return web.Response(status=204)  # No Content
            
            # 通常のレスポンスを返す
            print(f"[{datetime.now()}] Sending JSON-RPC response: {json.dumps(response_data, ensure_ascii=False)}")
            return web.json_response(response_data)
                
        except json.JSONDecodeError as e:
            error_msg = f"Parse error: Invalid JSON - {str(e)}"
            print(f"[{datetime.now()}] JSON decode error: {error_msg}")
            return web.json_response({
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": error_msg
                }
            }, status=400)
        except Exception as e:
            error_msg = f"Internal error: {str(e)}"
            print(f"[{datetime.now()}] MCP POST error: {error_msg}")
            traceback.print_exc()
            return web.json_response({
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": error_msg
                }
            }, status=500)
    
    elif method == 'DELETE':
        # DELETEリクエスト - セッション終了
        session_id = request.headers.get('Mcp-Session-Id')
        print(f"[{datetime.now()}] DELETE request - Session termination")
        if session_id:
            print(f"[{datetime.now()}] Session terminated: {session_id}")
        else:
            print(f"[{datetime.now()}] Session terminated (no session ID provided)")
        return web.Response(status=200, text="Session terminated")
    
    else:
        print(f"[{datetime.now()}] Unsupported method: {method}")
        return web.Response(status=405, text=f"Method Not Allowed: {method}")

async def handle_jsonrpc_message(data):
    """JSON-RPCメッセージを処理 - MCP仕様準拠"""
    request_id = None
    try:
        method = data.get('method')
        params = data.get('params', {})
        request_id = data.get('id')
        
        print(f"[{datetime.now()}] JSONRPC Request: method={method}, id={request_id}")
        
        # JSON-RPC 2.0仕様チェック
        if data.get('jsonrpc') != '2.0':
            error_response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: jsonrpc field must be '2.0'"
                }
            }
            print(f"[{datetime.now()}] JSON-RPC version error: {error_response}")
            return error_response
        
        # 通知メッセージ（idがない）の処理
        if request_id is None:
            print(f"[{datetime.now()}] Notification received (no response needed): {method}")
            # 通知には応答しない（MCP仕様）
            return None
        
        # initialize メソッド
        if method == 'initialize':
            print(f"[{datetime.now()}] Processing initialize request")
            result = {
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
            print(f"[{datetime.now()}] Initialize response: {json.dumps(result, ensure_ascii=False)}")
            return result
        
        # tools/list メソッド
        elif method == 'tools/list':
            print(f"[{datetime.now()}] Processing tools/list request")
            tools_list = []
            for tool_name, tool_info in TOOLS.items():
                # inputSchemaを正しく構築
                properties = {}
                required = []
                
                for param_name, param_info in tool_info["parameters"].items():
                    properties[param_name] = {
                        "type": param_info["type"]
                    }
                    if param_info.get("required", False):
                        required.append(param_name)
                
                input_schema = {
                    "type": "object",
                    "properties": properties
                }
                if required:
                    input_schema["required"] = required
                
                tools_list.append({
                    "name": tool_name,
                    "description": tool_info["description"],
                    "inputSchema": input_schema
                })
            
            result = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": tools_list
                }
            }
            print(f"[{datetime.now()}] Tools list response: {len(tools_list)} tools")
            return result
        
        # tools/call メソッド
        elif method == 'tools/call':
            tool_name = params.get('name')
            arguments = params.get('arguments', {})
            
            print(f"[{datetime.now()}] Processing tools/call request: {tool_name} with args: {arguments}")
            
            if tool_name not in TOOLS:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool not found: {tool_name}"
                    }
                }
                print(f"[{datetime.now()}] Tool not found error: {error_response}")
                return error_response
            
            # ツールを実行
            tool_handler = TOOLS[tool_name]["handler"]
            try:
                print(f"[{datetime.now()}] Executing tool: {tool_name}")
                result = await tool_handler(**arguments)
                
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, ensure_ascii=False, indent=2)
                            }
                        ]
                    }
                }
                print(f"[{datetime.now()}] Tool execution completed successfully: {tool_name}")
                return response
            
            except Exception as e:
                print(f"[{datetime.now()}] Tool execution error: {tool_name} - {e}")
                traceback.print_exc()
                error_response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error in {tool_name}: {str(e)}"
                    }
                }
                return error_response
        
        else:
            error_response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
            print(f"[{datetime.now()}] Method not found error: {error_response}")
            return error_response
    
    except Exception as e:
        print(f"[{datetime.now()}] JSON-RPC processing error: {e}")
        traceback.print_exc()
        error_response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }
        return error_response

async def handle_sse_stream(request):
    """SSEストリームを開始 - MCP streamable-http仕様準拠"""
    response = web.StreamResponse()
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE'
    
    await response.prepare(request)
    
    try:
        print(f"[{datetime.now()}] SSE connection established")
        
        # Requirements 2.2: SSE接続確立時に即座の初期化確認を送信
        initialization_message = "event: connection\ndata: {\"status\": \"ready\", \"timestamp\": \"" + datetime.now().isoformat() + "\"}\n\n"
        await response.write(initialization_message.encode('utf-8'))
        await response.drain()
        
        print(f"[{datetime.now()}] SSE initialization message sent")
        
        # Requirements 2.1: ハングを避けるため、ノンブロッキングで接続を維持
        # 長時間のsleepを避け、短い間隔でチェック
        connection_active = True
        while connection_active:
            try:
                # 短い間隔でチェック（ハング防止）
                await asyncio.sleep(1)
                
                # 接続状態を確認（transport層でのチェック）
                if response.transport is None or response.transport.is_closing():
                    print(f"[{datetime.now()}] SSE transport closed, ending connection")
                    break
                    
            except Exception as inner_e:
                print(f"[{datetime.now()}] SSE connection check error: {inner_e}")
                break
            
    except asyncio.CancelledError:
        print(f"[{datetime.now()}] SSE connection cancelled by client")
    except Exception as e:
        print(f"[{datetime.now()}] SSE error: {e}")
        traceback.print_exc()
    finally:
        # Requirements 2.5: 接続終了時の適切なリソースクリーンアップ
        print(f"[{datetime.now()}] SSE connection cleanup completed")
    
    return response


async def handle_health(request):
    """ヘルスチェック"""
    return web.json_response({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

async def handle_root(request):
    """ルートエンドポイント"""
    return web.json_response({
        "service": "e-Stat AWS MCP Server",
        "version": "1.0.0",
        "protocol": "MCP Streamable HTTP",
        "endpoints": ["/health", "/mcp"]
    })

def create_app():
    """Webアプリケーションを作成"""
    app = web.Application()
    
    # ルーティング
    app.router.add_get('/', handle_root)
    app.router.add_get('/health', handle_health)
    
    # MCP streamable-http エンドポイント
    app.router.add_get('/mcp', handle_mcp_endpoint)  # MCP GET (SSE)
    app.router.add_post('/mcp', handle_mcp_endpoint)  # MCP POST (JSONRPC)
    app.router.add_delete('/mcp', handle_mcp_endpoint)  # MCP DELETE (session termination)
    
    # 追加のMCPエンドポイント（仕様に応じて）
    app.router.add_get('/mcp/', handle_mcp_endpoint)
    app.router.add_post('/mcp/', handle_mcp_endpoint)
    app.router.add_delete('/mcp/', handle_mcp_endpoint)
    
    return app

if __name__ == '__main__':
    # e-Stat AWSサーバーの初期化
    init_estat_server()
    
    # Webサーバーを起動
    app = create_app()
    print(f"[{datetime.now()}] Starting HTTP server on {HOST}:{PORT}")
    print(f"[{datetime.now()}] MCP endpoint: /mcp")
    web.run_app(app, host=HOST, port=PORT)