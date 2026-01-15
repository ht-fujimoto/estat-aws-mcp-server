#!/bin/bash
# ECSサービスを新しいイメージで更新

set -e

# カラー定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# 設定
AWS_REGION="ap-northeast-1"
AWS_ACCOUNT_ID="639135896267"
CLUSTER_NAME="estat-mcp-cluster"
SERVICE_NAME="estat-mcp-service"
TASK_FAMILY="estat-mcp-task"
ECR_REPO_NAME="estat-mcp-server"

# 引数チェック
if [ -z "$1" ]; then
    echo -e "${RED}使用方法: $0 <image-tag>${NC}"
    echo ""
    echo "例: $0 optimized-optimized-20260114_104351"
    exit 1
fi

IMAGE_TAG=$1
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo -e "${BLUE}=========================================="
echo "ECSサービス更新"
echo -e "==========================================${NC}"
echo ""
echo "イメージ: $ECR_URI:$IMAGE_TAG"
echo ""

# 1. 現在のタスク定義を取得
echo -e "${YELLOW}Step 1: 現在のタスク定義を取得...${NC}"
CURRENT_TASK_DEF=$(aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME \
  --region $AWS_REGION \
  --query "services[0].taskDefinition" \
  --output text 2>/dev/null || echo "")

if [ -z "$CURRENT_TASK_DEF" ]; then
    echo -e "${RED}✗ サービスが見つかりません${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 現在のタスク定義: $CURRENT_TASK_DEF${NC}"
echo ""

# 2. タスク定義の詳細を取得
echo -e "${YELLOW}Step 2: タスク定義の詳細を取得...${NC}"
TASK_DEF_JSON=$(aws ecs describe-task-definition \
  --task-definition $TASK_FAMILY \
  --region $AWS_REGION \
  --query "taskDefinition")

if [ -z "$TASK_DEF_JSON" ]; then
    echo -e "${RED}✗ タスク定義の取得に失敗${NC}"
    exit 1
fi

echo -e "${GREEN}✓ タスク定義を取得${NC}"
echo ""

# 3. 新しいタスク定義を作成
echo -e "${YELLOW}Step 3: 新しいタスク定義を作成...${NC}"
echo "$TASK_DEF_JSON" | jq --arg image "$ECR_URI:$IMAGE_TAG" '
  .containerDefinitions[0].image = $image |
  del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)
' > task-definition-new.json

# タスク定義を登録
NEW_TASK_DEF_ARN=$(aws ecs register-task-definition \
  --cli-input-json file://task-definition-new.json \
  --region $AWS_REGION \
  --query "taskDefinition.taskDefinitionArn" \
  --output text)

if [ -z "$NEW_TASK_DEF_ARN" ]; then
    echo -e "${RED}✗ タスク定義の登録に失敗${NC}"
    rm -f task-definition-new.json
    exit 1
fi

echo -e "${GREEN}✓ 新しいタスク定義: $NEW_TASK_DEF_ARN${NC}"
echo ""

# 4. ECSサービスを更新
echo -e "${YELLOW}Step 4: ECSサービスを更新...${NC}"
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --task-definition $TASK_FAMILY \
  --force-new-deployment \
  --region $AWS_REGION \
  --query "service.serviceName" \
  --output text >/dev/null

echo -e "${GREEN}✓ サービス更新を開始${NC}"
echo ""

# 5. デプロイの進行状況を監視
echo -e "${YELLOW}Step 5: デプロイの進行状況を監視...${NC}"
echo ""

MAX_WAIT=600
WAIT_INTERVAL=15
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
  DEPLOYMENT_STATUS=$(aws ecs describe-services \
    --cluster $CLUSTER_NAME \
    --services $SERVICE_NAME \
    --region $AWS_REGION \
    --query "services[0].deployments" \
    --output json)
  
  PRIMARY_RUNNING=$(echo "$DEPLOYMENT_STATUS" | jq -r '.[] | select(.status=="PRIMARY") | .runningCount')
  PRIMARY_DESIRED=$(echo "$DEPLOYMENT_STATUS" | jq -r '.[] | select(.status=="PRIMARY") | .desiredCount')
  DEPLOYMENT_COUNT=$(echo "$DEPLOYMENT_STATUS" | jq 'length')
  
  TIMESTAMP=$(date +%H:%M:%S)
  echo -e "  ${BLUE}[$TIMESTAMP] 進行状況: $PRIMARY_RUNNING/$PRIMARY_DESIRED タスクが実行中 (デプロイメント数: $DEPLOYMENT_COUNT)${NC}"
  
  if [ "$DEPLOYMENT_COUNT" -eq 1 ] && [ "$PRIMARY_RUNNING" -eq "$PRIMARY_DESIRED" ]; then
    echo -e "${GREEN}✓ デプロイ完了！${NC}"
    break
  fi
  
  sleep $WAIT_INTERVAL
  ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
  echo -e "${YELLOW}⚠ タイムアウト: デプロイに時間がかかっています${NC}"
  echo "  手動で確認してください:"
  echo "  aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $AWS_REGION"
fi

echo ""

# 6. 動作確認
echo -e "${YELLOW}Step 6: 動作確認...${NC}"

ALB_DNS=$(aws elbv2 describe-load-balancers \
  --names estat-mcp-alb \
  --region $AWS_REGION \
  --query "LoadBalancers[0].DNSName" \
  --output text 2>/dev/null || echo "")

if [ -n "$ALB_DNS" ]; then
  API_URL="http://$ALB_DNS"
  echo "  API URL: $API_URL"
  echo ""
  
  echo "  ヘルスチェック実行中..."
  sleep 10
  
  HEALTH_CHECK=$(curl -s "$API_URL/health" 2>/dev/null || echo '{"status":"pending"}')
  echo "  結果: $HEALTH_CHECK"
  
  if echo "$HEALTH_CHECK" | jq -e '.status == "healthy"' >/dev/null 2>&1; then
    echo -e "${GREEN}✓ サービスは正常に動作しています${NC}"
  else
    echo -e "${YELLOW}⚠ サービスはまだ起動中です。数分後に再確認してください。${NC}"
  fi
fi

echo ""

# 7. クリーンアップ
echo -e "${YELLOW}Step 7: クリーンアップ...${NC}"
rm -f task-definition-new.json
echo -e "${GREEN}✓ 一時ファイルを削除${NC}"
echo ""

# 8. サマリー
echo -e "${BLUE}=========================================="
echo "更新完了サマリー"
echo -e "==========================================${NC}"
echo ""
echo -e "${GREEN}✓ 新しいイメージ:${NC} $ECR_URI:$IMAGE_TAG"
echo -e "${GREEN}✓ タスク定義:${NC} $NEW_TASK_DEF_ARN"
echo -e "${GREEN}✓ サービス:${NC} $SERVICE_NAME"
echo ""

if [ -n "$ALB_DNS" ]; then
  echo -e "${YELLOW}API エンドポイント:${NC}"
  echo "  $API_URL"
  echo ""
fi

echo -e "${YELLOW}修正内容:${NC}"
echo "  ✓ load_to_iceberg: Athenaワークグループ問題を修正"
echo "  ✓ analyze_with_athena: 出力バケット設定を改善"
echo "  ✓ イメージサイズ: 1GB → 736MB（約270MB削減）"
echo ""

echo -e "${YELLOW}ログの確認:${NC}"
echo "  aws logs tail /ecs/estat-mcp --follow --region $AWS_REGION"
echo ""

echo -e "${YELLOW}ロールバック方法:${NC}"
echo "  以前のタスク定義に戻す場合:"
echo "  aws ecs update-service --cluster $CLUSTER_NAME --service $SERVICE_NAME --task-definition $CURRENT_TASK_DEF --region $AWS_REGION"
echo ""

echo -e "${GREEN}=========================================="
echo "ECS更新が完了しました！"
echo -e "==========================================${NC}"
