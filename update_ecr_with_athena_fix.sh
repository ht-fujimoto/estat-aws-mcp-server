#!/bin/bash
# ECR更新スクリプト - Athenaツール修正版
# load_to_icebergとanalyze_with_athenaの修正を含む新しいイメージをデプロイ

set -e

# カラー定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 設定
AWS_REGION="ap-northeast-1"
AWS_ACCOUNT_ID="639135896267"
CLUSTER_NAME="estat-mcp-cluster"
SERVICE_NAME="estat-mcp-service"
TASK_FAMILY="estat-mcp-task"
ECR_REPO_NAME="estat-mcp-server"
CONTAINER_NAME="estat-mcp-container"

echo -e "${BLUE}=========================================="
echo "ECR更新 - Athenaツール修正版"
echo -e "==========================================${NC}"
echo ""
echo -e "${YELLOW}修正内容:${NC}"
echo "  - load_to_iceberg: Athenaワークグループ問題を修正"
echo "  - analyze_with_athena: 出力バケット設定を改善"
echo "  - エラーハンドリングを強化"
echo ""

# 1. 現在のバージョンを確認
echo -e "${YELLOW}Step 1: 現在のデプロイ状況を確認...${NC}"
CURRENT_TASK_DEF=$(aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME \
  --region $AWS_REGION \
  --query "services[0].taskDefinition" \
  --output text 2>/dev/null || echo "なし")

if [ "$CURRENT_TASK_DEF" != "なし" ]; then
  echo -e "${GREEN}✓ 現在のタスク定義: $CURRENT_TASK_DEF${NC}"
else
  echo -e "${YELLOW}⚠ サービスが見つかりません${NC}"
fi
echo ""

# 2. ECRリポジトリの確認
echo -e "${YELLOW}Step 2: ECRリポジトリを確認...${NC}"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"
aws ecr describe-repositories \
  --repository-names $ECR_REPO_NAME \
  --region $AWS_REGION >/dev/null 2>&1
echo -e "${GREEN}✓ ECRリポジトリ: $ECR_URI${NC}"
echo ""

# 3. Dockerイメージをビルド
echo -e "${YELLOW}Step 3: 新しいDockerイメージをビルド...${NC}"
echo "  修正されたコードを含むイメージを作成中..."

# タイムスタンプ付きタグを生成
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
IMAGE_TAG="athena-fix-${TIMESTAMP}"

docker build -t $ECR_REPO_NAME:$IMAGE_TAG -t $ECR_REPO_NAME:latest .
echo -e "${GREEN}✓ イメージビルド完了${NC}"
echo "  タグ: $IMAGE_TAG"
echo ""

# 4. ECRにログイン
echo -e "${YELLOW}Step 4: ECRにログイン...${NC}"
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_URI
echo -e "${GREEN}✓ ECRログイン成功${NC}"
echo ""

# 5. イメージをタグ付けしてプッシュ
echo -e "${YELLOW}Step 5: イメージをECRにプッシュ...${NC}"
docker tag $ECR_REPO_NAME:$IMAGE_TAG $ECR_URI:$IMAGE_TAG
docker tag $ECR_REPO_NAME:latest $ECR_URI:latest

echo "  プッシュ中: $ECR_URI:$IMAGE_TAG"
docker push $ECR_URI:$IMAGE_TAG

echo "  プッシュ中: $ECR_URI:latest"
docker push $ECR_URI:latest

echo -e "${GREEN}✓ イメージプッシュ完了${NC}"
echo ""

# 6. 新しいタスク定義を登録
echo -e "${YELLOW}Step 6: 新しいタスク定義を登録...${NC}"

# 既存のタスク定義を取得
TASK_DEF_JSON=$(aws ecs describe-task-definition \
  --task-definition $TASK_FAMILY \
  --region $AWS_REGION \
  --query "taskDefinition" 2>/dev/null || echo "{}")

if [ "$TASK_DEF_JSON" = "{}" ]; then
  echo -e "${RED}✗ 既存のタスク定義が見つかりません${NC}"
  echo "  deploy_ecs_fargate.sh を先に実行してください"
  exit 1
fi

# 新しいタスク定義を作成（イメージURLを更新）
echo "$TASK_DEF_JSON" | jq --arg image "$ECR_URI:$IMAGE_TAG" '
  .containerDefinitions[0].image = $image |
  del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)
' > task-definition-updated.json

# タスク定義を登録
NEW_TASK_DEF_ARN=$(aws ecs register-task-definition \
  --cli-input-json file://task-definition-updated.json \
  --region $AWS_REGION \
  --query "taskDefinition.taskDefinitionArn" \
  --output text)

echo -e "${GREEN}✓ 新しいタスク定義を登録: $NEW_TASK_DEF_ARN${NC}"
echo ""

# 7. ECSサービスを更新
echo -e "${YELLOW}Step 7: ECSサービスを更新...${NC}"
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

# 8. デプロイの進行状況を監視
echo -e "${YELLOW}Step 8: デプロイの進行状況を監視...${NC}"
echo "  新しいタスクの起動を待機中..."
echo ""

# 最大10分間待機
MAX_WAIT=600
WAIT_INTERVAL=15
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
  # サービスの状態を取得
  DEPLOYMENT_STATUS=$(aws ecs describe-services \
    --cluster $CLUSTER_NAME \
    --services $SERVICE_NAME \
    --region $AWS_REGION \
    --query "services[0].deployments" \
    --output json)
  
  # プライマリデプロイメントの状態を確認
  PRIMARY_RUNNING=$(echo "$DEPLOYMENT_STATUS" | jq -r '.[] | select(.status=="PRIMARY") | .runningCount')
  PRIMARY_DESIRED=$(echo "$DEPLOYMENT_STATUS" | jq -r '.[] | select(.status=="PRIMARY") | .desiredCount')
  
  echo -e "  ${BLUE}進行状況: $PRIMARY_RUNNING/$PRIMARY_DESIRED タスクが実行中${NC}"
  
  # デプロイメント数を確認
  DEPLOYMENT_COUNT=$(echo "$DEPLOYMENT_STATUS" | jq 'length')
  
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
else
  echo ""
fi

# 9. 動作確認
echo -e "${YELLOW}Step 9: 動作確認...${NC}"

# ALBのDNS名を取得
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
  sleep 10  # タスクの起動を待つ
  
  HEALTH_CHECK=$(curl -s "$API_URL/health" 2>/dev/null || echo '{"status":"pending"}')
  echo "  結果: $HEALTH_CHECK"
  
  if echo "$HEALTH_CHECK" | jq -e '.status == "healthy"' >/dev/null 2>&1; then
    echo -e "${GREEN}✓ サービスは正常に動作しています${NC}"
  else
    echo -e "${YELLOW}⚠ サービスはまだ起動中です。数分後に再確認してください。${NC}"
  fi
else
  echo -e "${YELLOW}⚠ ALBが見つかりません${NC}"
fi

echo ""

# 10. クリーンアップ
echo -e "${YELLOW}Step 10: クリーンアップ...${NC}"
rm -f task-definition-updated.json
echo -e "${GREEN}✓ 一時ファイルを削除${NC}"
echo ""

# 11. サマリー
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

echo -e "${YELLOW}修正内容の確認:${NC}"
echo "  1. load_to_icebergツールをテスト"
echo "  2. analyze_with_athenaツールをテスト"
echo "  3. エラーメッセージが改善されていることを確認"
echo ""

echo -e "${YELLOW}ログの確認:${NC}"
echo "  aws logs tail /ecs/estat-mcp --follow --region $AWS_REGION"
echo ""

echo -e "${YELLOW}ロールバック方法:${NC}"
echo "  以前のタスク定義に戻す場合:"
echo "  aws ecs update-service --cluster $CLUSTER_NAME --service $SERVICE_NAME --task-definition <previous-task-def> --region $AWS_REGION"
echo ""

echo -e "${GREEN}=========================================="
echo "ECR更新が完了しました！"
echo -e "==========================================${NC}"
