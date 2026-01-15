#!/bin/bash
# Herokuへのデプロイスクリプト

set -e

echo "=== Heroku Deployment ==="
echo ""

# カラー定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 設定
APP_NAME=${HEROKU_APP_NAME:-"estat-mcp-server"}

# 環境変数の確認
if [ -z "$ESTAT_APP_ID" ]; then
    echo -e "${RED}Error: ESTAT_APP_ID environment variable is not set${NC}"
    echo "Please set it with: export ESTAT_APP_ID=your_api_key"
    exit 1
fi

# Heroku CLIの確認
if ! command -v heroku &> /dev/null; then
    echo -e "${RED}Error: Heroku CLI is not installed${NC}"
    echo "Install from: https://devcenter.heroku.com/articles/heroku-cli"
    exit 1
fi

# ログイン確認
echo -e "${YELLOW}Step 1: Checking Heroku login...${NC}"
if ! heroku auth:whoami &> /dev/null; then
    echo "Please login to Heroku:"
    heroku login
fi
echo -e "${GREEN}✓ Logged in to Heroku${NC}"
echo ""

# アプリケーションの作成または確認
echo -e "${YELLOW}Step 2: Creating/checking Heroku app...${NC}"
if heroku apps:info --app $APP_NAME &> /dev/null; then
    echo -e "${GREEN}✓ App $APP_NAME already exists${NC}"
else
    heroku create $APP_NAME
    echo -e "${GREEN}✓ Created app $APP_NAME${NC}"
fi
echo ""

# Procfileの作成
echo -e "${YELLOW}Step 3: Creating Procfile...${NC}"
cat > Procfile << EOF
web: python server_http.py
EOF
echo -e "${GREEN}✓ Procfile created${NC}"
echo ""

# 環境変数の設定
echo -e "${YELLOW}Step 4: Setting environment variables...${NC}"
heroku config:set ESTAT_APP_ID=$ESTAT_APP_ID --app $APP_NAME
heroku config:set S3_BUCKET=${S3_BUCKET:-estat-data-lake} --app $APP_NAME
heroku config:set AWS_REGION=${AWS_REGION:-ap-northeast-1} --app $APP_NAME

if [ ! -z "$AWS_ACCESS_KEY_ID" ]; then
    heroku config:set AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID --app $APP_NAME
fi

if [ ! -z "$AWS_SECRET_ACCESS_KEY" ]; then
    heroku config:set AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY --app $APP_NAME
fi

echo -e "${GREEN}✓ Environment variables set${NC}"
echo ""

# Gitリポジトリの初期化（必要な場合）
if [ ! -d ".git" ]; then
    echo -e "${YELLOW}Step 5: Initializing Git repository...${NC}"
    git init
    git add .
    git commit -m "Initial commit for Heroku deployment"
    echo -e "${GREEN}✓ Git repository initialized${NC}"
    echo ""
fi

# Herokuリモートの追加
echo -e "${YELLOW}Step 6: Adding Heroku remote...${NC}"
if ! git remote | grep -q heroku; then
    heroku git:remote --app $APP_NAME
    echo -e "${GREEN}✓ Heroku remote added${NC}"
else
    echo -e "${GREEN}✓ Heroku remote already exists${NC}"
fi
echo ""

# デプロイ
echo -e "${YELLOW}Step 7: Deploying to Heroku...${NC}"
git push heroku main || git push heroku master
echo -e "${GREEN}✓ Deployment complete!${NC}"
echo ""

# アプリケーションURLの取得
APP_URL=$(heroku apps:info --app $APP_NAME --json | python3 -c "import sys, json; print(json.load(sys.stdin)['app']['web_url'])")

echo -e "${GREEN}=== Deployment Summary ===${NC}"
echo "App Name: $APP_NAME"
echo "App URL: $APP_URL"
echo ""
echo "Test endpoints:"
echo "  Health: curl ${APP_URL}health"
echo "  Tools:  curl ${APP_URL}tools"
echo ""
echo "View logs:"
echo "  heroku logs --tail --app $APP_NAME"
echo ""
echo "Kiro configuration:"
echo '{'
echo '  "mcpServers": {'
echo '    "estat-cloud": {'
echo '      "command": "curl",'
echo '      "args": ['
echo '        "-X", "POST",'
echo "        \"${APP_URL}execute\","
echo '        "-H", "Content-Type: application/json",'
echo '        "-d", "@-"'
echo '      ]'
echo '    }'
echo '  }'
echo '}'
