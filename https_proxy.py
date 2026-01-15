#!/usr/bin/env python3
"""
HTTPS Proxy for MCP Remote Server
証明書の問題を回避するためのローカルプロキシ（標準ライブラリ使用）
"""

import http.server
import socketserver
import urllib.request
import urllib.parse
import json
import ssl
from urllib.error import URLError

# リモートサーバーのURL
REMOTE_URL = "https://estat-mcp.snowmole.co.jp/mcp"
LOCAL_PORT = 8082

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        """POSTリクエストをプロキシ"""
        try:
            # リクエストボディを読み取り
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            # SSL証明書の検証を無効化
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # リモートサーバーにリクエストを転送
            req = urllib.request.Request(
                REMOTE_URL,
                data=post_data,
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req, context=ssl_context) as response:
                response_data = response.read()
                
                # レスポンスを返す
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(response_data)
        
        except Exception as e:
            print(f"Proxy error: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Proxy error: {str(e)}"
                }
            }
            
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_response).encode())
    
    def do_GET(self):
        """GETリクエストの処理"""
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "proxy_healthy"}).encode())
        elif self.path == '/mcp':
            # MCPサーバー情報を返す
            server_info = {
                "service": "e-Stat AWS MCP Server (via proxy)",
                "version": "1.0.0",
                "protocol": "MCP over HTTP (JSONRPC)",
                "proxy": True
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(server_info).encode())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    print(f"Starting HTTPS proxy on localhost:{LOCAL_PORT}")
    print(f"Proxying to: {REMOTE_URL}")
    
    with socketserver.TCPServer(("localhost", LOCAL_PORT), ProxyHandler) as httpd:
        httpd.serve_forever()