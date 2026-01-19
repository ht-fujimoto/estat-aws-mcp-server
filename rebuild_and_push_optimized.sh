#!/bin/bash
# 最適化されたDockerイメージのビルドとプッシュ

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

echo -e "${BLUE}=========================================="
echo "最適化されたイメージビルド"
echo -e "==========================================${NC}"
echo ""

# 1. 古いビルドキャッシュをクリーンアップ
echo -e "${YELLOW}Step 1: 古いイメージをクリーンアップ...${NC}"
docker image prune -f
echo -e "${GREEN}✓ クリーンアップ完了${NC}"
echo ""

# 2. ECRにログイン
echo -e "${YELLOW}Step 2: ECRにログイン...${NC}"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_URI
echo -e "${GREEN}✓ ECRログイン成功${NC}"
echo ""

# 3. 既存のイメージをプル（キャッシュとして使用）
echo -e "${YELLOW}Step 3: 既存のイメージをプル（キャッシュ用）...${NC}"
docker pull $ECR_URI:latest || echo "既存のイメージなし"
echo ""

# 4. 新しいイメージをビルド（キャッシュを活用）
echo -e "${YELLOW}Step 4: 新しいイメージをビルド...${NC}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
IMAGE_TAG="athena-fix-${TIMESTAMP}"

echo "  タグ: $IMAGE_TAG"
echo "  キャッシュを活用してビルド中..."

docker build \
  --platform linux/amd64 \
  --cache-from $ECR_URI:latest \
  -t $ECR_REPO_NAME:$IMAGE_TAG \
  -t $ECR_REPO_NAME:latest \
  .

echo -e "${GREEN}✓ ビルド完了${NC}"
echo ""

# 5. イメージサイズを確認
echo -e "${YELLOW}Step 5: イメージサイズを確認...${NC}"
IMAGE_SIZE=$(docker images $ECR_REPO_NAME:$IMAGE_TAG --format "{{.Size}}")
echo "  サイズ: $IMAGE_SIZE"
echo ""

# 6. イメージを圧縮してプッシュ
echo -e "${YELLOW}Step 6: イメージをECRにプッシュ...${NC}"
echo "  注: 大きなイメージの場合、数分かかることがあります"
echo ""

# タグ付け
docker tag $ECR_REPO_NAME:$IMAGE_TAG $ECR_URI:$IMAGE_TAG
docker tag $ECR_REPO_NAME:latest $ECR_URI:latest

# プッシュ（タイムスタンプ付きタグ）
echo "  プッシュ中: $IMAGE_TAG"
docker push $ECR_URI:$IMAGE_TAG &
PUSH_PID=$!

# 進行状況を表示
WAIT_COUNT=0
while kill -0 $PUSH_PID 2>/dev/null; do
  echo -e "  ${BLUE}プッシュ中... ($((WAIT_COUNT * 5))秒経過)${NC}"
  sleep 5
  WAIT_COUNT=$((WAIT_COUNT + 1))
  
  # 5分経過したら警告
  if [ $WAIT_COUNT -ge 60 ]; then
    echo -e "${YELLOW}⚠ プッシュに時間がかかっています。ネットワーク接続を確認してください。${NC}"
    echo "  Ctrl+C でキャンセルできます"
  fi
done

wait $PUSH_PID
PUSH_STATUS=$?

if [ $PUSH_STATUS -eq 0 ]; then
  echo -e "${GREEN}✓ プッシュ完了: $IMAGE_TAG${NC}"
else
  echo -e "${RED}✗ プッシュ失敗${NC}"
  exit 1
fi

echo ""

# latestタグもプッシュ
echo "  プッシュ中: latest"
docker push $ECR_URI:latest
echo -e "${GREEN}✓ プッシュ完了: latest${NC}"

echo ""
echo -e "${GREEN}=========================================="
echo "イメージのビルドとプッシュが完了しました"
echo -e "==========================================${NC}"
echo ""
echo "新しいイメージ: $ECR_URI:$IMAGE_TAG"
echo ""
echo "次のステップ:"
echo "  ./update_ecs_service.sh $IMAGE_TAG"
