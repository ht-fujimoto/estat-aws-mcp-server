#!/bin/bash
# 最適化されたイメージをECRにプッシュ

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

# 引数チェック
if [ -z "$1" ]; then
    echo -e "${RED}使用方法: $0 <image-tag>${NC}"
    echo ""
    echo "利用可能なイメージ:"
    docker images estat-mcp-server --format "  {{.Tag}}" | grep -v "<none>"
    exit 1
fi

IMAGE_TAG=$1

echo -e "${BLUE}=========================================="
echo "ECRへのプッシュ"
echo -e "==========================================${NC}"
echo ""
echo "イメージタグ: $IMAGE_TAG"
echo ""

# イメージの存在確認
if ! docker images estat-mcp-server:$IMAGE_TAG --format "{{.ID}}" | grep -q .; then
    echo -e "${RED}✗ イメージが見つかりません: estat-mcp-server:$IMAGE_TAG${NC}"
    exit 1
fi

# イメージサイズを表示
IMAGE_SIZE=$(docker images estat-mcp-server:$IMAGE_TAG --format "{{.Size}}")
echo -e "${GREEN}イメージサイズ: $IMAGE_SIZE${NC}"
echo ""

# ECRにログイン
echo -e "${YELLOW}Step 1: ECRにログイン...${NC}"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_URI

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ ECRログイン失敗${NC}"
    exit 1
fi

echo -e "${GREEN}✓ ECRログイン成功${NC}"
echo ""

# タグ付け
echo -e "${YELLOW}Step 2: イメージをタグ付け...${NC}"
docker tag estat-mcp-server:$IMAGE_TAG $ECR_URI:$IMAGE_TAG
docker tag estat-mcp-server:$IMAGE_TAG $ECR_URI:latest
echo -e "${GREEN}✓ タグ付け完了${NC}"
echo ""

# プッシュ
echo -e "${YELLOW}Step 3: ECRにプッシュ...${NC}"
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

# ECR上のイメージを確認
echo -e "${YELLOW}Step 4: ECR上のイメージを確認...${NC}"
aws ecr describe-images \
  --repository-name $ECR_REPO_NAME \
  --region $AWS_REGION \
  --query 'sort_by(imageDetails,& imagePushedAt)[-3:].[imageTags[0],imagePushedAt,imageSizeInBytes]' \
  --output table

echo ""
echo -e "${GREEN}=========================================="
echo "プッシュ完了"
echo -e "==========================================${NC}"
echo ""
echo "次のステップ:"
echo "  ECSサービスを更新:"
echo "  ./update_ecs_with_new_image.sh $IMAGE_TAG"
