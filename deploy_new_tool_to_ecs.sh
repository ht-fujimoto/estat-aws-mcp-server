#!/bin/bash
# 新しいツール（get_estat_table_url）をECSにデプロイ

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
IMAGE_TAG="v2.2.0-$(date +%Y%m%d-%H%M%S)"

echo -e "${BLUE}=========================================="
echo "新しいツールのECSデプロイ"
echo "get_estat_table_url ツール追加"
echo -e "==========================================${NC}"
echo ""
echo "イメージタグ: $IMAGE_TAG"
echo ""

# Step 1: Dockerイメージをビルド（linux/amd64用）
echo -e "${YELLOW}Step 1: Dockerイメージをビルド（linux/amd64用）...${NC}"
echo "  注: Apple Siliconでlinux/amd64用にビルドします"
echo ""

docker build --platform linux/amd64 -t estat-mcp-server:$IMAGE_TAG -f Dockerfile.optimized .

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ ビルド失敗${NC}"
    exit 1
fi

echo -e "${GREEN}✓ ビルド完了（linux/amd64）${NC}"
echo ""

# イメージサイズを表示
IMAGE_SIZE=$(docker images estat-mcp-server:$IMAGE_TAG --format "{{.Size}}")
echo -e "${GREEN}イメージサイズ: $IMAGE_SIZE${NC}"
echo ""

# Step 2: ECRにログイン
echo -e "${YELLOW}Step 2: ECRにログイン...${NC}"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_URI

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ ECRログイン失敗${NC}"
    exit 1
fi

echo -e "${GREEN}✓ ECRログイン成功${NC}"
echo ""

# Step 3: イメージをタグ付け
echo -e "${YELLOW}Step 3: イメージをタグ付け...${NC}"
docker tag estat-mcp-server:$IMAGE_TAG $ECR_URI:$IMAGE_TAG
docker tag estat-mcp-server:$IMAGE_TAG $ECR_URI:latest
echo -e "${GREEN}✓ タグ付け完了${NC}"
echo ""

# Step 4: ECRにプッシュ
echo -e "${YELLOW}Step 4: ECRにプッシュ...${NC}"
echo "  これには数分かかる場合があります..."
echo ""

# プッシュ（タイムスタンプ付きタグ）
echo "  プッシュ中: $IMAGE_TAG"
docker push $ECR_URI:$IMAGE_TAG

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ プッシュ失敗${NC}"
    exit 1
fi

echo -e "${GREEN}✓ プッシュ完了: $IMAGE_TAG${NC}"
echo ""

# latestタグもプッシュ
echo "  プッシュ中: latest"
docker push $ECR_URI:latest

if [ $? -ne 0 ]; then
    echo -e "${YELLOW}⚠ latestタグのプッシュに失敗（継続）${NC}"
else
    echo -e "${GREEN}✓ プッシュ完了: latest${NC}"
fi

echo ""

# Step 5: ECSサービスを更新
echo -e "${YELLOW}Step 5: ECSサービスを更新...${NC}"
echo ""

# 現在のタスク定義を取得
CURRENT_TASK_DEF=$(aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME \
  --region $AWS_REGION \
  --query "services[0].taskDefinition" \
  --output text)

echo "現在のタスク定義: $CURRENT_TASK_DEF"

# 新しいタスク定義を作成（イメージのみ更新）
TASK_FAMILY=$(echo $CURRENT_TASK_DEF | cut -d'/' -f2 | cut -d':' -f1)

echo "タスクファミリー: $TASK_FAMILY"
echo ""

# 既存のタスク定義を取得
TASK_DEF_JSON=$(aws ecs describe-task-definition \
  --task-definition $CURRENT_TASK_DEF \
  --region $AWS_REGION \
  --query "taskDefinition")

# 新しいイメージURIで更新
NEW_TASK_DEF=$(echo $TASK_DEF_JSON | jq --arg IMAGE "$ECR_URI:$IMAGE_TAG" '
  .containerDefinitions[0].image = $IMAGE |
  del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)
')

# 新しいタスク定義を登録
echo "新しいタスク定義を登録中..."
NEW_TASK_DEF_ARN=$(echo $NEW_TASK_DEF | aws ecs register-task-definition \
  --cli-input-json file:///dev/stdin \
  --region $AWS_REGION \
  --query "taskDefinition.taskDefinitionArn" \
  --output text)

echo -e "${GREEN}✓ 新しいタスク定義: $NEW_TASK_DEF_ARN${NC}"
echo ""

# サービスを更新
echo "サービスを更新中..."
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

# Step 6: デプロイの進行状況を監視
echo -e "${YELLOW}Step 6: デプロイの進行状況を監視...${NC}"
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
  echo "  手動で確認してください: aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME"
fi

echo ""

# Step 7: 動作確認
echo -e "${YELLOW}Step 7: 動作確認...${NC}"
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
echo "デプロイ完了"
echo -e "==========================================${NC}"
echo ""
echo "デプロイ情報:"
echo "  イメージタグ: $IMAGE_TAG"
echo "  ECR URI: $ECR_URI:$IMAGE_TAG"
echo "  タスク定義: $NEW_TASK_DEF_ARN"
echo ""
echo "API エンドポイント:"
echo "  $API_URL"
echo ""
echo "新しいツール:"
echo "  - get_estat_table_url: 統計表IDからe-Statホームページのリンクを生成"
echo ""
echo "確認コマンド:"
echo "  curl -X POST $API_URL/mcp -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{}}' | jq '.result.tools[] | select(.name==\"get_estat_table_url\")'"

