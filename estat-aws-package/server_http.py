#!/usr/bin/env python3
"""
HTTP wrapper for MCP Server
クラウドデプロイ用のHTTPサーバー（e-Stat AWS統合版）
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import sys
import traceback
import asyncio
from datetime import datetime

# MCPサーバーのインポート
sys.path.append(os.path.dirname(__file__))
from mcp_servers.estat_aws.server import EStatAWSServer

PORT = int(os.environ.get('PORT', 8080))
ESTAT_APP_ID = os.environ.get('ESTAT_APP_ID', '')

# MCPサーバーの初期化（グローバル）
mcp_server = None

def init_mcp_server():
    """MCPサーバーを初期化"""
    global mcp_server
    try:
        mcp_server = EStatAWSServer()
        print(f"[{datetime.now()}] e-Stat AWS MCP Server initialized successfully")
    except Exception as e:
        print(f"[{datetime.now()}] Error initializing MCP Server: {e}")
        traceback.print_exc()

class EStatMCPServerWrapper:
    """e-Stat MCPサーバーのHTTPラッパー"""
    
    def __init__(self, server: EStatAWSServer):
        self.server = server
        self.tools = self._load_tools()
    
    def _load_tools(self):
        """利用可能なツールのリストを返す"""
        return [
            {
                "name": "search_estat_data",
                "description": "自然言語でe-Statデータを検索し、キーワードサジェスト機能付きで最適なデータセットを提案",
                "parameters": {
                    "query": {"type": "string", "required": True},
                    "max_results": {"type": "integer", "default": 5},
                    "auto_suggest": {"type": "boolean", "default": True},
                    "scoring_method": {"type": "string", "default": "enhanced"}
                }
            },
            {
                "name": "apply_keyword_suggestions",
                "description": "ユーザーが承認したキーワード変換を適用して新しい検索クエリを生成",
                "parameters": {
                    "original_query": {"type": "string", "required": True},
                    "accepted_keywords": {"type": "object", "required": True}
                }
            },
            {
                "name": "fetch_dataset_auto",
                "description": "データセットを自動取得（デフォルトで全データ取得、大規模データは自動分割）",
                "parameters": {
                    "dataset_id": {"type": "string", "required": True},
                    "save_to_s3": {"type": "boolean", "default": True},
                    "convert_to_japanese": {"type": "boolean", "default": True}
                }
            },
            {
                "name": "fetch_large_dataset_complete",
                "description": "大規模データセットの完全取得（分割取得対応、最大100万件）",
                "parameters": {
                    "dataset_id": {"type": "string", "required": True},
                    "max_records": {"type": "integer", "default": 1000000},
                    "chunk_size": {"type": "integer", "default": 100000},
                    "save_to_s3": {"type": "boolean", "default": True},
                    "convert_to_japanese": {"type": "boolean", "default": True}
                }
            },
            {
                "name": "fetch_dataset_filtered",
                "description": "10万件以上のデータセットをカテゴリ指定で絞り込み取得",
                "parameters": {
                    "dataset_id": {"type": "string", "required": True},
                    "filters": {"type": "object", "required": True},
                    "save_to_s3": {"type": "boolean", "default": True},
                    "convert_to_japanese": {"type": "boolean", "default": True}
                }
            },
            {
                "name": "transform_to_parquet",
                "description": "JSONデータをParquet形式に変換してS3に保存",
                "parameters": {
                    "s3_json_path": {"type": "string", "required": True},
                    "data_type": {"type": "string", "required": True},
                    "output_prefix": {"type": "string", "required": False}
                }
            },
            {
                "name": "load_to_iceberg",
                "description": "ParquetデータをIcebergテーブルに投入",
                "parameters": {
                    "table_name": {"type": "string", "required": True},
                    "s3_parquet_path": {"type": "string", "required": True},
                    "create_if_not_exists": {"type": "boolean", "default": True}
                }
            },
            {
                "name": "analyze_with_athena",
                "description": "Athenaで統計分析を実行",
                "parameters": {
                    "table_name": {"type": "string", "required": True},
                    "analysis_type": {"type": "string", "default": "basic"},
                    "custom_query": {"type": "string", "required": False}
                }
            },
            {
                "name": "save_dataset_as_csv",
                "description": "取得したデータセットをCSV形式でS3に保存",
                "parameters": {
                    "dataset_id": {"type": "string", "required": True},
                    "s3_json_path": {"type": "string", "required": False},
                    "local_json_path": {"type": "string", "required": False},
                    "output_filename": {"type": "string", "required": False}
                }
            },
            {
                "name": "download_csv_from_s3",
                "description": "S3に保存されたCSVファイルをローカルにダウンロード",
                "parameters": {
                    "s3_path": {"type": "string", "required": True},
                    "local_path": {"type": "string", "required": False}
                }
            }
        ]
    
    def get_tools(self):
        """ツール一覧を返す"""
        return self.tools
    
    def execute_tool(self, tool_name, arguments):
        """ツールを実行（非同期をラップ）"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if tool_name == 'search_estat_data':
                result = loop.run_until_complete(
                    self.server.search_estat_data(
                        query=arguments.get('query', ''),
                        max_results=arguments.get('max_results', 5),
                        auto_suggest=arguments.get('auto_suggest', True),
                        scoring_method=arguments.get('scoring_method', 'enhanced')
                    )
                )
            elif tool_name == 'apply_keyword_suggestions':
                result = self.server.apply_keyword_suggestions_tool(
                    original_query=arguments.get('original_query', ''),
                    accepted_keywords=arguments.get('accepted_keywords', {})
                )
            elif tool_name == 'fetch_dataset_auto':
                result = loop.run_until_complete(
                    self.server.fetch_dataset_auto(
                        dataset_id=arguments.get('dataset_id', ''),
                        save_to_s3=arguments.get('save_to_s3', True),
                        convert_to_japanese=arguments.get('convert_to_japanese', True)
                    )
                )
            elif tool_name == 'fetch_large_dataset_complete':
                result = loop.run_until_complete(
                    self.server.fetch_large_dataset_complete(
                        dataset_id=arguments.get('dataset_id', ''),
                        max_records=arguments.get('max_records', 1000000),
                        chunk_size=arguments.get('chunk_size', 100000),
                        save_to_s3=arguments.get('save_to_s3', True),
                        convert_to_japanese=arguments.get('convert_to_japanese', True)
                    )
                )
            elif tool_name == 'fetch_dataset_filtered':
                result = loop.run_until_complete(
                    self.server.fetch_dataset_filtered(
                        dataset_id=arguments.get('dataset_id', ''),
                        filters=arguments.get('filters', {}),
                        save_to_s3=arguments.get('save_to_s3', True),
                        convert_to_japanese=arguments.get('convert_to_japanese', True)
                    )
                )
            elif tool_name == 'transform_to_parquet':
                result = loop.run_until_complete(
                    self.server.transform_to_parquet(
                        s3_json_path=arguments.get('s3_json_path', ''),
                        data_type=arguments.get('data_type', ''),
                        output_prefix=arguments.get('output_prefix')
                    )
                )
            elif tool_name == 'load_to_iceberg':
                result = loop.run_until_complete(
                    self.server.load_to_iceberg(
                        table_name=arguments.get('table_name', ''),
                        s3_parquet_path=arguments.get('s3_parquet_path', ''),
                        create_if_not_exists=arguments.get('create_if_not_exists', True)
                    )
                )
            elif tool_name == 'analyze_with_athena':
                result = loop.run_until_complete(
                    self.server.analyze_with_athena(
                        table_name=arguments.get('table_name', ''),
                        analysis_type=arguments.get('analysis_type', 'basic'),
                        custom_query=arguments.get('custom_query')
                    )
                )
            elif tool_name == 'save_dataset_as_csv':
                result = loop.run_until_complete(
                    self.server.save_dataset_as_csv(
                        dataset_id=arguments.get('dataset_id', ''),
                        s3_json_path=arguments.get('s3_json_path'),
                        local_json_path=arguments.get('local_json_path'),
                        output_filename=arguments.get('output_filename')
                    )
                )
            elif tool_name == 'download_csv_from_s3':
                result = loop.run_until_complete(
                    self.server.download_csv_from_s3(
                        s3_path=arguments.get('s3_path', ''),
                        local_path=arguments.get('local_path')
                    )
                )
            else:
                result = {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}"
                }
            return result
        finally:
            loop.close()

class MCPHandler(BaseHTTPRequestHandler):
    """HTTPリクエストハンドラー"""
    
    def log_message(self, format, *args):
        """ログメッセージをカスタマイズ"""
        print(f"[{datetime.now()}] {self.address_string()} - {format % args}")
    
    def do_GET(self):
        """GETリクエストの処理"""
        if self.path == '/health':
            self._send_response(200, {'status': 'healthy', 'timestamp': datetime.now().isoformat()})
        elif self.path == '/tools':
            try:
                tools = mcp_server.get_tools()
                self._send_response(200, {'success': True, 'tools': tools})
            except Exception as e:
                self._send_error(500, str(e))
        else:
            self._send_response(200, {
                'service': 'e-Stat AWS MCP Server',
                'version': '1.0.0',
                'endpoints': ['/health', '/tools', '/execute']
            })
    
    def do_POST(self):
        """POSTリクエストの処理"""
        content_length = int(self.headers.get('Content-Length', 0))
        
        try:
            post_data = self.rfile.read(content_length)
            request = json.loads(post_data.decode('utf-8'))
            
            if self.path == '/tools':
                tools = mcp_server.get_tools()
                self._send_response(200, {'success': True, 'tools': tools})
            
            elif self.path == '/execute':
                tool_name = request.get('tool_name')
                arguments = request.get('arguments', {})
                
                if not tool_name:
                    self._send_error(400, 'tool_name is required')
                    return
                
                result = mcp_server.execute_tool(tool_name, arguments)
                self._send_response(200, {'success': True, 'result': result})
            
            else:
                self._send_error(404, 'Invalid path')
        
        except json.JSONDecodeError:
            self._send_error(400, 'Invalid JSON')
        except Exception as e:
            self._send_error(500, str(e))
    
    def do_OPTIONS(self):
        """OPTIONSリクエストの処理（CORS対応）"""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()
    
    def _set_cors_headers(self):
        """CORSヘッダーを設定"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key')
        self.send_header('Access-Control-Max-Age', '3600')
    
    def _send_response(self, status_code, data):
        """JSONレスポンスを送信"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def _send_error(self, status_code, message):
        """エラーレスポンスを送信"""
        self._send_response(status_code, {
            'success': False,
            'error': message,
            'timestamp': datetime.now().isoformat()
        })

def run_server():
    """サーバーを起動"""
    # MCPサーバーの初期化
    init_mcp_server()
    
    # ラッパーの作成
    global mcp_server
    mcp_server = EStatMCPServerWrapper(mcp_server)
    
    # HTTPサーバーの起動
    server_address = ('0.0.0.0', PORT)
    httpd = HTTPServer(server_address, MCPHandler)
    
    print(f"[{datetime.now()}] Starting e-Stat AWS MCP HTTP Server on port {PORT}...")
    print(f"[{datetime.now()}] Server ready to accept connections")
    print(f"[{datetime.now()}] Health check: http://localhost:{PORT}/health")
    print(f"[{datetime.now()}] Tools endpoint: http://localhost:{PORT}/tools")
    print(f"[{datetime.now()}] Execute endpoint: http://localhost:{PORT}/execute")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n[{datetime.now()}] Server stopped by user")
    except Exception as e:
        print(f"[{datetime.now()}] Server error: {e}")
        traceback.print_exc()
    finally:
        httpd.server_close()
        print(f"[{datetime.now()}] Server closed")

if __name__ == '__main__':
    run_server()
