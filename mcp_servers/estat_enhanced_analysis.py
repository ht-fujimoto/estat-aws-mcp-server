#!/usr/bin/env python3
"""
e-Stat Enhanced Analysis MCP Server
キーワードサジェスト機能と強化されたスコアリングを持つe-Stat分析サーバー

Features:
- 134用語の統計用語辞書によるキーワードサジェスト
- 8項目の強化されたスコアリングアルゴリズム
- ヒューマンインザループ対応
- メタデータ並列取得による高速化
- 統計的有意性を重視したデータセット推奨

Compatible with: Kiro, Cline, and other MCP clients
"""

import warnings
# すべての警告を抑制（Kiroとの互換性のため）
warnings.filterwarnings('ignore')

import asyncio
import json
import os
import sys
from typing import Any, Dict, List

# Local imports
sys.path.append(os.path.dirname(__file__))
from estat_analysis_hitl import EStatHITLServer

# 環境変数
ESTAT_APP_ID = os.environ.get('ESTAT_APP_ID', '320dd2fbff6974743e3f95505c9f346650ab635e')
S3_BUCKET = os.environ.get('S3_BUCKET', 'estat-data-lake')
AWS_REGION = os.environ.get('AWS_REGION', 'ap-northeast-1')

# グローバル変数（遅延初期化）
estat_server = None

def init_estat_server():
    """e-Stat HITLサーバーを初期化（遅延初期化）"""
    global estat_server
    if estat_server is not None:
        return
    
    if not ESTAT_APP_ID:
        raise ValueError("ESTAT_APP_ID not set")
    
    try:
        estat_server = EStatHITLServer()
    except Exception as e:
        raise RuntimeError(f"Failed to initialize EStatHITLServer: {str(e)}")


class MCPServer:
    """シンプルなMCP Enhanced サーバー実装"""
    
    def __init__(self):
        self.request_id = 0
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """利用可能なツールのリストを返す"""
        return [
            {
                "name": "search_estat_data",
                "description": "自然言語でe-Statデータを検索し、キーワードサジェスト機能付きで最適なデータセットを提案",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "検索クエリ（例: 年齢別 収入、東京都 交通事故）"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "返却する最大件数",
                            "default": 5,
                            "minimum": 1,
                            "maximum": 20
                        },
                        "auto_suggest": {
                            "type": "boolean",
                            "description": "キーワードサジェスト機能を有効にするか",
                            "default": True
                        },
                        "scoring_method": {
                            "type": "string",
                            "description": "スコアリング方法",
                            "enum": ["enhanced", "basic"],
                            "default": "enhanced"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "apply_keyword_suggestions",
                "description": "ユーザーが承認したキーワード変換を適用して新しい検索クエリを生成",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "original_query": {
                            "type": "string",
                            "description": "元のクエリ"
                        },
                        "accepted_keywords": {
                            "type": "object",
                            "description": "承認されたキーワード変換（{元のキーワード: 新しいキーワード}の辞書形式）",
                            "additionalProperties": {
                                "type": "string"
                            }
                        }
                    },
                    "required": ["original_query", "accepted_keywords"]
                }
            },
            {
                "name": "fetch_dataset_auto",
                "description": "データセットを自動取得（デフォルトで全データ取得、大規模データは自動分割）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "データセットID"
                        },
                        "save_to_s3": {
                            "type": "boolean",
                            "description": "S3に保存するか",
                            "default": True
                        },
                        "convert_to_japanese": {
                            "type": "boolean",
                            "description": "コード→和名変換を実施するか",
                            "default": True
                        }
                    },
                    "required": ["dataset_id"]
                }
            },
            {
                "name": "fetch_large_dataset_complete",
                "description": "大規模データセットの完全取得（分割取得対応、最大100万件）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "データセットID"
                        },
                        "max_records": {
                            "type": "integer",
                            "description": "取得する最大レコード数",
                            "default": 1000000,
                            "minimum": 1,
                            "maximum": 1000000
                        },
                        "chunk_size": {
                            "type": "integer",
                            "description": "1回あたりの取得件数",
                            "default": 100000,
                            "minimum": 1000,
                            "maximum": 100000
                        },
                        "save_to_s3": {
                            "type": "boolean",
                            "description": "S3に保存するか",
                            "default": True
                        },
                        "convert_to_japanese": {
                            "type": "boolean",
                            "description": "コード→和名変換を実施するか",
                            "default": True
                        }
                    },
                    "required": ["dataset_id"]
                }
            },
            {
                "name": "fetch_dataset_filtered",
                "description": "10万件以上のデータセットをカテゴリ指定で絞り込み取得",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "データセットID"
                        },
                        "filters": {
                            "type": "object",
                            "description": "フィルタ条件（例: {\"area\": \"13000\", \"time\": \"2020\"}）",
                            "additionalProperties": {
                                "type": "string"
                            }
                        },
                        "save_to_s3": {
                            "type": "boolean",
                            "description": "S3に保存するか",
                            "default": True
                        },
                        "convert_to_japanese": {
                            "type": "boolean",
                            "description": "コード→和名変換を実施するか",
                            "default": True
                        }
                    },
                    "required": ["dataset_id", "filters"]
                }
            },
            {
                "name": "transform_to_parquet",
                "description": "JSONデータをParquet形式に変換してS3に保存",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "s3_json_path": {
                            "type": "string",
                            "description": "S3上のJSONファイルパス"
                        },
                        "data_type": {
                            "type": "string",
                            "description": "データ種別"
                        },
                        "output_prefix": {
                            "type": "string",
                            "description": "出力先プレフィックス（オプション）"
                        }
                    },
                    "required": ["s3_json_path", "data_type"]
                }
            },
            {
                "name": "load_to_iceberg",
                "description": "ParquetデータをIcebergテーブルに投入",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "テーブル名"
                        },
                        "s3_parquet_path": {
                            "type": "string",
                            "description": "S3上のParquetファイルパス"
                        },
                        "create_if_not_exists": {
                            "type": "boolean",
                            "description": "テーブルが存在しない場合に作成するか",
                            "default": True
                        }
                    },
                    "required": ["table_name", "s3_parquet_path"]
                }
            },
            {
                "name": "analyze_with_athena",
                "description": "Athenaで統計分析を実行",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "テーブル名"
                        },
                        "analysis_type": {
                            "type": "string",
                            "description": "分析タイプ",
                            "enum": ["basic", "advanced"],
                            "default": "basic"
                        },
                        "custom_query": {
                            "type": "string",
                            "description": "カスタムクエリ（オプション）"
                        }
                    },
                    "required": ["table_name"]
                }
            },
            {
                "name": "save_dataset_as_csv",
                "description": "取得したデータセットをCSV形式でS3に保存",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "データセットID"
                        },
                        "s3_json_path": {
                            "type": "string",
                            "description": "S3上のJSONファイルパス（オプション）"
                        },
                        "local_json_path": {
                            "type": "string",
                            "description": "ローカルのJSONファイルパス（オプション）"
                        },
                        "output_filename": {
                            "type": "string",
                            "description": "出力ファイル名（オプション、デフォルトは dataset_id_YYYYMMDD_HHMMSS.csv）"
                        }
                    },
                    "required": ["dataset_id"]
                }
            },
            {
                "name": "download_csv_from_s3",
                "description": "S3に保存されたCSVファイルをローカルにダウンロード",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "s3_path": {
                            "type": "string",
                            "description": "S3上のCSVファイルパス（s3://bucket/key 形式）"
                        },
                        "local_path": {
                            "type": "string",
                            "description": "ローカル保存先パス（オプション、デフォルトはカレントディレクトリ）"
                        }
                    },
                    "required": ["s3_path"]
                }
            }
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """ツールを呼び出す"""
        try:
            # 遅延初期化
            init_estat_server()
            
            if name == "search_estat_data":
                result = await estat_server.search_and_rank_datasets(
                    query=arguments["query"],
                    max_results=arguments.get("max_results", 5),
                    scoring_method=arguments.get("scoring_method", "enhanced"),
                    auto_suggest=arguments.get("auto_suggest", True)
                )
                
            elif name == "apply_keyword_suggestions":
                new_query = estat_server.apply_keyword_suggestions_and_search(
                    original_query=arguments["original_query"],
                    accepted_keywords=arguments["accepted_keywords"]
                )
                result = {
                    "success": True,
                    "original_query": arguments["original_query"],
                    "transformed_query": new_query,
                    "accepted_keywords": arguments["accepted_keywords"]
                }
                
            elif name == "fetch_dataset_auto":
                result = await estat_server.fetch_dataset_auto(
                    dataset_id=arguments["dataset_id"],
                    save_to_s3=arguments.get("save_to_s3", True),
                    convert_to_japanese=arguments.get("convert_to_japanese", True)
                )
                
            elif name == "fetch_large_dataset_complete":
                result = await estat_server.fetch_large_dataset_complete(
                    dataset_id=arguments["dataset_id"],
                    max_records=arguments.get("max_records", 1000000),
                    chunk_size=arguments.get("chunk_size", 100000),
                    save_to_s3=arguments.get("save_to_s3", True),
                    convert_to_japanese=arguments.get("convert_to_japanese", True)
                )
                
            elif name == "fetch_dataset_filtered":
                result = await estat_server.fetch_dataset_filtered(
                    dataset_id=arguments["dataset_id"],
                    filters=arguments["filters"],
                    save_to_s3=arguments.get("save_to_s3", True),
                    convert_to_japanese=arguments.get("convert_to_japanese", True)
                )
                
            elif name == "transform_to_parquet":
                result = await estat_server.transform_to_parquet(
                    s3_json_path=arguments["s3_json_path"],
                    data_type=arguments["data_type"],
                    output_prefix=arguments.get("output_prefix")
                )
                
            elif name == "load_to_iceberg":
                result = await estat_server.load_to_iceberg(
                    table_name=arguments["table_name"],
                    s3_parquet_path=arguments["s3_parquet_path"],
                    create_if_not_exists=arguments.get("create_if_not_exists", True)
                )
                
            elif name == "analyze_with_athena":
                result = await estat_server.analyze_with_athena(
                    table_name=arguments["table_name"],
                    analysis_type=arguments.get("analysis_type", "basic"),
                    custom_query=arguments.get("custom_query")
                )
                
            elif name == "save_dataset_as_csv":
                result = await estat_server.save_dataset_as_csv(
                    dataset_id=arguments["dataset_id"],
                    s3_json_path=arguments.get("s3_json_path"),
                    local_json_path=arguments.get("local_json_path"),
                    output_filename=arguments.get("output_filename")
                )
                
            elif name == "download_csv_from_s3":
                result = await estat_server.download_csv_from_s3(
                    s3_path=arguments["s3_path"],
                    local_path=arguments.get("local_path")
                )
                
            else:
                result = {"success": False, "error": f"Unknown tool: {name}"}
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e), "tool": name, "arguments": arguments}

    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """メッセージを処理"""
        method = message.get("method")
        
        if method == "initialize":
            return {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "estat-enhanced-analysis",
                    "version": "2.0.0"
                }
            }
        
        elif method == "tools/list":
            return {"tools": self.get_tools()}
        
        elif method == "tools/call":
            params = message.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            result = await self.call_tool(tool_name, arguments)
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }
                ]
            }
        
        return {"error": f"Unknown method: {method}"}
    
    async def run(self):
        """サーバーを実行"""
        # 標準入力からメッセージを読み取る
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            
            try:
                message = json.loads(line)
                response = await self.handle_message(message)
                
                result = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": response
                }
                
                print(json.dumps(result, ensure_ascii=False), flush=True)
            
            except Exception as e:
                error_msg = {
                    "jsonrpc": "2.0",
                    "id": message.get("id") if 'message' in locals() else None,
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    }
                }
                print(json.dumps(error_msg), flush=True)


async def main():
    """メイン関数"""
    mcp_server = MCPServer()
    await mcp_server.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        # エラーは無視（Kiroとの互換性のため）
        pass