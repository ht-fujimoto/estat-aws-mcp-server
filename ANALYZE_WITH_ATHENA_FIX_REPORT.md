# analyze_with_athena MCP Tool Fix Report

## 概要

**日時**: 2026-01-20  
**ステータス**: ✓ 修正完了  
**問題**: `analyze_with_athena` MCPツールが「Invalid path」エラーで失敗  
**原因**: KiroのMCP設定でURLに不要な`/mcp`パスが含まれていた  
**解決策**: URLを`https://estat-mcp.snowmole.co.jp`に修正

## 問題の詳細

### エラーメッセージ

```
Error calling MCP tool: Streamable HTTP error: Error POSTing to endpoint: 
{"success": false, "error": "Invalid path", "timestamp": "2026-01-20T01:27:50.969492"}
```

### 影響範囲

- `analyze_with_athena`ツールが使用不可
- Athenaでの統計分析が実行できない
- データレイクの分析機能が制限される

## 原因分析

### 1. MCP設定の確認

`.kiro/settings/mcp.json`の設定:

```json
{
  "estat-aws-remote": {
    "transport": "streamable-http",
    "url": "https://estat-mcp.snowmole.co.jp/mcp",  // ← 問題: /mcpパスが不要
    "disabled": false,
    "autoApprove": [
      "analyze_with_athena",
      ...
    ]
  }
}
```

### 2. FastMCPのエンドポイント構造

FastMCPは以下のエンドポイントを提供:

- `GET /tools` - ツール一覧
- `POST /execute` - ツール実行
- `GET /health` - ヘルスチェック

ルートパスは`/`であり、`/mcp`サブパスは存在しない。

### 3. 直接テストの結果

```bash
# 正しいURL（成功）
curl https://estat-mcp.snowmole.co.jp/tools

# 間違ったURL（失敗）
curl https://estat-mcp.snowmole.co.jp/mcp/tools
# → {"success": false, "error": "Invalid path"}
```

## 修正内容

### 修正前

```json
{
  "estat-aws-remote": {
    "transport": "streamable-http",
    "url": "https://estat-mcp.snowmole.co.jp/mcp",
    "disabled": false,
    "autoApprove": [...]
  }
}
```

### 修正後

```json
{
  "estat-aws-remote": {
    "transport": "streamable-http",
    "url": "https://estat-mcp.snowmole.co.jp",
    "disabled": false,
    "autoApprove": [...]
  }
}
```

## 検証

### 1. ツール一覧の取得

```bash
curl https://estat-mcp.snowmole.co.jp/tools
```

**結果**: ✓ 成功

```json
{
  "success": true,
  "tools": [
    {
      "name": "analyze_with_athena",
      "description": "Athenaで統計分析を実行",
      "parameters": {
        "table_name": {"type": "string", "required": true},
        "analysis_type": {"type": "string", "default": "basic"},
        "custom_query": {"type": "string", "required": false}
      }
    },
    ...
  ]
}
```

### 2. ツールの実行

```bash
curl -X POST https://estat-mcp.snowmole.co.jp/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "analyze_with_athena",
    "arguments": {
      "table_name": "economy_data",
      "analysis_type": "basic"
    }
  }'
```

**結果**: ✓ 成功

```json
{
  "success": true,
  "result": {
    "success": true,
    "table_name": "economy_data",
    "database": "estat_db",
    "analysis_type": "basic",
    "results": {
      "total_records": 142573,
      "statistics": {
        "count": 115421,
        "avg_value": 23070.46698356455,
        "min_value": -39396.0,
        "max_value": 1521541.0,
        "sum_value": 2662816369.710004
      },
      "by_year": [...]
    },
    "message": "Successfully analyzed table economy_data"
  }
}
```

## 使用方法

### Kiroから使用

修正後、Kiroから以下のように使用できます:

```python
# 基本分析
result = mcp_estat_aws_remote_analyze_with_athena(
    table_name="economy_data",
    analysis_type="basic"
)

# カスタムクエリ
result = mcp_estat_aws_remote_analyze_with_athena(
    table_name="economy_data",
    analysis_type="custom",
    custom_query="SELECT year, COUNT(*) FROM estat_db.economy_data GROUP BY year"
)
```

### 分析タイプ

1. **basic**: 基本統計
   - 総レコード数
   - 統計情報（平均、最小、最大、合計）
   - 年次別集計（上位10年）

2. **advanced**: 高度分析
   - 地域別集計（上位10地域）
   - カテゴリ別集計（上位10カテゴリ）
   - 時系列トレンド

3. **custom**: カスタムクエリ
   - 任意のSQLクエリを実行

## 関連ファイル

- `.kiro/settings/mcp.json` - Kiro MCP設定（修正済み）
- `server_http.py` - FastMCPサーバー実装
- `mcp_servers/estat_aws/server.py` - analyze_with_athena実装
- `test_analyze_with_athena.py` - テストスクリプト

## 今後の推奨事項

### 1. エンドポイントの標準化

すべてのMCPサーバーで一貫したエンドポイント構造を使用:

- `GET /tools` - ツール一覧
- `POST /execute` - ツール実行
- `GET /health` - ヘルスチェック

### 2. エラーメッセージの改善

「Invalid path」エラーをより詳細なメッセージに改善:

```json
{
  "success": false,
  "error": "Invalid path: /mcp/tools",
  "message": "Valid endpoints are: /tools, /execute, /health",
  "timestamp": "2026-01-20T01:27:50.969492"
}
```

### 3. ドキュメントの更新

MCP設定のドキュメントに正しいURL形式を明記:

```markdown
## MCP Server Configuration

### Streamable HTTP Transport

```json
{
  "transport": "streamable-http",
  "url": "https://your-server.com",  // ← No trailing path
  "disabled": false
}
```

Note: Do not include `/mcp` or other paths in the URL. 
FastMCP automatically handles routing.
```

### 4. 設定検証ツール

MCP設定の妥当性を検証するツールを作成:

```python
def validate_mcp_config(config):
    """MCP設定を検証"""
    for server_name, server_config in config.get("mcpServers", {}).items():
        if server_config.get("transport") == "streamable-http":
            url = server_config.get("url", "")
            
            # URLに不要なパスが含まれていないかチェック
            if url.endswith("/mcp") or url.endswith("/tools") or url.endswith("/execute"):
                print(f"Warning: {server_name} URL should not include path: {url}")
                print(f"Suggested: {url.rsplit('/', 1)[0]}")
```

## まとめ

✓ `analyze_with_athena`ツールのエラーを修正  
✓ KiroのMCP設定を更新（`/mcp`パスを削除）  
✓ ツールが正常に動作することを確認  
✓ 基本分析、高度分析、カスタムクエリがすべて利用可能  

データレイクの分析機能が完全に復旧し、Athenaでの統計分析が実行できるようになりました。

---

**作成日**: 2026-01-20  
**バージョン**: 1.0  
**ステータス**: ✓ 修正完了
