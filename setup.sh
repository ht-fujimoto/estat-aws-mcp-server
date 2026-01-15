#!/bin/bash
# estat-enhanced MCP セットアップスクリプト

echo "🚀 estat-enhanced MCP セットアップを開始します..."

# Python依存関係のインストール
echo "📦 Python依存関係をインストール中..."
pip install -r requirements.txt

# AWS設定の確認
echo "🔧 AWS設定を確認中..."
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "⚠️  AWS認証が設定されていません。以下のコマンドで設定してください："
    echo "   aws configure"
    exit 1
fi

# 環境変数の設定
echo "🌍 環境変数を設定中..."
export AWS_REGION=ap-northeast-1
export S3_BUCKET=estat-data-lake
export ESTAT_APP_ID=320dd2fbff6974743e3f95505c9f346650ab635e

# MCPサーバーのテスト
echo "🧪 MCPサーバーをテスト中..."
timeout 5 python3 mcp_servers/estat_enhanced_analysis.py < /dev/null > /dev/null 2>&1
if [ $? -eq 124 ]; then
    echo "✅ MCPサーバーが正常に起動しました"
else
    echo "❌ MCPサーバーの起動に問題があります"
fi

echo "✅ セットアップ完了！"
echo ""
echo "次の手順："
echo "1. Kiroを起動"
echo "2. .kiro/settings/mcp.json をKiroの設定ディレクトリにコピー"
echo "3. Kiroを再起動"
echo "4. 'estat-enhanced MCPを使用してテストしてください' でテスト"
