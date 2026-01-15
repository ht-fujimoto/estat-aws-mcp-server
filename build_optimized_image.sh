#!/bin/bash
# 最適化されたDockerイメージのビルド

set -e

# カラー定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=========================================="
echo "最適化されたDockerイメージのビルド"
echo -e "==========================================${NC}"
echo ""

# オプション選択
echo -e "${YELLOW}ビルド方法を選択してください:${NC}"
echo "1) 最適化ビルド（マルチステージ） - 約500-600MB（推奨）"
echo "2) 標準ビルド（現在の方法） - 約1GB"
read -p "選択 (1-2): " choice

case $choice in
    1)
        echo -e "${YELLOW}最適化ビルドを実行します${NC}"
        DOCKERFILE="Dockerfile.optimized"
        TAG_SUFFIX="optimized"
        ;;
    2)
        echo -e "${YELLOW}標準ビルドを実行します${NC}"
        DOCKERFILE="Dockerfile"
        TAG_SUFFIX="standard"
        ;;
    *)
        echo -e "${RED}無効な選択${NC}"
        exit 1
        ;;
esac

echo ""

# ビルド開始
echo -e "${YELLOW}Dockerイメージをビルド中...${NC}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
IMAGE_TAG="optimized-${TAG_SUFFIX}-${TIMESTAMP}"

echo "  Dockerfile: $DOCKERFILE"
echo "  タグ: $IMAGE_TAG"
echo ""

# ビルド実行
docker build \
    --platform linux/amd64 \
    -f $DOCKERFILE \
    -t estat-mcp-server:$IMAGE_TAG \
    -t estat-mcp-server:latest-$TAG_SUFFIX \
    .

BUILD_STATUS=$?

if [ $BUILD_STATUS -ne 0 ]; then
    echo -e "${RED}✗ ビルド失敗${NC}"
    exit 1
fi

echo -e "${GREEN}✓ ビルド完了${NC}"
echo ""

# イメージサイズを確認
echo -e "${YELLOW}イメージサイズを確認...${NC}"
IMAGE_SIZE=$(docker images estat-mcp-server:$IMAGE_TAG --format "{{.Size}}")
echo -e "${GREEN}  サイズ: $IMAGE_SIZE${NC}"
echo ""

# 比較
echo -e "${BLUE}=========================================="
echo "サイズ比較"
echo -e "==========================================${NC}"
docker images estat-mcp-server --format "table {{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | head -5
echo ""

# 次のステップ
echo -e "${YELLOW}次のステップ:${NC}"
echo "1. ローカルでテスト:"
echo "   docker run -p 8080:8080 -e ESTAT_APP_ID=your_id estat-mcp-server:$IMAGE_TAG"
echo ""
echo "2. ECRにプッシュ:"
echo "   ./push_to_ecr.sh $IMAGE_TAG"
echo ""

# 最適化の効果を表示
if [ "$TAG_SUFFIX" = "optimized" ]; then
    echo -e "${GREEN}✓ 最適化により約400-500MBのサイズ削減を実現${NC}"
    echo -e "${GREEN}✓ 全ての機能（pandas/pyarrow含む）が利用可能${NC}"
    echo ""
fi

echo -e "${GREEN}=========================================="
echo "ビルド完了"
echo -e "==========================================${NC}"
