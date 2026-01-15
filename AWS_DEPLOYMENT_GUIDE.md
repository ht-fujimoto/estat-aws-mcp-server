# AWS完全デプロイメントガイド

MCPサーバーをAWSで運用するための完全ガイド。複数のAWSサービスを使った実装方法を説明します。

## 目次
1. [AWSアーキテクチャ比較](#1-awsアーキテクチャ比較)
2. [Lambda + API Gateway（推奨）](#2-lambda--api-gateway推奨)
3. [ECS Fargate](#3-ecs-fargate)
4. [App Runner](#4-app-runner)
5. [EC2 + ALB](#5-ec2--alb)
6. [コスト最適化](#6-コスト最適化)
7. [セキュリティ設定](#7-セキュリティ設定)
8. [モニタリング](#8-モニタリング)

---

## 1. AWSアーキテクチャ比較

### 推奨アーキテクチャ

| サービス | 難易度 | 月額コスト | スケーラビリティ | 推奨用途 |
|---------|--------|-----------|----------------|----------|
| **Lambda + API Gateway** | ⭐⭐ | $0〜$10 | 自動 | 小〜中規模（推奨） |
| **App Runner** | ⭐ | $5〜$20 | 自動 | 最も簡単 |
| **ECS Fargate** | ⭐⭐⭐ | $15〜$50 | 自動 | 本格運用 |
| **EC2 + ALB** | ⭐⭐⭐ | $20〜$100 | 手動 | フルコントロール |

### アーキテクチャ図

```
┌─────────────────────────────────────────────────────────────┐
│                    クライアント（Kiro/Cline）                  │
└─────────────────────────────────────────────────────────────┘
                              │ HTTPS
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              CloudFront（CDN・オプション）                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              API Gateway / ALB                               │
└─────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
         ┌──────────┐  ┌──────────┐  ┌──────────┐
         │ Lambda   │  │ Fargate  │  │   EC2    │
         │ Function │  │ Container│  │ Instance │
         └──────────┘  └──────────┘  └──────────┘
                │             │             │
                └─────────────┼─────────────┘
                              ▼
                    ┌──────────────────┐
                    │   e-Stat API     │
                    │   AWS S3         │
                    │   DynamoDB       │
                    └──────────────────┘
```

---

## 2. Lambda + API Gateway（推奨）

### メリット
- ✅ サーバーレスで管理不要
- ✅ 従量課金（使った分だけ）
- ✅ 自動スケーリング
- ✅ 無料枠: 月100万リクエスト
- ✅ コールドスタート対策可能

### コスト試算
- **小規模（月1万リクエスト）:** 無料
- **中規模（月100万リクエスト）:** 無料
- **大規模（月1000万リクエスト）:** 約$2/月

### 2.1 Lambda関数の実装

#### lambda_handler.py
```python
import json
import os
import sys
import boto3
from datetime import datetime

# MCPサーバーのインポート
sys.path.append('/opt/python')  # Lambda Layer
from estat_mcp_server.server import MCPServer

# グローバル変数（コールドスタート対策）
mcp_server = None
ssm_client = boto3.client('ssm', region_name=os.environ.get('AWS_REGION', 'ap-northeast-1'))

def get_parameter(name, decrypt=True):
    """Systems Manager Parameter Storeから値を取得"""
    try:
        response = ssm_client.get_parameter(Name=name, WithDecryption=decrypt)
        return response['Parameter']['Value']
    except Exception as e:
        print(f"Error getting parameter {name}: {e}")
        return None

def init_mcp_server():
    """MCPサーバーを初期化（初回のみ）"""
    global mcp_server
    if mcp_server is None:
        # Parameter Storeから設定を取得
        estat_app_id = get_parameter('/estat-mcp/api-key')
        if not estat_app_id:
            estat_app_id = os.environ.get('ESTAT_APP_ID')
        
        os.environ['ESTAT_APP_ID'] = estat_app_id
        mcp_server = MCPServer()
        print(f"[{datetime.now()}] MCP Server initialized")

def lambda_handler(event, context):
    """
    Lambda関数のエントリーポイント
    """
    print(f"[{datetime.now()}] Request received: {event.get('path')}")
    
    # MCPサーバーの初期化
    init_mcp_server()
    
    try:
        # HTTPメソッドとパスを取得
        http_method = event.get('httpMethod', 'POST')
        path = event.get('path', '/')
        
        # リクエストボディを取得
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body) if body else {}
        
        # ヘッダーからAPI認証（オプション）
        headers = event.get('headers', {})
        api_key = headers.get('X-API-Key') or headers.get('x-api-key')
        expected_key = os.environ.get('MCP_API_KEY')
        
        if expected_key and api_key != expected_key:
            return create_response(401, {'error': 'Unauthorized'})
        
        # ルーティング
        if path == '/health' or path == '/':
            response_body = {
                'status': 'healthy',
                'service': 'e-Stat MCP Server',
                'version': '1.0.0',
                'timestamp': datetime.now().isoformat()
            }
        
        elif path == '/tools':
            tools = mcp_server.get_tools()
            response_body = {'success': True, 'tools': tools}
        
        elif path == '/execute':
            tool_name = body.get('tool_name')
            arguments = body.get('arguments', {})
            
            if not tool_name:
                return create_response(400, {'error': 'tool_name is required'})
            
            result = mcp_server.execute_tool(tool_name, arguments)
            response_body = {'success': True, 'result': result}
        
        else:
            return create_response(404, {'error': 'Not found'})
        
        return create_response(200, response_body)
    
    except Exception as e:
        print(f"[{datetime.now()}] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        })

def create_response(status_code, body):
    """レスポンスを作成"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-API-Key'
        },
        'body': json.dumps(body, ensure_ascii=False)
    }
```

### 2.2 デプロイスクリプト

#### deploy_lambda.sh
```bash
#!/bin/bash
set -e

echo "=== AWS Lambda Deployment ==="
echo ""

# カラー定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 設定
FUNCTION_NAME="estat-mcp-server"
REGION="ap-northeast-1"
RUNTIME="python3.11"
MEMORY_SIZE=512
TIMEOUT=30
ROLE_NAME="estat-mcp-lambda-role"

# 環境変数の確認
if [ -z "$ESTAT_APP_ID" ]; then
    echo -e "${RED}Error: ESTAT_APP_ID is not set${NC}"
    exit 1
fi

# AWS CLIの確認
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    exit 1
fi

# アカウントIDの取得
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "AWS Account ID: $ACCOUNT_ID"
echo ""

# Step 1: IAMロールの作成
echo -e "${YELLOW}Step 1: Creating IAM role...${NC}"
if ! aws iam get-role --role-name $ROLE_NAME &> /dev/null; then
    cat > trust-policy.json << EOF
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
        --assume-role-policy-document file://trust-policy.json
    
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
    echo "Waiting 10 seconds for role to propagate..."
    sleep 10
else
    echo -e "${GREEN}✓ IAM role already exists${NC}"
fi

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
echo ""

# Step 2: Parameter Storeに設定を保存
echo -e "${YELLOW}Step 2: Storing configuration in Parameter Store...${NC}"
aws ssm put-parameter \
    --name "/estat-mcp/api-key" \
    --value "$ESTAT_APP_ID" \
    --type "SecureString" \
    --overwrite \
    --region $REGION || true
echo -e "${GREEN}✓ Configuration stored${NC}"
echo ""

# Step 3: Lambda Layerの作成
echo -e "${YELLOW}Step 3: Creating Lambda Layer...${NC}"
mkdir -p lambda_layer/python
pip install -r requirements.txt -t lambda_layer/python/ --quiet
cd lambda_layer
zip -r ../layer.zip python > /dev/null
cd ..

LAYER_VERSION=$(aws lambda publish-layer-version \
    --layer-name estat-mcp-dependencies \
    --zip-file fileb://layer.zip \
    --compatible-runtimes $RUNTIME \
    --region $REGION \
    --query 'Version' \
    --output text)

echo -e "${GREEN}✓ Layer created (version: $LAYER_VERSION)${NC}"
echo ""

# Step 4: Lambda関数パッケージの作成
echo -e "${YELLOW}Step 4: Creating Lambda function package...${NC}"
mkdir -p lambda_package
cp lambda_handler.py lambda_package/
cp -r estat_mcp_server lambda_package/ 2>/dev/null || true

cd lambda_package
zip -r ../function.zip . > /dev/null
cd ..

echo -e "${GREEN}✓ Function package created${NC}"
echo ""

# Step 5: Lambda関数の作成または更新
echo -e "${YELLOW}Step 5: Deploying Lambda function...${NC}"
if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION &> /dev/null; then
    # 更新
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://function.zip \
        --region $REGION > /dev/null
    
    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --runtime $RUNTIME \
        --handler lambda_handler.lambda_handler \
        --memory-size $MEMORY_SIZE \
        --timeout $TIMEOUT \
        --layers "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:layer:estat-mcp-dependencies:${LAYER_VERSION}" \
        --environment "Variables={AWS_REGION=$REGION,S3_BUCKET=${S3_BUCKET:-estat-data-lake}}" \
        --region $REGION > /dev/null
    
    echo -e "${GREEN}✓ Lambda function updated${NC}"
else
    # 新規作成
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime $RUNTIME \
        --role $ROLE_ARN \
        --handler lambda_handler.lambda_handler \
        --zip-file fileb://function.zip \
        --memory-size $MEMORY_SIZE \
        --timeout $TIMEOUT \
        --layers "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:layer:estat-mcp-dependencies:${LAYER_VERSION}" \
        --environment "Variables={AWS_REGION=$REGION,S3_BUCKET=${S3_BUCKET:-estat-data-lake}}" \
        --region $REGION > /dev/null
    
    echo -e "${GREEN}✓ Lambda function created${NC}"
fi
echo ""

# Step 6: API Gatewayの作成
echo -e "${YELLOW}Step 6: Creating API Gateway...${NC}"

# REST APIの作成
API_ID=$(aws apigateway create-rest-api \
    --name "estat-mcp-api" \
    --description "e-Stat MCP Server API" \
    --region $REGION \
    --query 'id' \
    --output text 2>/dev/null || \
    aws apigateway get-rest-apis \
    --region $REGION \
    --query "items[?name=='estat-mcp-api'].id" \
    --output text)

echo "API ID: $API_ID"

# ルートリソースIDの取得
ROOT_ID=$(aws apigateway get-resources \
    --rest-api-id $API_ID \
    --region $REGION \
    --query 'items[?path==`/`].id' \
    --output text)

# プロキシリソースの作成
RESOURCE_ID=$(aws apigateway create-resource \
    --rest-api-id $API_ID \
    --parent-id $ROOT_ID \
    --path-part '{proxy+}' \
    --region $REGION \
    --query 'id' \
    --output text 2>/dev/null || \
    aws apigateway get-resources \
    --rest-api-id $API_ID \
    --region $REGION \
    --query "items[?pathPart=='{proxy+}'].id" \
    --output text)

# ANYメソッドの作成
aws apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $RESOURCE_ID \
    --http-method ANY \
    --authorization-type NONE \
    --region $REGION 2>/dev/null || true

# Lambda統合の設定
LAMBDA_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}"

aws apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $RESOURCE_ID \
    --http-method ANY \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations" \
    --region $REGION 2>/dev/null || true

# Lambda実行権限の付与
aws lambda add-permission \
    --function-name $FUNCTION_NAME \
    --statement-id apigateway-invoke \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*/*" \
    --region $REGION 2>/dev/null || true

# デプロイメントの作成
aws apigateway create-deployment \
    --rest-api-id $API_ID \
    --stage-name prod \
    --region $REGION > /dev/null

echo -e "${GREEN}✓ API Gateway configured${NC}"
echo ""

# クリーンアップ
rm -rf lambda_layer lambda_package layer.zip function.zip trust-policy.json

# デプロイ完了
API_URL="https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod"

echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Function Name: $FUNCTION_NAME"
echo "API URL: $API_URL"
echo "Region: $REGION"
echo ""
echo "Test endpoints:"
echo "  Health: curl $API_URL/health"
echo "  Tools:  curl $API_URL/tools"
echo ""
echo "Kiro configuration:"
echo '{'
echo '  "mcpServers": {'
echo '    "estat-aws": {'
echo '      "command": "curl",'
echo '      "args": ['
echo '        "-X", "POST",'
echo "        \"$API_URL/execute\","
echo '        "-H", "Content-Type: application/json",'
echo '        "-d", "@-"'
echo '      ]'
echo '    }'
echo '  }'
echo '}'
```

---

## 3. ECS Fargate

本格的な運用に適したコンテナベースのデプロイ。

### デプロイスクリプト

#### deploy_ecs.sh
```bash
#!/bin/bash
set -e

echo "=== AWS ECS Fargate Deployment ==="
# 詳細は次のセクションで
```

---

## 4. App Runner

最も簡単なAWSデプロイ方法。

### デプロイスクリプト

#### deploy_apprunner.sh
```bash
#!/bin/bash
set -e

echo "=== AWS App Runner Deployment ==="
# Dockerfileから自動デプロイ
```

---

続きは次のメッセージで作成します...
