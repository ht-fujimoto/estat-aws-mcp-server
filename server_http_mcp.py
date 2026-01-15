#!/usr/bin/env python3
"""
MCP over HTTP Server for e-Stat AWS
Kiroのstreamable-httpトランスポートに完全対応
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

print(f"[{datetime.now()}] Starting e-Stat AWS MCP Server (MCP over HTTP)")
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
    "download_csv_from_s3": {
        "handler": lambda **kwargs: estat_server.download_csv_from_s3(**kwargs),
        "description": "S3に保存されたCSVファイルをローカルにダウンロード",
        "parameters": {
            "s3_path": {"type": "string", "required": True},
            "local_path": {"type": "string", "required": False}
        }
    }
}

async def handle_jsonrpc(request):
    """MCP JSONRPC リクエストを処理"""
    try:
        data = await request.json()
        
        method = data.get('method')
        params = data.get('params', {})
        request_id = data.get('id')
        
        print(f"[{datetime.now()}] JSONRPC Request: method={method}, id={request_id}")
        
        # 通知メッセージ（idがない）は無視して200を返す
        if request_id is None:
            print(f"[{datetime.now()}] Notification received (no response needed): {method}")
            return web.json_response({"status": "ok"})
        
        # initialize メソッド
        if method == 'initialize':
            response = {
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
            return web.json_response(response)
        
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
            
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": tools_list
                }
            }
            return web.json_response(response)
        
        # tools/call メソッド
        elif method == 'tools/call':
            tool_name = params.get('name')
            arguments = params.get('arguments', {})
            
            if tool_name not in TOOLS:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool not found: {tool_name}"
                    }
                }
                return web.json_response(response, status=404)
            
            # ツールを実行
            tool_handler = TOOLS[tool_name]["handler"]
            try:
                result = await tool_handler(**arguments)
                
                response = {
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
                return web.json_response(response)
            
            except Exception as e:
                print(f"[{datetime.now()}] Tool execution error: {e}")
                traceback.print_exc()
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": f"Tool execution failed: {str(e)}"
                    }
                }
                return web.json_response(response, status=500)
        
        else:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
            return web.json_response(response, status=404)
    
    except Exception as e:
        print(f"[{datetime.now()}] Request handling error: {e}")
        traceback.print_exc()
        return web.json_response({
            "jsonrpc": "2.0",
            "error": {
                "code": -32700,
                "message": f"Parse error: {str(e)}"
            }
        }, status=400)

async def handle_health(request):
    """ヘルスチェック"""
    return web.json_response({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

async def handle_mcp_endpoint(request):
    """統一されたMCPエンドポイント（GET/POST/DELETE対応）"""
    method = request.method
    
    if method == 'GET':
        # GETリクエスト - SSEストリームを開始
        accept_header = request.headers.get('Accept', '')
        if 'text/event-stream' not in accept_header:
            return web.Response(status=405, text="Method Not Allowed")
        
        return await handle_sse_stream(request)
    
    elif method == 'POST':
        # POSTリクエスト - JSON-RPCメッセージを処理
        accept_header = request.headers.get('Accept', '')
        
        try:
            data = await request.json()
            
            # 初期化リクエストかどうかチェック
            if data.get('method') == 'initialize':
                response_data = await handle_initialize(data)
                
                # SSEストリームが要求されているかチェック
                if 'text/event-stream' in accept_header:
                    return await handle_sse_with_initial_response(request, response_data)
                else:
                    return web.json_response(response_data)
            
            # 通常のJSON-RPCリクエスト
            response_data = await handle_jsonrpc_message(data)
            
            # SSEストリームが要求されているかチェック
            if 'text/event-stream' in accept_header:
                return await handle_sse_with_initial_response(request, response_data)
            else:
                return web.json_response(response_data)
                
        except Exception as e:
            print(f"[{datetime.now()}] MCP POST error: {e}")
            traceback.print_exc()
            return web.json_response({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            }, status=400)
    
    elif method == 'DELETE':
        # DELETEリクエスト - セッション終了
        session_id = request.headers.get('Mcp-Session-Id')
        if session_id:
            print(f"[{datetime.now()}] Session terminated: {session_id}")
        return web.Response(status=200)
    
    else:
        return web.Response(status=405, text="Method Not Allowed")

async def handle_initialize(data):
    """初期化リクエストを処理"""
    request_id = data.get('id')
    
    response = {
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
    return response

async def handle_jsonrpc_message(data):
    """JSON-RPCメッセージを処理"""
    method = data.get('method')
    params = data.get('params', {})
    request_id = data.get('id')
    
    print(f"[{datetime.now()}] JSONRPC Request: method={method}, id={request_id}")
    
    # 通知メッセージ（idがない）は無視して200を返す
    if request_id is None:
        print(f"[{datetime.now()}] Notification received (no response needed): {method}")
        return {"status": "ok"}
    
    # tools/list メソッド
    if method == 'tools/list':
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
            print(f"[{datetime.now()}] Tool execution error: {e}")
            traceback.print_exc()
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

async def handle_sse_stream(request):
    """SSEストリームを開始"""
    response = web.StreamResponse()
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['Access-Control-Allow-Origin'] = '*'
    
    await response.prepare(request)
    
    try:
        # 初期化メッセージを送信
        init_data = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        await response.write(f"data: {json.dumps(init_data)}\n\n".encode())
        
        # 接続を維持
        while True:
            await asyncio.sleep(30)  # 30秒ごとにキープアライブ
            keepalive_data = {
                "jsonrpc": "2.0",
                "method": "notifications/ping",
                "params": {"timestamp": datetime.now().isoformat()}
            }
            await response.write(f"data: {json.dumps(keepalive_data)}\n\n".encode())
            
    except asyncio.CancelledError:
        print(f"[{datetime.now()}] SSE connection closed")
    except Exception as e:
        print(f"[{datetime.now()}] SSE error: {e}")
    
    return response

async def handle_sse_with_initial_response(request, initial_response):
    """初期レスポンス付きでSSEストリームを開始"""
    response = web.StreamResponse()
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['Access-Control-Allow-Origin'] = '*'
    
    await response.prepare(request)
    
    try:
        # 初期レスポンスを送信
        await response.write(f"data: {json.dumps(initial_response)}\n\n".encode())
        
        # 接続を維持
        while True:
            await asyncio.sleep(30)  # 30秒ごとにキープアライブ
            keepalive_data = {
                "jsonrpc": "2.0",
                "method": "notifications/ping",
                "params": {"timestamp": datetime.now().isoformat()}
            }
            await response.write(f"data: {json.dumps(keepalive_data)}\n\n".encode())
            
    except asyncio.CancelledError:
        print(f"[{datetime.now()}] SSE connection closed")
    except Exception as e:
        print(f"[{datetime.now()}] SSE error: {e}")
    
    return response

async def handle_root(request):
    """ルートエンドポイント"""
    return web.json_response({
        "service": "e-Stat AWS MCP Server",
        "version": "1.0.0",
        "protocol": "MCP over HTTP (JSONRPC + SSE)",
        "endpoints": ["/health", "/mcp", "/mcp/sse"]
    })

def create_app():
    """Webアプリケーションを作成"""
    app = web.Application()
    
    # ルーティング
    app.router.add_get('/', handle_root)
    app.router.add_get('/health', handle_health)
    app.router.add_get('/mcp', handle_mcp_endpoint)  # MCP GET (SSE)
    app.router.add_post('/mcp', handle_mcp_endpoint)  # MCP POST (JSONRPC)
    app.router.add_delete('/mcp', handle_mcp_endpoint)  # MCP DELETE (session termination)
    
    return app

if __name__ == '__main__':
    # e-Stat AWSサーバーの初期化
    init_estat_server()
    
    # Webサーバーを起動
    app = create_app()
    print(f"[{datetime.now()}] Starting HTTP server on {HOST}:{PORT}")
    print(f"[{datetime.now()}] MCP endpoint: /mcp")
    web.run_app(app, host=HOST, port=PORT)
