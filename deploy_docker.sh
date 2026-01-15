#!/bin/bash
# Docker + Docker Composeでのローカル/VPSデプロイスクリプト

set -e

echo "=== Docker Deployment ==="
echo ""

# カラー定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 環境変数の確認
if [ -z "$ESTAT_APP_ID" ]; then
    echo -e "${RED}Error: ESTAT_APP_ID environment variable is not set${NC}"
    echo "Please set it with: export ESTAT_APP_ID=your_api_key"
    exit 1
fi

# Dockerの確認
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Install from: https://docs.docker.com/get-docker/"
    exit 1
fi

# Docker Composeの確認
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    echo "Install from: https://docs.docker.com/compose/install/"
    exit 1
fi

# .envファイルの作成
echo -e "${YELLOW}Step 1: Creating .env file...${NC}"
cat > .env << EOF
ESTAT_APP_ID=$ESTAT_APP_ID
S3_BUCKET=${S3_BUCKET:-estat-data-lake}
AWS_REGION=${AWS_REGION:-ap-northeast-1}
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-}
EOF
echo -e "${GREEN}✓ .env file created${NC}"
echo ""

# SSL証明書の生成（自己署名）
echo -e "${YELLOW}Step 2: Generating self-signed SSL certificate...${NC}"
mkdir -p ssl
if [ ! -f "ssl/cert.pem" ]; then
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout ssl/key.pem -out ssl/cert.pem \
        -subj "/C=JP/ST=Tokyo/L=Tokyo/O=Organization/CN=localhost"
    echo -e "${GREEN}✓ SSL certificate generated${NC}"
else
    echo -e "${GREEN}✓ SSL certificate already exists${NC}"
fi
echo ""

# 古いコンテナの停止と削除
echo -e "${YELLOW}Step 3: Stopping old containers...${NC}"
docker-compose down 2>/dev/null || true
echo -e "${GREEN}✓ Old containers stopped${NC}"
echo ""

# イメージのビルド
echo -e "${YELLOW}Step 4: Building Docker image...${NC}"
docker-compose build
echo -e "${GREEN}✓ Docker image built${NC}"
echo ""

# コンテナの起動
echo -e "${YELLOW}Step 5: Starting containers...${NC}"
docker-compose up -d
echo -e "${GREEN}✓ Containers started${NC}"
echo ""

# ヘルスチェック
echo -e "${YELLOW}Step 6: Waiting for service to be ready...${NC}"
sleep 5

MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Service is ready!${NC}"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for service... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}Error: Service failed to start${NC}"
    echo "Check logs with: docker-compose logs"
    exit 1
fi
echo ""

# デプロイ情報の表示
echo -e "${GREEN}=== Deployment Summary ===${NC}"
echo "Service: estat-mcp-server"
echo "Status: Running"
echo ""
echo "Endpoints:"
echo "  HTTP:  http://localhost:8080"
echo "  HTTPS: https://localhost (with self-signed cert)"
echo ""
echo "Test endpoints:"
echo "  Health: curl http://localhost:8080/health"
echo "  Tools:  curl http://localhost:8080/tools"
echo ""
echo "View logs:"
echo "  docker-compose logs -f"
echo ""
echo "Stop service:"
echo "  docker-compose down"
echo ""
echo "Kiro configuration (local):"
echo '{'
echo '  "mcpServers": {'
echo '    "estat-local": {'
echo '      "command": "curl",'
echo '      "args": ['
echo '        "-X", "POST",'
echo '        "http://localhost:8080/execute",'
echo '        "-H", "Content-Type: application/json",'
echo '        "-d", "@-"'
echo '      ]'
echo '    }'
echo '  }'
echo '}'
echo ""
echo -e "${YELLOW}Note: For production deployment, replace localhost with your domain${NC}"
