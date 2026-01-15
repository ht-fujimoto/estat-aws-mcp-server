#!/bin/bash
# ECS Fargate MCPサーバー更新スクリプト
# url/httpUrl型のMCPトランスポートに対応

set -e

# 設定
AWS_REGION="ap-northeast-1"
AWS_ACCOUNT_ID="639135896267"
CLUSTER_NAME="estat-mcp-cluster"
SERVICE_NAME="estat-mcp-service"
TASK_FAMILY="estat-mcp-task"
ECR_REPO_NAME="estat-mcp-server"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo "=========================================="
echo "ECS Fargate MCP更新（url/httpUrl型対応）"
echo "=========================================="
echo ""

# 1. Dockerイメージをビルド（amd64用）
echo "1. Dockerイメージをビルド（amd64アーキテクチャ）..."
docker buildx build --platform linux/amd64 -t $ECR_REPO_NAME:latest . --load
echo "✅ イメージビルド完了"

# 2. ECRにログイン
echo ""
echo "2. ECRにログイン..."
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_URI
echo "✅ ECRログイン成功"

# 3. イメージをタグ付けしてプッシュ
echo ""
echo "3. イメージをECRにプッシュ..."
docker tag $ECR_REPO_NAME:latest $ECR_URI:latest
docker push $ECR_URI:latest
echo "✅ イメージプッシュ完了"

# 4. タスク定義を更新
echo ""
echo "4. タスク定義を更新..."
aws ecs register-task-definition \
  --cli-input-json file://task-definition.json \
  --region $AWS_REGION
echo "✅ タスク定義更新完了"

# 5. ECSサービスを更新（新しいデプロイを強制）
echo ""
echo "5. ECSサービスを更新..."
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --force-new-deployment \
  --region $AWS_REGION
echo "✅ サービス更新開始"

# 6. デプロイ完了を待機
echo ""
echo "6. デプロイ完了を待機中..."
echo "⏳ これには数分かかる場合があります..."
aws ecs wait services-stable \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME \
  --region $AWS_REGION

echo ""
echo "=========================================="
echo "✅ 更新完了！"
echo "=========================================="
echo ""
echo "MCPサーバーURL: http://estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com/mcp"
echo ""
echo "Kiro設定（.kiro/settings/mcp.json）:"
echo '  "estat-aws-remote": {'
echo '    "transport": "streamable-http",'
echo '    "url": "http://estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com/mcp",'
echo '    "disabled": false'
echo '  }'
echo ""
echo "動作確認:"
echo "curl http://estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com/health"
echo ""
echo "ログ確認:"
echo "aws logs tail /ecs/estat-mcp --follow --region $AWS_REGION"
echo ""
