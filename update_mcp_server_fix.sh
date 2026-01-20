#!/bin/bash
# MCPサーバーの修正をECSにデプロイ

set -e

echo "=========================================="
echo "MCP Server Fix Deployment"
echo "=========================================="
echo ""

# 変数設定
AWS_REGION="ap-northeast-1"
ECR_REPO="639135896267.dkr.ecr.ap-northeast-1.amazonaws.com/estat-mcp-server"
IMAGE_TAG="v2.2.1-fix"
CLUSTER_NAME="estat-mcp-cluster"
SERVICE_NAME="estat-mcp-service"

echo "Step 1: Building Docker image..."
docker build -t estat-mcp-server:${IMAGE_TAG} -f estat-aws-package/Dockerfile estat-aws-package/

echo ""
echo "Step 2: Tagging image..."
docker tag estat-mcp-server:${IMAGE_TAG} ${ECR_REPO}:${IMAGE_TAG}
docker tag estat-mcp-server:${IMAGE_TAG} ${ECR_REPO}:latest

echo ""
echo "Step 3: Logging in to ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REPO}

echo ""
echo "Step 4: Pushing to ECR..."
docker push ${ECR_REPO}:${IMAGE_TAG}
docker push ${ECR_REPO}:latest

echo ""
echo "Step 5: Updating ECS service..."
aws ecs update-service \
    --cluster ${CLUSTER_NAME} \
    --service ${SERVICE_NAME} \
    --force-new-deployment \
    --region ${AWS_REGION}

echo ""
echo "=========================================="
echo "✓ Deployment initiated!"
echo "=========================================="
echo ""
echo "Monitor deployment:"
echo "  aws ecs describe-services --cluster ${CLUSTER_NAME} --services ${SERVICE_NAME} --region ${AWS_REGION}"
echo ""
echo "Check logs:"
echo "  aws logs tail /ecs/estat-mcp-server --follow --region ${AWS_REGION}"
echo ""
