#!/bin/bash

# estat-aws セットアップテストスクリプト
# 他の環境でestat-awsが正しく動作するかテストします

set -e

echo "=========================================="
echo "estat-aws セットアップテスト"
echo "=========================================="
echo ""

# 色の定義
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# テスト結果カウンター
PASSED=0
FAILED=0

# テスト関数
test_step() {
    local step_name=$1
    local command=$2
    
    echo -n "テスト: ${step_name}... "
    
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 成功${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ 失敗${NC}"
        ((FAILED++))
        return 1
    fi
}

# 詳細テスト関数（出力を表示）
test_step_verbose() {
    local step_name=$1
    local command=$2
    
    echo "テスト: ${step_name}"
    
    if eval "$command"; then
        echo -e "${GREEN}✓ 成功${NC}"
        echo ""
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ 失敗${NC}"
        echo ""
        ((FAILED++))
        return 1
    fi
}

echo "1. 前提条件の確認"
echo "----------------------------------------"

# Python 3.11以上のチェック
test_step "Python 3.11以上" "python3 --version | grep -E 'Python 3\.(1[1-9]|[2-9][0-9])'"

# 必要なファイルの存在確認
test_step "mcp_aws_wrapper.py の存在" "test -f mcp_aws_wrapper.py"

# Kiro設定ファイルの確認
if test -f .kiro/settings/mcp.json; then
    echo -n "テスト: .kiro/settings/mcp.json の存在... "
    echo -e "${GREEN}✓ 成功${NC}"
    ((PASSED++))
else
    echo -n "テスト: .kiro/settings/mcp.json の存在... "
    echo -e "${YELLOW}⚠ 警告: ファイルが見つかりません${NC}"
    echo "  → .kiro/settings/mcp.json を作成してください"
fi

echo ""
echo "2. ECS Fargateサービスの確認"
echo "----------------------------------------"

# ヘルスチェック
test_step_verbose "サービスヘルスチェック" \
    "curl -s http://estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com/health | grep -q 'healthy'"

# ツール一覧の取得
echo "テスト: ツール一覧の取得"
TOOLS_COUNT=$(curl -s http://estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com/tools | python3 -c "import sys, json; data = json.load(sys.stdin); print(len(data.get('tools', [])))" 2>/dev/null || echo "0")

if [ "$TOOLS_COUNT" -eq 10 ]; then
    echo -e "${GREEN}✓ 成功: 10個のツールが利用可能${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ 失敗: ${TOOLS_COUNT}個のツールのみ検出（期待: 10個）${NC}"
    ((FAILED++))
fi
echo ""

echo "3. MCPラッパーのテスト"
echo "----------------------------------------"

# MCPプロトコルテスト - initialize
test_step_verbose "MCPプロトコル: initialize" \
    "echo '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"test\",\"version\":\"1.0.0\"}}}' | python3 mcp_aws_wrapper.py | grep -q 'estat-aws'"

# MCPプロトコルテスト - tools/list
echo "テスト: MCPプロトコル: tools/list"
MCP_TOOLS_COUNT=$(echo '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | python3 mcp_aws_wrapper.py 2>/dev/null | python3 -c "import sys, json; data = json.load(sys.stdin); print(len(data.get('result', {}).get('tools', [])))" 2>/dev/null || echo "0")

if [ "$MCP_TOOLS_COUNT" -eq 10 ]; then
    echo -e "${GREEN}✓ 成功: MCPプロトコル経由で10個のツールが利用可能${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ 失敗: ${MCP_TOOLS_COUNT}個のツールのみ検出（期待: 10個）${NC}"
    ((FAILED++))
fi
echo ""

echo "4. 実際のツール実行テスト"
echo "----------------------------------------"

# search_estat_dataのテスト
echo "テスト: search_estat_data（人口統計検索）"
SEARCH_RESULT=$(echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_estat_data","arguments":{"query":"人口統計","max_results":2}}}' | python3 mcp_aws_wrapper.py 2>/dev/null | python3 -c "import sys, json; data = json.load(sys.stdin); result = json.loads(data['result']['content'][0]['text']); print('success' if result.get('success') else 'failed')" 2>/dev/null || echo "error")

if [ "$SEARCH_RESULT" = "success" ]; then
    echo -e "${GREEN}✓ 成功: データ検索が正常に動作${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ 失敗: データ検索でエラーが発生${NC}"
    ((FAILED++))
fi
echo ""

echo "=========================================="
echo "テスト結果サマリー"
echo "=========================================="
echo ""
echo -e "成功: ${GREEN}${PASSED}${NC} 件"
echo -e "失敗: ${RED}${FAILED}${NC} 件"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ 全てのテストに合格しました！${NC}"
    echo ""
    echo "estat-awsは正常に動作しています。"
    echo "Kiro IDEで使用する準備が整いました。"
    echo ""
    echo "次のステップ:"
    echo "1. Kiro IDEを開く"
    echo "2. このプロジェクトを開く"
    echo "3. Kiro IDEを再起動（設定を読み込むため）"
    echo "4. チャットで試す: '東京都の人口データを検索してください'"
    exit 0
else
    echo -e "${RED}✗ いくつかのテストが失敗しました${NC}"
    echo ""
    echo "トラブルシューティング:"
    echo ""
    
    if [ ! -f mcp_aws_wrapper.py ]; then
        echo "- mcp_aws_wrapper.py が見つかりません"
        echo "  → 元のプロジェクトからコピーしてください"
    fi
    
    if [ ! -f .kiro/settings/mcp.json ]; then
        echo "- .kiro/settings/mcp.json が見つかりません"
        echo "  → ESTAT_AWS_QUICK_START.md を参照して作成してください"
    fi
    
    if [ "$TOOLS_COUNT" -ne 10 ]; then
        echo "- ECS Fargateサービスが正常に動作していません"
        echo "  → サービスの状態を確認してください"
        echo "  → curl http://estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com/health"
    fi
    
    echo ""
    echo "詳細なセットアップ手順は ESTAT_AWS_SETUP_GUIDE.md を参照してください。"
    exit 1
fi
