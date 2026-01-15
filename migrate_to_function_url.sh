#!/bin/bash
# Lambda Function URLへの移行スクリプト

set -e

FUNCTION_NAME="estat-mcp-server"
REGION="ap-northeast-1"

echo "=========================================="
echo "Lambda Function URL 設定"
echo "=========================================="

# 1. Lambda関数のタイムアウトを延長（60秒→300秒）
echo ""
echo "1. Lambda関数のタイムアウトを300秒に延長..."
aws lambda update-function-configuration \
  --function-name $FUNCTION_NAME \
  --timeout 300 \
  --region $REGION

echo "✅ タイムアウトを300秒に設定しました"

# 2. Function URLを作成
echo ""
echo "2. Function URLを作成..."
FUNCTION_URL=$(aws lambda create-function-url-config \
  --function-name $FUNCTION_NAME \
  --auth-type NONE \
  --cors '{
    "AllowOrigins": ["*"],
    "AllowMethods": ["GET", "POST", "OPTIONS"],
    "AllowHeaders": ["Content-Type", "Authorization"],
    "MaxAge": 86400
  }' \
  --region $REGION \
  --query 'FunctionUrl' \
  --output text 2>/dev/null || \
  aws lambda get-function-url-config \
    --function-name $FUNCTION_NAME \
    --region $REGION \
    --query 'FunctionUrl' \
    --output text)

echo "✅ Function URL: $FUNCTION_URL"

# 3. パブリックアクセスを許可
echo ""
echo "3. パブリックアクセスを許可..."
aws lambda add-permission \
  --function-name $FUNCTION_NAME \
  --statement-id FunctionURLAllowPublicAccess \
  --action lambda:InvokeFunctionUrl \
  --principal "*" \
  --function-url-auth-type NONE \
  --region $REGION 2>/dev/null || echo "権限は既に設定済み"

echo "✅ パブリックアクセスを許可しました"

# 4. 動作確認
echo ""
echo "=========================================="
echo "動作確認"
echo "=========================================="

echo ""
echo "ヘルスチェック..."
curl -s "${FUNCTION_URL}health" | jq '.'

echo ""
echo "ツール一覧..."
curl -s "${FUNCTION_URL}tools" | jq '.tools[].name'

# 5. 結果を保存
echo ""
echo "=========================================="
echo "✅ 移行完了！"
echo "=========================================="
echo ""
echo "新しいFunction URL: $FUNCTION_URL"
echo ""
echo "このURLをmcp_aws_wrapper.pyに設定してください："
echo "API_URL = \"${FUNCTION_URL%/}\""
echo ""
echo "タイムアウト: 300秒（5分）"
echo ""
