#!/bin/bash
# MCP over HTTP対応版をデプロイ

set -e

AWS_REGION="ap-northeast-1"
AWS_ACCOUNT_ID="639135896267"
CLUSTER_NAME="estat-mcp-cluster"
SERVICE_NAME="estat-mcp-service"
TASK_FAMILY="estat-mcp-task"
ECR_REPO_NAME="estat-mcp-server"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo "=========================================="
echo "MCP over HTTP対応版デプロイ"
echo "=========================================="
echo ""

# 1. Dockerイメージをビルド
echo "1. Dockerイメージをビルド中..."
docker buildx build --platform linux/amd64 -t $ECR_REPO_NAME:latest . --load
echo "✅ イメージビルド完了"

# 2. ECRにログイン
echo ""
echo "2. ECRにログイン..."
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_URI
echo "✅ ECRログイン成功"

# 3. イメージをプッシュ
echo ""
echo "3. イメージをECRにプッシュ..."
docker tag $ECR_REPO_NAME:latest $ECR_URI:latest
docker push $ECR_URI:latest
echo "✅ イメージプッシュ完了"

# 4. ECSサービスを更新
echo ""
echo "4. ECSサービスを更新..."
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --force-new-deployment \
  --region $AWS_REGION
echo "✅ サービス更新開始"

# 5. デプロイ完了を待機
echo ""
echo "5. デプロイ完了を待機中..."
echo "⏳ これには数分かかる場合があります..."
aws ecs wait services-stable \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME \
  --region $AWS_REGION

echo ""
echo "=========================================="
echo "✅ デプロイ完了！"
echo "=========================================="
echo ""
echo "MCP endpoint: https://estat-mcp.snowmole.co.jp/mcp"
echo ""
echo "動作確認:"
echo "curl -X POST https://estat-mcp.snowmole.co.jp/mcp \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"test\",\"version\":\"1.0\"}}}'"
echo ""
echo "Kiro設定を更新:"
echo '  "url": "https://estat-mcp.snowmole.co.jp/mcp"'
echo ""
