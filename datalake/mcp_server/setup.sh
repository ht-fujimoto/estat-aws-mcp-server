#!/bin/bash
#
# データレイク専用MCPサーバーのセットアップスクリプト
#

set -e

echo "=========================================="
echo "E-stat データレイク MCP サーバー セットアップ"
echo "=========================================="
echo

# 1. 依存パッケージのインストール
echo "ステップ1: 依存パッケージのインストール"
echo "------------------------------------------"
pip3 install -q mcp-server-sdk pandas pyarrow boto3 pyyaml
echo "✅ 依存パッケージをインストールしました"
echo

# 2. Kiro設定ファイルの確認
echo "ステップ2: Kiro設定ファイルの確認"
echo "------------------------------------------"

KIRO_CONFIG=".kiro/settings/mcp.json"

if [ ! -f "$KIRO_CONFIG" ]; then
    echo "⚠️  Kiro設定ファイルが見つかりません: $KIRO_CONFIG"
    echo "   新しい設定ファイルを作成します..."
    
    mkdir -p .kiro/settings
    cp datalake/mcp_server/mcp_config.json "$KIRO_CONFIG"
    
    echo "✅ 設定ファイルを作成しました"
else
    echo "✅ Kiro設定ファイルが存在します"
    echo
    echo "📋 次の設定を手動で追加してください:"
    echo
    cat datalake/mcp_server/mcp_config.json
    echo
fi
echo

# 3. AWS認証情報の確認
echo "ステップ3: AWS認証情報の確認"
echo "------------------------------------------"

if aws configure list &> /dev/null; then
    echo "✅ AWS認証情報が設定されています"
    aws configure list
else
    echo "⚠️  AWS認証情報が設定されていません"
    echo "   次のコマンドで設定してください:"
    echo "   aws configure"
fi
echo

# 4. MCPサーバーのテスト
echo "ステップ4: MCPサーバーのテスト"
echo "------------------------------------------"

if python3 -c "from mcp.server import Server" 2>/dev/null; then
    echo "✅ MCPパッケージがインストールされています"
else
    echo "❌ MCPパッケージが見つかりません"
    echo "   pip3 install mcp-server-sdk を実行してください"
    exit 1
fi

if python3 -c "import pandas" 2>/dev/null; then
    echo "✅ pandasがインストールされています"
else
    echo "❌ pandasが見つかりません"
    exit 1
fi

if python3 -c "import pyarrow" 2>/dev/null; then
    echo "✅ pyarrowがインストールされています"
else
    echo "❌ pyarrowが見つかりません"
    exit 1
fi

if python3 -c "import boto3" 2>/dev/null; then
    echo "✅ boto3がインストールされています"
else
    echo "❌ boto3が見つかりません"
    exit 1
fi
echo

# 5. 完了
echo "=========================================="
echo "✅ セットアップが完了しました！"
echo "=========================================="
echo
echo "次のステップ:"
echo "1. Kiroを再起動"
echo "2. コマンドパレット → 'MCP: Reconnect All Servers'"
echo "3. データレイクMCPツールを使用開始"
echo
echo "詳細は datalake/mcp_server/README.md を参照してください"
echo
