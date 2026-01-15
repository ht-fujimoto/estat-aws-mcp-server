#!/bin/bash
# 実行中のコンテナに修正ファイルをパッチする（開発/テスト用）

set -e

# カラー定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=========================================="
echo "コンテナパッチ適用（開発用）"
echo -e "==========================================${NC}"
echo ""
echo -e "${RED}警告: これは一時的な修正です。${NC}"
echo -e "${RED}本番環境では新しいイメージをビルドしてください。${NC}"
echo ""

# 設定
AWS_REGION="ap-northeast-1"
CLUSTER_NAME="estat-mcp-cluster"
SERVICE_NAME="estat-mcp-service"

# 1. 実行中のタスクを取得
echo -e "${YELLOW}Step 1: 実行中のタスクを取得...${NC}"
TASK_ARN=$(aws ecs list-tasks \
  --cluster $CLUSTER_NAME \
  --service-name $SERVICE_NAME \
  --region $AWS_REGION \
  --query "taskArns[0]" \
  --output text)

if [ "$TASK_ARN" = "None" ] || [ -z "$TASK_ARN" ]; then
  echo -e "${RED}✗ 実行中のタスクが見つかりません${NC}"
  exit 1
fi

echo -e "${GREEN}✓ タスクARN: $TASK_ARN${NC}"
echo ""

# 2. タスクの詳細を取得
echo -e "${YELLOW}Step 2: タスクの詳細を取得...${NC}"
TASK_DETAILS=$(aws ecs describe-tasks \
  --cluster $CLUSTER_NAME \
  --tasks $TASK_ARN \
  --region $AWS_REGION)

CONTAINER_RUNTIME_ID=$(echo "$TASK_DETAILS" | jq -r '.tasks[0].containers[0].runtimeId')

if [ -z "$CONTAINER_RUNTIME_ID" ] || [ "$CONTAINER_RUNTIME_ID" = "null" ]; then
  echo -e "${RED}✗ コンテナIDを取得できません${NC}"
  exit 1
fi

echo -e "${GREEN}✓ コンテナID: $CONTAINER_RUNTIME_ID${NC}"
echo ""

# 3. ECS Execを有効化（必要な場合）
echo -e "${YELLOW}Step 3: ECS Execの確認...${NC}"
echo -e "${YELLOW}注: ECS Execが有効になっていない場合、この方法は使用できません${NC}"
echo -e "${YELLOW}代わりに新しいイメージをビルドしてください${NC}"
echo ""

echo -e "${BLUE}=========================================="
echo "代替案: 新しいイメージのビルド"
echo -e "==========================================${NC}"
echo ""
echo "修正を適用するには、以下のいずれかの方法を使用してください:"
echo ""
echo "1. 最適化されたビルド（推奨）:"
echo "   chmod +x rebuild_and_push_optimized.sh"
echo "   ./rebuild_and_push_optimized.sh"
echo ""
echo "2. 既存のイメージで強制再デプロイ（修正なし）:"
echo "   chmod +x quick_update_ecs.sh"
echo "   ./quick_update_ecs.sh"
echo ""
echo "3. 手動でDockerイメージをビルド:"
echo "   docker build -t estat-mcp-server:latest ."
echo "   # 次にECRにプッシュ"
echo ""
