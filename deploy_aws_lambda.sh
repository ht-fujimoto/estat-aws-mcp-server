#!/bin/bash
# AWS Lambda + API Gateway デプロイスクリプト

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         AWS Lambda + API Gateway Deployment                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# カラー定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# 設定
FUNCTION_NAME="${AWS_FUNCTION_NAME:-estat-mcp-server}"
REGION="${AWS_REGION:-ap-northeast-1}"
RUNTIME="python3.11"
MEMORY_SIZE=512
TIMEOUT=30
ROLE_NAME="estat-mcp-lambda-role"
API_NAME="estat-mcp-api"

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
    echo "Install from: https://aws.amazon.com/cli/"
    exit 1
fi
echo -e "${GREEN}✓ AWS CLI is installed${NC}"

# AWS認証情報の確認
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}Error: AWS credentials are not configured${NC}"
    echo "Run: aws configure"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✓ AWS credentials configured (Account: $ACCOUNT_ID)${NC}"
echo ""

# Step 1: IAMロールの作成
echo -e "${YELLOW}Step 1/7: Creating IAM role...${NC}"
if ! aws iam get-role --role-name $ROLE_NAME &> /dev/null; then
    cat > /tmp/trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file:///tmp/trust-policy.json \
        --description "Execution role for e-Stat MCP Server Lambda" > /dev/null
    
    # 基本実行ポリシーをアタッチ
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    
    # S3アクセスポリシーをアタッチ
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
    
    # Systems Managerアクセスポリシーをアタッチ
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess
    
    echo -e "${GREEN}✓ IAM role created${NC}"
    echo -e "${YELLOW}  Waiting 10 seconds for role to propagate...${NC}"
    sleep 10
else
    echo -e "${GREEN}✓ IAM role already exists${NC}"
fi

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
echo ""

# Step 2: Parameter Storeに設定を保存
echo -e "${YELLOW}Step 2/7: Storing API key in Parameter Store...${NC}"
aws ssm put-parameter \
    --name "/estat-mcp/api-key" \
    --value "$ESTAT_APP_ID" \
    --type "SecureString" \
    --overwrite \
    --region $REGION > /dev/null 2>&1 || true
echo -e "${GREEN}✓ API key stored securely${NC}"
echo ""

# Step 3: Lambda Layerの作成
echo -e "${YELLOW}Step 3/7: Creating Lambda Layer with dependencies...${NC}"
rm -rf lambda_layer layer.zip
mkdir -p lambda_layer/python

echo "  Installing dependencies..."
pip3 install -r requirements-lambda.txt -t lambda_layer/python/ --quiet --no-cache-dir

cd lambda_layer
zip -r ../layer.zip python > /dev/null 2>&1
cd ..

echo "  Publishing layer..."
LAYER_VERSION=$(aws lambda publish-layer-version \
    --layer-name estat-mcp-dependencies \
    --description "Dependencies for e-Stat MCP Server" \
    --zip-file fileb://layer.zip \
    --compatible-runtimes $RUNTIME \
    --region $REGION \
    --query 'Version' \
    --output text)

echo -e "${GREEN}✓ Layer created (version: $LAYER_VERSION)${NC}"
echo ""

# Step 4: Lambda関数パッケージの作成
echo -e "${YELLOW}Step 4/7: Creating Lambda function package...${NC}"
rm -rf lambda_package function.zip
mkdir -p lambda_package

cp lambda_handler.py lambda_package/
if [ -d "estat_mcp_server" ]; then
    cp -r estat_mcp_server lambda_package/
fi

cd lambda_package
zip -r ../function.zip . > /dev/null 2>&1
cd ..

PACKAGE_SIZE=$(du -h function.zip | cut -f1)
echo -e "${GREEN}✓ Function package created ($PACKAGE_SIZE)${NC}"
echo ""

# Step 5: Lambda関数の作成または更新
echo -e "${YELLOW}Step 5/7: Deploying Lambda function...${NC}"
if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION &> /dev/null; then
    echo "  Updating existing function..."
    
    # コードの更新
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://function.zip \
        --region $REGION > /dev/null
    
    # 設定の更新
    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --runtime $RUNTIME \
        --handler lambda_handler.lambda_handler \
        --memory-size $MEMORY_SIZE \
        --timeout $TIMEOUT \
        --layers "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:layer:estat-mcp-dependencies:${LAYER_VERSION}" \
        --environment "Variables={ESTAT_REGION=$REGION,S3_BUCKET=${S3_BUCKET:-estat-data-lake}}" \
        --region $REGION > /dev/null
    
    echo -e "${GREEN}✓ Lambda function updated${NC}"
else
    echo "  Creating new function..."
    
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime $RUNTIME \
        --role $ROLE_ARN \
        --handler lambda_handler.lambda_handler \
        --zip-file fileb://function.zip \
        --memory-size $MEMORY_SIZE \
        --timeout $TIMEOUT \
        --layers "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:layer:estat-mcp-dependencies:${LAYER_VERSION}" \
        --environment "Variables={ESTAT_REGION=$REGION,S3_BUCKET=${S3_BUCKET:-estat-data-lake}}" \
        --description "e-Stat MCP Server" \
        --region $REGION > /dev/null
    
    echo -e "${GREEN}✓ Lambda function created${NC}"
fi
echo ""

# Step 6: API Gatewayの作成
echo -e "${YELLOW}Step 6/7: Configuring API Gateway...${NC}"

# 既存のAPIを検索
API_ID=$(aws apigateway get-rest-apis \
    --region $REGION \
    --query "items[?name=='$API_NAME'].id" \
    --output text 2>/dev/null)

if [ -z "$API_ID" ]; then
    echo "  Creating new REST API..."
    API_ID=$(aws apigateway create-rest-api \
        --name "$API_NAME" \
        --description "e-Stat MCP Server API" \
        --endpoint-configuration types=REGIONAL \
        --region $REGION \
        --query 'id' \
        --output text)
    echo "  API ID: $API_ID"
else
    echo "  Using existing API: $API_ID"
fi

# ルートリソースIDの取得
ROOT_ID=$(aws apigateway get-resources \
    --rest-api-id $API_ID \
    --region $REGION \
    --query 'items[?path==`/`].id' \
    --output text)

# プロキシリソースの作成または取得
RESOURCE_ID=$(aws apigateway get-resources \
    --rest-api-id $API_ID \
    --region $REGION \
    --query "items[?pathPart=='{proxy+}'].id" \
    --output text 2>/dev/null)

if [ -z "$RESOURCE_ID" ]; then
    RESOURCE_ID=$(aws apigateway create-resource \
        --rest-api-id $API_ID \
        --parent-id $ROOT_ID \
        --path-part '{proxy+}' \
        --region $REGION \
        --query 'id' \
        --output text)
fi

# ANYメソッドの作成
aws apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $RESOURCE_ID \
    --http-method ANY \
    --authorization-type NONE \
    --region $REGION > /dev/null 2>&1 || true

# Lambda統合の設定
LAMBDA_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}"

aws apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $RESOURCE_ID \
    --http-method ANY \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations" \
    --region $REGION > /dev/null 2>&1 || true

# Lambda実行権限の付与
aws lambda add-permission \
    --function-name $FUNCTION_NAME \
    --statement-id apigateway-invoke-$(date +%s) \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*/*" \
    --region $REGION > /dev/null 2>&1 || true

echo -e "${GREEN}✓ API Gateway configured${NC}"
echo ""

# Step 7: デプロイメントの作成
echo -e "${YELLOW}Step 7/7: Deploying API...${NC}"
aws apigateway create-deployment \
    --rest-api-id $API_ID \
    --stage-name prod \
    --stage-description "Production stage" \
    --description "Deployment $(date +%Y-%m-%d\ %H:%M:%S)" \
    --region $REGION > /dev/null

echo -e "${GREEN}✓ API deployed to production${NC}"
echo ""

# クリーンアップ
rm -rf lambda_layer lambda_package layer.zip function.zip /tmp/trust-policy.json

# デプロイ完了
API_URL="https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                  Deployment Complete! 🎉                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}Service Information:${NC}"
echo "  Function Name: $FUNCTION_NAME"
echo "  API ID: $API_ID"
echo "  Region: $REGION"
echo "  API URL: $API_URL"
echo ""
echo -e "${GREEN}Test Endpoints:${NC}"
echo "  Health Check:"
echo "    curl $API_URL/health"
echo ""
echo "  List Tools:"
echo "    curl $API_URL/tools"
echo ""
echo "  Execute Tool:"
echo "    curl -X POST $API_URL/execute \\"
echo "      -H 'Content-Type: application/json' \\"
echo "      -d '{\"tool_name\":\"search_estat_data\",\"arguments\":{\"query\":\"人口\"}}'"
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
        "$API_URL/execute",
        "-H", "Content-Type: application/json",
        "-d", "@-"
      ],
      "disabled": false
    }
  }
}
EOF
echo ""
echo -e "${GREEN}AWS Console Links:${NC}"
echo "  Lambda: https://${REGION}.console.aws.amazon.com/lambda/home?region=${REGION}#/functions/${FUNCTION_NAME}"
echo "  API Gateway: https://${REGION}.console.aws.amazon.com/apigateway/home?region=${REGION}#/apis/${API_ID}"
echo "  CloudWatch Logs: https://${REGION}.console.aws.amazon.com/cloudwatch/home?region=${REGION}#logsV2:log-groups/log-group/\$252Faws\$252Flambda\$252F${FUNCTION_NAME}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Test the health endpoint"
echo "  2. Configure Kiro with the provided configuration"
echo "  3. Monitor logs in CloudWatch"
echo "  4. (Optional) Set up custom domain with Route 53"
echo ""
