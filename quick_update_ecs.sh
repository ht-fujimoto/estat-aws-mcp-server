#!/bin/bash
# ECSサービスのクイック更新スクリプト
# 既存のイメージを使用して強制的に再デプロイ

set -e

# カラー定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# 設定
AWS_REGION="ap-northeast-1"
CLUSTER_NAME="estat-mcp-cluster"
SERVICE_NAME="estat-mcp-service"

echo -e "${BLUE}=========================================="
echo "ECSサービス クイック更新"
echo -e "==========================================${NC}"
echo ""

# 1. 現在の状態を確認
echo -e "${YELLOW}Step 1: 現在のサービス状態を確認...${NC}"
CURRENT_STATUS=$(aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME \
  --region $AWS_REGION \
  --query "services[0].status" \
  --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$CURRENT_STATUS" = "NOT_FOUND" ]; then
  echo -e "${RED}✗ サービスが見つかりません${NC}"
  exit 1
fi

echo -e "${GREEN}✓ サービス状態: $CURRENT_STATUS${NC}"

# 現在のタスク数を確認
RUNNING_COUNT=$(aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME \
  --region $AWS_REGION \
  --query "services[0].runningCount" \
  --output text)

echo -e "${GREEN}✓ 実行中のタスク: $RUNNING_COUNT${NC}"
echo ""

# 2. 強制的に新しいデプロイを実行
echo -e "${YELLOW}Step 2: 強制的に新しいデプロイを実行...${NC}"
echo "  注: これにより既存のタスクが再起動されます"
echo ""

aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --force-new-deployment \
  --region $AWS_REGION \
  --query "service.serviceName" \
  --output text >/dev/null

echo -e "${GREEN}✓ デプロイを開始しました${NC}"
echo ""

# 3. デプロイの進行状況を監視
echo -e "${YELLOW}Step 3: デプロイの進行状況を監視...${NC}"
echo ""

MAX_WAIT=300
WAIT_INTERVAL=10
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
  
  echo -e "  ${BLUE}[$(date +%H:%M:%S)] 進行状況: $PRIMARY_RUNNING/$PRIMARY_DESIRED タスクが実行中 (デプロイメント数: $DEPLOYMENT_COUNT)${NC}"
  
  if [ "$DEPLOYMENT_COUNT" -eq 1 ] && [ "$PRIMARY_RUNNING" -eq "$PRIMARY_DESIRED" ]; then
    echo -e "${GREEN}✓ デプロイ完了！${NC}"
    break
  fi
  
  sleep $WAIT_INTERVAL
  ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
  echo -e "${YELLOW}⚠ タイムアウト: デプロイに時間がかかっています${NC}"
fi

echo ""

# 4. 動作確認
echo -e "${YELLOW}Step 4: 動作確認...${NC}"

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
  sleep 5
  
  HEALTH_CHECK=$(curl -s "$API_URL/health" 2>/dev/null || echo '{"status":"pending"}')
  echo "  結果: $HEALTH_CHECK"
  
  if echo "$HEALTH_CHECK" | jq -e '.status == "healthy"' >/dev/null 2>&1; then
    echo -e "${GREEN}✓ サービスは正常に動作しています${NC}"
  else
    echo -e "${YELLOW}⚠ サービスはまだ起動中です${NC}"
  fi
fi

echo ""
echo -e "${GREEN}=========================================="
echo "更新完了"
echo -e "==========================================${NC}"
