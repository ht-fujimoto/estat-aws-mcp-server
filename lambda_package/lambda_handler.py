#!/usr/bin/env python3
"""
AWS Lambda Handler for e-Stat MCP Server (Full Implementation)
"""

import json
import os
import boto3
import requests
from datetime import datetime
from urllib.parse import urlencode

# グローバル変数（コールドスタート対策）
ssm_client = None
estat_app_id = None

def get_ssm_client():
    """SSMクライアントを取得（遅延初期化）"""
    global ssm_client
    if ssm_client is None:
        region = os.environ.get('ESTAT_REGION', 'ap-northeast-1')
        ssm_client = boto3.client('ssm', region_name=region)
    return ssm_client

def get_estat_app_id():
    """e-Stat APIキーを取得"""
    global estat_app_id
    if estat_app_id is None:
        try:
            client = get_ssm_client()
            response = client.get_parameter(Name='/estat-mcp/api-key', WithDecryption=True)
            estat_app_id = response['Parameter']['Value']
        except Exception as e:
            print(f"[{datetime.now()}] Error getting API key from Parameter Store: {e}")
            estat_app_id = os.environ.get('ESTAT_APP_ID', '')
    return estat_app_id

def search_estat_data(query, max_results=5):
    """e-Statデータセットを検索"""
    try:
        app_id = get_estat_app_id()
        if not app_id:
            return {"error": "ESTAT_APP_ID not configured"}
        
        print(f"[{datetime.now()}] Searching e-Stat with query: {query}")
        
        # e-Stat API呼び出し（タイムアウトを短く）
        base_url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsList"
        params = {
            "appId": app_id,
            "searchWord": query,
            "limit": max_results
        }
        
        print(f"[{datetime.now()}] Calling e-Stat API...")
        response = requests.get(base_url, params=params, timeout=15)
        print(f"[{datetime.now()}] e-Stat API responded with status: {response.status_code}")
        
        data = response.json()
        
        if data.get("GET_STATS_LIST"):
            result = data["GET_STATS_LIST"].get("DATALIST_INF", {})
            table_inf = result.get("TABLE_INF", [])
            
            if isinstance(table_inf, dict):
                table_inf = [table_inf]
            
            datasets = []
            for table in table_inf[:max_results]:
                datasets.append({
                    "id": table.get("@id"),
                    "title": table.get("TITLE"),
                    "gov_org": table.get("GOV_ORG", {}).get("$") if isinstance(table.get("GOV_ORG"), dict) else table.get("GOV_ORG"),
                    "survey_date": table.get("SURVEY_DATE")
                })
            
            print(f"[{datetime.now()}] Found {len(datasets)} datasets")
            return {
                "success": True,
                "query": query,
                "count": len(datasets),
                "datasets": datasets
            }
        else:
            error_msg = data.get("GET_STATS_LIST", {}).get("ERROR_MSG", "Unknown error")
            print(f"[{datetime.now()}] e-Stat API error: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    except requests.exceptions.Timeout:
        print(f"[{datetime.now()}] e-Stat API timeout")
        return {
            "success": False,
            "error": "e-Stat API request timed out. Please try again."
        }
    except Exception as e:
        print(f"[{datetime.now()}] Error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def fetch_dataset_auto(dataset_id):
    """データセットを自動取得"""
    try:
        app_id = get_estat_app_id()
        if not app_id:
            return {"error": "ESTAT_APP_ID not configured"}
        
        # データセット情報を取得
        base_url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
        params = {
            "appId": app_id,
            "statsDataId": dataset_id,
            "limit": 10
        }
        
        response = requests.get(base_url, params=params, timeout=30)
        data = response.json()
        
        if data.get("GET_STATS_DATA"):
            result = data["GET_STATS_DATA"].get("STATISTICAL_DATA", {})
            data_inf = result.get("DATA_INF", {})
            
            return {
                "success": True,
                "dataset_id": dataset_id,
                "title": result.get("TABLE_INF", {}).get("TITLE"),
                "data": data_inf
            }
        else:
            return {
                "success": False,
                "error": data.get("GET_STATS_DATA", {}).get("ERROR_MSG", "Unknown error")
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def lambda_handler(event, context):
    """
    Lambda関数のエントリーポイント
    """
    request_id = context.aws_request_id if context else 'local'
    print(f"[{datetime.now()}] Request {request_id}: {event.get('httpMethod')} {event.get('path')}")
    
    try:
        # HTTPメソッドとパスを取得
        http_method = event.get('httpMethod', 'POST')
        path = event.get('path', '/')
        
        # リクエストボディを取得
        body = event.get('body', '{}')
        if isinstance(body, str):
            try:
                body = json.loads(body) if body else {}
            except json.JSONDecodeError:
                return create_response(400, {'error': 'Invalid JSON in request body'})
        
        # ルーティング
        if path == '/health' or path == '/' or path == '/prod' or path == '/prod/':
            response_body = {
                'status': 'healthy',
                'service': 'e-Stat MCP Server',
                'version': '1.0.0',
                'timestamp': datetime.now().isoformat(),
                'request_id': request_id
            }
            print(f"[{datetime.now()}] Health check OK")
        
        elif path == '/tools' or path == '/prod/tools':
            tools = [
                {
                    "name": "search_estat_data",
                    "description": "e-Statデータセット検索"
                },
                {
                    "name": "fetch_dataset_auto",
                    "description": "データセット自動取得"
                }
            ]
            response_body = {
                'success': True,
                'tools': tools,
                'count': len(tools)
            }
            print(f"[{datetime.now()}] Tools list returned: {len(tools)} tools")
        
        elif path == '/execute' or path == '/prod/execute':
            tool_name = body.get('tool_name')
            arguments = body.get('arguments', {})
            
            if not tool_name:
                return create_response(400, {'error': 'tool_name is required'})
            
            print(f"[{datetime.now()}] Executing tool: {tool_name} with args: {arguments}")
            
            # ツールの実行
            if tool_name == 'search_estat_data':
                query = arguments.get('query', '')
                max_results = arguments.get('max_results', 5)
                result = search_estat_data(query, max_results)
            elif tool_name == 'fetch_dataset_auto':
                dataset_id = arguments.get('dataset_id', '')
                result = fetch_dataset_auto(dataset_id)
            else:
                result = {
                    'success': False,
                    'error': f'Unknown tool: {tool_name}'
                }
            
            response_body = {
                'success': True,
                'result': result,
                'tool_name': tool_name
            }
            print(f"[{datetime.now()}] Tool execution completed")
        
        else:
            print(f"[{datetime.now()}] Path not found: {path}")
            return create_response(404, {
                'error': 'Not found',
                'path': path,
                'available_paths': ['/health', '/tools', '/execute']
            })
        
        return create_response(200, response_body)
    
    except Exception as e:
        print(f"[{datetime.now()}] Error processing request: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return create_response(500, {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
            'request_id': request_id
        })

def create_response(status_code, body):
    """
    API Gateway用のレスポンスを作成
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-API-Key',
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY'
        },
        'body': json.dumps(body, ensure_ascii=False, indent=2)
    }

# ローカルテスト用
if __name__ == '__main__':
    # テストイベント
    test_event = {
        'httpMethod': 'POST',
        'path': '/execute',
        'headers': {},
        'body': json.dumps({
            'tool_name': 'search_estat_data',
            'arguments': {
                'query': '東京都 人口',
                'max_results': 3
            }
        })
    }
    
    class MockContext:
        aws_request_id = 'test-request-id'
    
    response = lambda_handler(test_event, MockContext())
    print(json.dumps(json.loads(response['body']), indent=2, ensure_ascii=False))
