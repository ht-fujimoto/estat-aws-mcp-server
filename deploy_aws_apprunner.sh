#!/bin/bash
# AWS App Runner デプロイスクリプト（最も簡単）

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              AWS App Runner Deployment                       ║"
echo "║              (最も簡単なAWSデプロイ方法)                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# カラー定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# 設定
SERVICE_NAME="${AWS_SERVICE_NAME:-estat-mcp-server}"
REGION="${AWS_REGION:-ap-northeast-1}"
ECR_REPO_NAME="estat-mcp-server"

# 環境変数の確認
echo -e "${BLUE}Checking environment variables...${NC}"
if [ -z "$ESTAT_APP_ID" ]; then
    echo -e "${RED}Error: ESTAT_APP_ID environment variable is not set${NC}"
    echo "Please set it with: export ESTAT_APP_ID=your_api_key"
    exit 1
fi
echo -e "${GREEN}✓ ESTAT_APP_ID is set${NC}"

# AWS CLIの確認
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ AWS CLI is installed${NC}"

# Dockerの確認
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker is installed${NC}"

# AWS認証情報の確認
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✓ AWS credentials configured (Account: $ACCOUNT_ID)${NC}"
echo ""

# Step 1: ECRリポジトリの作成
echo -e "${YELLOW}Step 1/5: Creating ECR repository...${NC}"
if ! aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $REGION &> /dev/null; then
    aws ecr create-repository \
        --repository-name $ECR_REPO_NAME \
        --region $REGION > /dev/null
    echo -e "${GREEN}✓ ECR repository created${NC}"
else
    echo -e "${GREEN}✓ ECR repository already exists${NC}"
fi

ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO_NAME}"
echo "  ECR URI: $ECR_URI"
echo ""

# Step 2: ECRにログイン
echo -e "${YELLOW}Step 2/5: Logging in to ECR...${NC}"
aws ecr get-login-password --region $REGION | \
    docker login --username AWS --password-stdin $ECR_URI
echo -e "${GREEN}✓ Logged in to ECR${NC}"
echo ""

# Step 3: Dockerイメージのビルド
echo -e "${YELLOW}Step 3/5: Building Docker image...${NC}"
docker build -t $ECR_REPO_NAME:latest .
docker tag $ECR_REPO_NAME:latest $ECR_URI:latest
echo -e "${GREEN}✓ Docker image built${NC}"
echo ""

# Step 4: ECRにプッシュ
echo -e "${YELLOW}Step 4/5: Pushing image to ECR...${NC}"
docker push $ECR_URI:latest
echo -e "${GREEN}✓ Image pushed to ECR${NC}"
echo ""

# Step 5: App Runnerサービスの作成
echo -e "${YELLOW}Step 5/5: Creating App Runner service...${NC}"

# IAMロールの作成
ROLE_NAME="AppRunnerECRAccessRole"
if ! aws iam get-role --role-name $ROLE_NAME &> /dev/null; then
    cat > /tmp/apprunner-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "build.apprunner.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file:///tmp/apprunner-trust-policy.json > /dev/null
    
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
    
    sleep 5
fi

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

# サービス設定ファイルの作成
cat > /tmp/apprunner-config.json << EOF
{
  "ServiceName": "$SERVICE_NAME",
  "SourceConfiguration": {
    "ImageRepository": {
      "ImageIdentifier": "$ECR_URI:latest",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8080",
        "RuntimeEnvironmentVariables": {
          "ESTAT_APP_ID": "$ESTAT_APP_ID",
          "S3_BUCKET": "${S3_BUCKET:-estat-data-lake}",
          "AWS_REGION": "$REGION"
        }
      }
    },
    "AuthenticationConfiguration": {
      "AccessRoleArn": "$ROLE_ARN"
    },
    "AutoDeploymentsEnabled": true
  },
  "InstanceConfiguration": {
    "Cpu": "1 vCPU",
    "Memory": "2 GB"
  },
  "HealthCheckConfiguration": {
    "Protocol": "HTTP",
    "Path": "/health",
    "Interval": 10,
    "Timeout": 5,
    "HealthyThreshold": 1,
    "UnhealthyThreshold": 5
  }
}
EOF

# サービスの作成または更新
if aws apprunner list-services --region $REGION --query "ServiceSummaryList[?ServiceName=='$SERVICE_NAME'].ServiceArn" --output text | grep -q .; then
    echo "  Updating existing service..."
    SERVICE_ARN=$(aws apprunner list-services --region $REGION --query "ServiceSummaryList[?ServiceName=='$SERVICE_NAME'].ServiceArn" --output text)
    
    aws apprunner update-service \
        --service-arn $SERVICE_ARN \
        --source-configuration file:///tmp/apprunner-config.json \
        --region $REGION > /dev/null
else
    echo "  Creating new service..."
    SERVICE_ARN=$(aws apprunner create-service \
        --cli-input-json file:///tmp/apprunner-config.json \
        --region $REGION \
        --query 'Service.ServiceArn' \
        --output text)
fi

echo -e "${GREEN}✓ App Runner service configured${NC}"
echo ""

# サービスの起動を待つ
echo -e "${YELLOW}Waiting for service to be ready...${NC}"
echo "  This may take 3-5 minutes..."

aws apprunner wait service-running \
    --service-arn $SERVICE_ARN \
    --region $REGION 2>/dev/null || true

# サービスURLの取得
SERVICE_URL=$(aws apprunner describe-service \
    --service-arn $SERVICE_ARN \
    --region $REGION \
    --query 'Service.ServiceUrl' \
    --output text)

# クリーンアップ
rm -f /tmp/apprunner-trust-policy.json /tmp/apprunner-config.json

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                  Deployment Complete! 🎉                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}Service Information:${NC}"
echo "  Service Name: $SERVICE_NAME"
echo "  Service ARN: $SERVICE_ARN"
echo "  Region: $REGION"
echo "  Service URL: https://$SERVICE_URL"
echo ""
echo -e "${GREEN}Test Endpoints:${NC}"
echo "  Health Check:"
echo "    curl https://$SERVICE_URL/health"
echo ""
echo "  List Tools:"
echo "    curl https://$SERVICE_URL/tools"
echo ""
echo -e "${GREEN}Kiro Configuration:${NC}"
echo "Add this to ~/.kiro/settings/mcp.json:"
echo ""
cat << EOF
{
  "mcpServers": {
    "estat-aws": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "https://$SERVICE_URL/execute",
        "-H", "Content-Type: application/json",
        "-d", "@-"
      ],
      "disabled": false
    }
  }
}
EOF
echo ""
echo -e "${GREEN}AWS Console:${NC}"
echo "  https://${REGION}.console.aws.amazon.com/apprunner/home?region=${REGION}#/services"
echo ""
echo -e "${YELLOW}Note:${NC} App Runner automatically handles HTTPS, scaling, and health checks!"
echo ""
