#!/bin/bash
# ECSタスク定義を更新してサービスをデプロイ

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
ECR_REPO_NAME="estat-mcp-server"
CLUSTER_NAME="estat-mcp-cluster"
SERVICE_NAME="estat-mcp-service"

# 引数チェック
if [ -z "$1" ]; then
    echo -e "${RED}使用方法: $0 <image-tag>${NC}"
    exit 1
fi

IMAGE_TAG=$1
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:${IMAGE_TAG}"

echo -e "${BLUE}=========================================="
echo "ECSタスク定義の更新"
echo -e "==========================================${NC}"
echo ""
echo "イメージ: $ECR_URI"
echo ""

# 現在のタスク定義を取得
echo -e "${YELLOW}Step 1: 現在のタスク定義を取得...${NC}"
CURRENT_TASK_DEF=$(aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME \
  --region $AWS_REGION \
  --query "services[0].taskDefinition" \
  --output text)

echo "現在のタスク定義: $CURRENT_TASK_DEF"
echo ""

# タスク定義の詳細を取得してファイルに保存
echo -e "${YELLOW}Step 2: タスク定義の詳細を取得...${NC}"
aws ecs describe-task-definition \
  --task-definition $CURRENT_TASK_DEF \
  --region $AWS_REGION \
  --query "taskDefinition" > /tmp/task-def-original.json

# 不要なフィールドを削除し、イメージを更新
jq --arg IMAGE "$ECR_URI" '
  .containerDefinitions[0].image = $IMAGE |
  del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)
' /tmp/task-def-original.json > /tmp/task-def-new.json

echo -e "${GREEN}✓ 新しいタスク定義を準備しました${NC}"
echo ""

# 新しいタスク定義を登録
echo -e "${YELLOW}Step 3: 新しいタスク定義を登録...${NC}"
NEW_TASK_DEF_ARN=$(aws ecs register-task-definition \
  --cli-input-json file:///tmp/task-def-new.json \
  --region $AWS_REGION \
  --query "taskDefinition.taskDefinitionArn" \
  --output text)

echo -e "${GREEN}✓ 新しいタスク定義: $NEW_TASK_DEF_ARN${NC}"
echo ""

# サービスを更新
echo -e "${YELLOW}Step 4: サービスを更新...${NC}"
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service $SERVICE_NAME \
  --task-definition $NEW_TASK_DEF_ARN \
  --force-new-deployment \
  --region $AWS_REGION \
  --query "service.serviceName" \
  --output text >/dev/null

echo -e "${GREEN}✓ サービス更新を開始しました${NC}"
echo ""

# デプロイの進行状況を監視
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

# 動作確認
echo -e "${YELLOW}Step 6: 動作確認...${NC}"
echo ""

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
  echo ""
  
  if echo "$HEALTH_CHECK" | jq -e '.status == "healthy"' >/dev/null 2>&1; then
    echo -e "${GREEN}✓ サービスは正常に動作しています${NC}"
    
    # ツール一覧を確認
    echo ""
    echo "  ツール一覧を確認中..."
    TOOLS_RESPONSE=$(curl -s -X POST "$API_URL/mcp" \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' 2>/dev/null || echo '{}')
    
    TOOL_COUNT=$(echo "$TOOLS_RESPONSE" | jq -r '.result.tools | length' 2>/dev/null || echo "0")
    
    if [ "$TOOL_COUNT" -gt 0 ]; then
      echo -e "${GREEN}✓ ツール数: $TOOL_COUNT${NC}"
      
      # get_estat_table_url ツールが含まれているか確認
      HAS_NEW_TOOL=$(echo "$TOOLS_RESPONSE" | jq -r '.result.tools[] | select(.name=="get_estat_table_url") | .name' 2>/dev/null || echo "")
      
      if [ "$HAS_NEW_TOOL" = "get_estat_table_url" ]; then
        echo -e "${GREEN}✓ 新しいツール 'get_estat_table_url' が正常に登録されています！${NC}"
      else
        echo -e "${YELLOW}⚠ 新しいツールが見つかりません${NC}"
      fi
    else
      echo -e "${YELLOW}⚠ ツール一覧の取得に失敗しました${NC}"
    fi
  else
    echo -e "${YELLOW}⚠ サービスはまだ起動中です${NC}"
  fi
fi

echo ""
echo -e "${GREEN}=========================================="
echo "更新完了"
echo -e "==========================================${NC}"
echo ""
echo "タスク定義: $NEW_TASK_DEF_ARN"
echo "イメージ: $ECR_URI"

# 一時ファイルを削除
rm -f /tmp/task-def-original.json /tmp/task-def-new.json
