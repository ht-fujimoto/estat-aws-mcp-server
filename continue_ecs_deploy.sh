#!/bin/bash
# ECS Fargate デプロイの続き

set -e

AWS_REGION="ap-northeast-1"
AWS_ACCOUNT_ID="639135896267"
CLUSTER_NAME="estat-mcp-cluster"
SERVICE_NAME="estat-mcp-service"
TASK_FAMILY="estat-mcp-task"
CONTAINER_NAME="estat-mcp-container"
CONTAINER_PORT=8080
VPC_ID="vpc-032e06c223520bd44"
SUBNET_IDS="subnet-0d041dcb0f945d721,subnet-03ba7c7611560097a,subnet-030bed1711793dc2d"
SG_ID="sg-03ae5df18c9a33c8b"
ALB_NAME="estat-mcp-alb"
TG_NAME="estat-mcp-tg"

echo "=========================================="
echo "ECS Fargate デプロイ（続き）"
echo "=========================================="

# 11. Application Load Balancerを作成
echo ""
echo "11. Application Load Balancerを作成..."
ALB_ARN=$(aws elbv2 create-load-balancer \
  --name $ALB_NAME \
  --subnets subnet-0d041dcb0f945d721 subnet-03ba7c7611560097a subnet-030bed1711793dc2d \
  --security-groups $SG_ID \
  --scheme internet-facing \
  --type application \
  --region $AWS_REGION \
  --query "LoadBalancers[0].LoadBalancerArn" \
  --output text)

echo "✅ ALB ARN: $ALB_ARN"
echo "⏳ ALBの作成を待機中..."
aws elbv2 wait load-balancer-available --load-balancer-arns $ALB_ARN --region $AWS_REGION

ALB_DNS=$(aws elbv2 describe-load-balancers \
  --load-balancer-arns $ALB_ARN \
  --query "LoadBalancers[0].DNSName" \
  --output text \
  --region $AWS_REGION)

echo "✅ ALB DNS: $ALB_DNS"

# 12. ターゲットグループを作成
echo ""
echo "12. ターゲットグループを作成..."
TG_ARN=$(aws elbv2 create-target-group \
  --name $TG_NAME \
  --protocol HTTP \
  --port $CONTAINER_PORT \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-path /health \
  --health-check-interval-seconds 30 \
  --health-check-timeout-seconds 10 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3 \
  --region $AWS_REGION \
  --query "TargetGroups[0].TargetGroupArn" \
  --output text)

echo "✅ ターゲットグループ: $TG_ARN"

# タイムアウトを延長
aws elbv2 modify-target-group-attributes \
  --target-group-arn $TG_ARN \
  --attributes Key=deregistration_delay.timeout_seconds,Value=30 \
  --region $AWS_REGION

# 13. リスナーを作成
echo ""
echo "13. リスナーを作成..."
LISTENER_ARN=$(aws elbv2 create-listener \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=$TG_ARN \
  --region $AWS_REGION \
  --query "Listeners[0].ListenerArn" \
  --output text)

echo "✅ リスナー作成完了"

# 14. ECSサービスを作成
echo ""
echo "14. ECSサービスを作成..."
aws ecs create-service \
  --cluster $CLUSTER_NAME \
  --service-name $SERVICE_NAME \
  --task-definition $TASK_FAMILY \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=$TG_ARN,containerName=$CONTAINER_NAME,containerPort=$CONTAINER_PORT" \
  --region $AWS_REGION

echo "✅ ECSサービス作成完了"

# 15. サービスの起動を待機
echo ""
echo "15. サービスの起動を待機中..."
echo "⏳ これには数分かかる場合があります..."
sleep 90

# 16. 動作確認
echo ""
echo "=========================================="
echo "動作確認"
echo "=========================================="

API_URL="http://$ALB_DNS"
echo ""
echo "API URL: $API_URL"
echo ""

echo "ヘルスチェック..."
curl -s "$API_URL/health" | jq '.' || echo "まだ起動中です。数分後に再試行してください。"

echo ""
echo "=========================================="
echo "✅ デプロイ完了！"
echo "=========================================="
echo ""
echo "API URL: $API_URL"
echo ""
echo "mcp_aws_wrapper.pyを更新してください："
echo "API_URL = \"$API_URL\""
echo ""
echo "タイムアウト: 制限なし（ALBタイムアウト: 300秒設定可能）"
echo ""
echo "CloudWatch Logs:"
echo "aws logs tail /ecs/estat-mcp --follow --region $AWS_REGION"
echo ""
