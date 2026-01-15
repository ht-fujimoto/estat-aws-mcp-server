#!/usr/bin/env python3
"""
MCP Streamable HTTP Server for e-Stat AWS
MCPのHTTPトランスポート仕様に準拠したサーバー実装
"""

import os
import sys
import asyncio
from datetime import datetime

# FastMCPのインポート
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("Error: fastmcp not installed. Run: pip install mcp")
    sys.exit(1)

# MCPサーバーのインポート
sys.path.append(os.path.dirname(__file__))
from mcp_servers.estat_aws.server import EStatAWSServer

# 環境変数
PORT = int(os.environ.get('PORT', 8080))
HOST = os.environ.get('TRANSPORT_HOST', '0.0.0.0')
TRANSPORT_MODE = os.environ.get('TRANSPORT_MODE', 'streamable-http')
ESTAT_APP_ID = os.environ.get('ESTAT_APP_ID', '')
S3_BUCKET = os.environ.get('S3_BUCKET', 'estat-data-lake')
AWS_REGION = os.environ.get('AWS_REGION', 'ap-northeast-1')

print(f"[{datetime.now()}] Starting e-Stat AWS MCP Server")
print(f"[{datetime.now()}] Transport: {TRANSPORT_MODE}")
print(f"[{datetime.now()}] Host: {HOST}:{PORT}")

# FastMCPインスタンスの作成
mcp = FastMCP("estat-aws")

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

# MCPツールの登録
@mcp.tool()
async def search_estat_data(
    query: str,
    max_results: int = 5,
    auto_suggest: bool = True,
    scoring_method: str = "enhanced"
) -> dict:
    """自然言語でe-Statデータを検索し、キーワードサジェスト機能付きで最適なデータセットを提案"""
    return await estat_server.search_estat_data(query, max_results, auto_suggest, scoring_method)

@mcp.tool()
def apply_keyword_suggestions(
    original_query: str,
    accepted_keywords: dict
) -> dict:
    """ユーザーが承認したキーワード変換を適用して新しい検索クエリを生成"""
    return estat_server.apply_keyword_suggestions_tool(original_query, accepted_keywords)

@mcp.tool()
async def fetch_dataset_auto(
    dataset_id: str,
    save_to_s3: bool = True,
    convert_to_japanese: bool = True
) -> dict:
    """データセットを自動取得（デフォルトで全データ取得、大規模データは自動分割）"""
    return await estat_server.fetch_dataset_auto(dataset_id, save_to_s3, convert_to_japanese)

@mcp.tool()
async def fetch_large_dataset_complete(
    dataset_id: str,
    max_records: int = 1000000,
    chunk_size: int = 100000,
    save_to_s3: bool = True,
    convert_to_japanese: bool = True
) -> dict:
    """大規模データセットの完全取得（分割取得対応、最大100万件）"""
    return await estat_server.fetch_large_dataset_complete(
        dataset_id, max_records, chunk_size, save_to_s3, convert_to_japanese
    )

@mcp.tool()
async def fetch_dataset_filtered(
    dataset_id: str,
    filters: dict,
    save_to_s3: bool = True,
    convert_to_japanese: bool = True
) -> dict:
    """10万件以上のデータセットをカテゴリ指定で絞り込み取得"""
    return await estat_server.fetch_dataset_filtered(dataset_id, filters, save_to_s3, convert_to_japanese)

@mcp.tool()
async def transform_to_parquet(
    s3_json_path: str,
    data_type: str,
    output_prefix: str = None
) -> dict:
    """JSONデータをParquet形式に変換してS3に保存"""
    return await estat_server.transform_to_parquet(s3_json_path, data_type, output_prefix)

@mcp.tool()
async def load_to_iceberg(
    table_name: str,
    s3_parquet_path: str,
    create_if_not_exists: bool = True
) -> dict:
    """ParquetデータをIcebergテーブルに投入"""
    return await estat_server.load_to_iceberg(table_name, s3_parquet_path, create_if_not_exists)

@mcp.tool()
async def analyze_with_athena(
    table_name: str,
    analysis_type: str = "basic",
    custom_query: str = None
) -> dict:
    """Athenaで統計分析を実行"""
    return await estat_server.analyze_with_athena(table_name, analysis_type, custom_query)

@mcp.tool()
async def save_dataset_as_csv(
    dataset_id: str,
    s3_json_path: str = None,
    local_json_path: str = None,
    output_filename: str = None
) -> dict:
    """取得したデータセットをCSV形式でS3に保存"""
    return await estat_server.save_dataset_as_csv(dataset_id, s3_json_path, local_json_path, output_filename)

@mcp.tool()
async def download_csv_from_s3(
    s3_path: str,
    local_path: str = None
) -> dict:
    """S3に保存されたCSVファイルをローカルにダウンロード"""
    return await estat_server.download_csv_from_s3(s3_path, local_path)

if __name__ == '__main__':
    # e-Stat AWSサーバーの初期化
    init_estat_server()
    
    # MCPサーバーを起動（streamable-http）
    print(f"[{datetime.now()}] Starting MCP server with {TRANSPORT_MODE} transport...")
    mcp.run(
        transport=TRANSPORT_MODE,
        host=HOST,
        port=PORT
    )
