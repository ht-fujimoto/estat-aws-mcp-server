#!/usr/bin/env python3
"""
MCP Wrapper for AWS Lambda Backend
KiroのMCPプロトコルとAWS Lambda APIの間のブリッジ
"""

import sys
import json
import requests
from typing import Any, Dict

# AWS ECS Fargate API URL (ALB)
API_URL = "http://estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com"

def send_response(response: Dict[str, Any]) -> None:
    """MCPレスポンスを送信"""
    print(json.dumps(response), flush=True)

def handle_initialize(params: Dict[str, Any]) -> Dict[str, Any]:
    """初期化リクエストを処理"""
    return {
        "jsonrpc": "2.0",
        "id": params.get("id"),
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

def handle_tools_list(params: Dict[str, Any]) -> Dict[str, Any]:
    """ツール一覧リクエストを処理"""
    try:
        response = requests.get(f"{API_URL}/tools", timeout=10)
        data = response.json()
        
        tools = []
        if data.get("success") and "tools" in data:
            for tool in data["tools"]:
                # パラメータをMCP inputSchemaに変換
                properties = {}
                required = []
                
                for param_name, param_info in tool.get("parameters", {}).items():
                    param_type = param_info.get("type", "string")
                    properties[param_name] = {"type": param_type}
                    
                    # デフォルト値があれば追加
                    if "default" in param_info:
                        properties[param_name]["default"] = param_info["default"]
                    
                    # 必須パラメータをチェック
                    if param_info.get("required", False):
                        required.append(param_name)
                
                input_schema = {
                    "type": "object",
                    "properties": properties
                }
                
                if required:
                    input_schema["required"] = required
                
                tools.append({
                    "name": tool["name"],
                    "description": tool["description"],
                    "inputSchema": input_schema
                })
        
        return {
            "jsonrpc": "2.0",
            "id": params.get("id"),
            "result": {
                "tools": tools
            }
        }
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": params.get("id"),
            "error": {
                "code": -32603,
                "message": f"Failed to fetch tools: {str(e)}"
            }
        }

def handle_tools_call(params: Dict[str, Any]) -> Dict[str, Any]:
    """ツール実行リクエストを処理"""
    try:
        tool_params = params.get("params", {})
        tool_name = tool_params.get("name")
        arguments = tool_params.get("arguments", {})
        
        # AWS Lambda APIを呼び出し
        response = requests.post(
            f"{API_URL}/execute",
            json={
                "tool_name": tool_name,
                "arguments": arguments
            },
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        data = response.json()
        
        if data.get("success"):
            result = data.get("result", {})
            return {
                "jsonrpc": "2.0",
                "id": params.get("id"),
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, indent=2)
                        }
                    ]
                }
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": params.get("id"),
                "error": {
                    "code": -32603,
                    "message": data.get("error", "Unknown error")
                }
            }
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": params.get("id"),
            "error": {
                "code": -32603,
                "message": f"Tool execution failed: {str(e)}"
            }
        }

def main():
    """メインループ"""
    # 標準入力からMCPリクエストを読み取る
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            method = request.get("method")
            
            if method == "initialize":
                response = handle_initialize(request)
            elif method == "tools/list":
                response = handle_tools_list(request)
            elif method == "tools/call":
                response = handle_tools_call(request)
            elif method == "notifications/initialized":
                # 初期化完了通知は無視
                continue
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
            
            send_response(response)
            
        except json.JSONDecodeError:
            continue
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            }
            send_response(error_response)

if __name__ == "__main__":
    main()
