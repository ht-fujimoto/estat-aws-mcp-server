#!/usr/bin/env python3
"""
Simple MCP Test Server
最小限の機能でKiroとの互換性をテスト
"""

import sys
import json

def main():
    """メインループ"""
    # 標準入力からJSON-RPCメッセージを読み取り
    for line in sys.stdin:
        try:
            line = line.strip()
            if not line:
                continue
            
            # JSON-RPCメッセージをパース
            request = json.loads(line)
            method = request.get("method")
            request_id = request.get("id")
            
            # 通知メッセージ（idがない）は無視
            if request_id is None:
                continue
            
            # initialize メソッド
            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "test-server",
                            "version": "1.0.0"
                        }
                    }
                }
            
            # tools/list メソッド
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": [
                            {
                                "name": "test_tool",
                                "description": "テスト用のシンプルなツール",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "message": {
                                            "type": "string",
                                            "description": "テストメッセージ"
                                        }
                                    },
                                    "required": ["message"]
                                }
                            }
                        ]
                    }
                }
            
            # tools/call メソッド
            elif method == "tools/call":
                params = request.get("params", {})
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                if tool_name == "test_tool":
                    message = arguments.get("message", "Hello from test tool!")
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Test response: {message}"
                                }
                            ]
                        }
                    }
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Tool not found: {tool_name}"
                        }
                    }
            
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
            
            # レスポンスを送信
            print(json.dumps(response, ensure_ascii=False))
            sys.stdout.flush()
            
        except json.JSONDecodeError:
            continue
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": request.get("id") if 'request' in locals() else None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            }
            print(json.dumps(error_response, ensure_ascii=False))
            sys.stdout.flush()

if __name__ == "__main__":
    main()