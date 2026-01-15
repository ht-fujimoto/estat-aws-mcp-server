#!/bin/bash
# Google Cloud Runへのデプロイスクリプト

set -e

echo "=== Google Cloud Run Deployment ==="
echo ""

# カラー定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 設定
PROJECT_ID=${GCP_PROJECT_ID:-"your-project-id"}
SERVICE_NAME="estat-mcp-server"
REGION="asia-northeast1"
MEMORY="512Mi"
CPU="1"
MAX_INSTANCES="10"
MIN_INSTANCES="0"

# 環境変数の確認
if [ -z "$ESTAT_APP_ID" ]; then
    echo -e "${RED}Error: ESTAT_APP_ID environment variable is not set${NC}"
    echo "Please set it with: export ESTAT_APP_ID=your_api_key"
    exit 1
fi

# Google Cloud SDKの確認
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# プロジェクトの設定
echo -e "${YELLOW}Step 1: Setting up project...${NC}"
gcloud config set project $PROJECT_ID
echo -e "${GREEN}✓ Project set to $PROJECT_ID${NC}"
echo ""

# Cloud Run APIの有効化
echo -e "${YELLOW}Step 2: Enabling Cloud Run API...${NC}"
gcloud services enable run.googleapis.com
echo -e "${GREEN}✓ Cloud Run API enabled${NC}"
echo ""

# デプロイ
echo -e "${YELLOW}Step 3: Deploying to Cloud Run...${NC}"
gcloud run deploy $SERVICE_NAME \
    --source . \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory $MEMORY \
    --cpu $CPU \
    --max-instances $MAX_INSTANCES \
    --min-instances $MIN_INSTANCES \
    --set-env-vars "ESTAT_APP_ID=$ESTAT_APP_ID,S3_BUCKET=${S3_BUCKET:-estat-data-lake},AWS_REGION=${AWS_REGION:-ap-northeast-1}" \
    --timeout 300

echo ""
echo -e "${GREEN}✓ Deployment complete!${NC}"
echo ""

# サービスURLの取得
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')

echo -e "${GREEN}=== Deployment Summary ===${NC}"
echo "Service Name: $SERVICE_NAME"
echo "Region: $REGION"
echo "Service URL: $SERVICE_URL"
echo ""
echo "Test endpoints:"
echo "  Health: curl $SERVICE_URL/health"
echo "  Tools:  curl $SERVICE_URL/tools"
echo ""
echo "Kiro configuration:"
echo '{'
echo '  "mcpServers": {'
echo '    "estat-cloud": {'
echo '      "command": "curl",'
echo '      "args": ['
echo '        "-X", "POST",'
echo "        \"$SERVICE_URL/execute\","
echo '        "-H", "Content-Type: application/json",'
echo '        "-d", "@-"'
echo '      ]'
echo '    }'
echo '  }'
echo '}'
