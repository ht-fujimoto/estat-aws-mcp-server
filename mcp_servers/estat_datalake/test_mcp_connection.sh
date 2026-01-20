#!/bin/bash

# E-stat Data Lake MCP Server 接続テスト

echo "========================================="
echo "E-stat Data Lake MCP Server 接続テスト"
echo "========================================="
echo ""

# サーバーを起動してinitializeメッセージを送信
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}' | python3 mcp_servers/estat_datalake/server.py

echo ""
echo "========================================="
echo "テスト完了"
echo "========================================="
