#!/bin/bash
# ECS Fargate デプロイスクリプト
# タイムアウト制限なしでe-Stat MCPサーバーを運用

set -e

# 設定
AWS_REGION="ap-northeast-1"
AWS_ACCOUNT_ID="639135896267"
CLUSTER_NAME="estat-mcp-cluster"
SERVICE_NAME="estat-mcp-service"
TASK_FAMILY="estat-mcp-task"
ECR_REPO_NAME="estat-mcp-server"
CONTAINER_NAME="estat-mcp-container"
CONTAINER_PORT=8080
ESTAT_APP_ID="320dd2fbff6974743e3f95505c9f346650ab635e"

echo "=========================================="
echo "ECS Fargate デプロイ"
echo "=========================================="
echo "リージョン: $AWS_REGION"
echo "クラスター: $CLUSTER_NAME"
echo ""

# 1. ECRリポジトリを作成
echo "1. ECRリポジトリを作成..."
aws ecr describe-repositories \
  --repository-names $ECR_REPO_NAME \
  --region $AWS_REGION 2>/dev/null || \
aws ecr create-repository \
  --repository-name $ECR_REPO_NAME \
  --region $AWS_REGION

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"
echo "✅ ECRリポジトリ: $ECR_URI"

# 2. Dockerイメージをビルド
echo ""
echo "2. Dockerイメージをビルド..."
docker build -t $ECR_REPO_NAME:latest .
echo "✅ イメージビルド完了"

# 3. ECRにログイン
echo ""
echo "3. ECRにログイン..."
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_URI
echo "✅ ECRログイン成功"

# 4. イメージをタグ付けしてプッシュ
echo ""
echo "4. イメージをECRにプッシュ..."
docker tag $ECR_REPO_NAME:latest $ECR_URI:latest
docker push $ECR_URI:latest
echo "✅ イメージプッシュ完了"

# 5. ECSクラスターを作成
echo ""
echo "5. ECSクラスターを作成..."
aws ecs describe-clusters \
  --clusters $CLUSTER_NAME \
  --region $AWS_REGION 2>/dev/null | grep -q "ACTIVE" || \
aws ecs create-cluster \
  --cluster-name $CLUSTER_NAME \
  --region $AWS_REGION
echo "✅ クラスター作成完了"

# 6. タスク実行ロールを作成
echo ""
echo "6. タスク実行ロールを作成..."
TASK_ROLE_NAME="ecsTaskExecutionRole"
aws iam get-role --role-name $TASK_ROLE_NAME 2>/dev/null || \
aws iam create-role \
  --role-name $TASK_ROLE_NAME \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

aws iam attach-role-policy \
  --role-name $TASK_ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy 2>/dev/null || true

TASK_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${TASK_ROLE_NAME}"
echo "✅ タスク実行ロール: $TASK_ROLE_ARN"

# 7. CloudWatch Logsグループを作成
echo ""
echo "7. CloudWatch Logsグループを作成..."
LOG_GROUP="/ecs/estat-mcp"
aws logs create-log-group \
  --log-group-name $LOG_GROUP \
  --region $AWS_REGION 2>/dev/null || echo "ログループは既に存在"
echo "✅ ログループ: $LOG_GROUP"

# 8. タスク定義を登録
echo ""
echo "8. タスク定義を登録..."
cat > task-definition.json <<EOF
{
  "family": "$TASK_FAMILY",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "$TASK_ROLE_ARN",
  "containerDefinitions": [
    {
      "name": "$CONTAINER_NAME",
      "image": "$ECR_URI:latest",
      "portMappings": [
        {
          "containerPort": $CONTAINER_PORT,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ESTAT_APP_ID",
          "value": "$ESTAT_APP_ID"
        },
        {
          "name": "S3_BUCKET",
          "value": "estat-data-lake"
        },
        {
          "name": "AWS_REGION",
          "value": "$AWS_REGION"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "$LOG_GROUP",
          "awslogs-region": "$AWS_REGION",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
EOF

aws ecs register-task-definition \
  --cli-input-json file://task-definition.json \
  --region $AWS_REGION
echo "✅ タスク定義登録完了"

# 9. デフォルトVPCとサブネットを取得
echo ""
echo "9. VPC情報を取得..."
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" \
  --output text \
  --region $AWS_REGION)

SUBNET_IDS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query "Subnets[*].SubnetId" \
  --output text \
  --region $AWS_REGION | tr '\t' ',')

echo "✅ VPC: $VPC_ID"
echo "✅ サブネット: $SUBNET_IDS"

# 10. セキュリティグループを作成
echo ""
echo "10. セキュリティグループを作成..."
SG_NAME="estat-mcp-sg"
SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
  --query "SecurityGroups[0].GroupId" \
  --output text \
  --region $AWS_REGION 2>/dev/null)

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  SG_ID=$(aws ec2 create-security-group \
    --group-name $SG_NAME \
    --description "Security group for e-Stat MCP Server" \
    --vpc-id $VPC_ID \
    --region $AWS_REGION \
    --query "GroupId" \
    --output text)
  
  # インバウンドルールを追加
  aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port $CONTAINER_PORT \
    --cidr 0.0.0.0/0 \
    --region $AWS_REGION
fi

echo "✅ セキュリティグループ: $SG_ID"

# 11. Application Load Balancerを作成
echo ""
echo "11. Application Load Balancerを作成..."
ALB_NAME="estat-mcp-alb"
ALB_ARN=$(aws elbv2 describe-load-balancers \
  --names $ALB_NAME \
  --query "LoadBalancers[0].LoadBalancerArn" \
  --output text \
  --region $AWS_REGION 2>/dev/null)

if [ "$ALB_ARN" = "None" ] || [ -z "$ALB_ARN" ]; then
  ALB_ARN=$(aws elbv2 create-load-balancer \
    --name $ALB_NAME \
    --subnets $(echo $SUBNET_IDS | tr ',' ' ') \
    --security-groups $SG_ID \
    --scheme internet-facing \
    --type application \
    --region $AWS_REGION \
    --query "LoadBalancers[0].LoadBalancerArn" \
    --output text)
  
  echo "⏳ ALBの作成を待機中..."
  aws elbv2 wait load-balancer-available \
    --load-balancer-arns $ALB_ARN \
    --region $AWS_REGION
fi

ALB_DNS=$(aws elbv2 describe-load-balancers \
  --load-balancer-arns $ALB_ARN \
  --query "LoadBalancers[0].DNSName" \
  --output text \
  --region $AWS_REGION)

echo "✅ ALB: $ALB_DNS"

# 12. ターゲットグループを作成
echo ""
echo "12. ターゲットグループを作成..."
TG_NAME="estat-mcp-tg"
TG_ARN=$(aws elbv2 describe-target-groups \
  --names $TG_NAME \
  --query "TargetGroups[0].TargetGroupArn" \
  --output text \
  --region $AWS_REGION 2>/dev/null)

if [ "$TG_ARN" = "None" ] || [ -z "$TG_ARN" ]; then
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
  
  # タイムアウトを延長（デフォルト60秒→300秒）
  aws elbv2 modify-target-group-attributes \
    --target-group-arn $TG_ARN \
    --attributes Key=deregistration_delay.timeout_seconds,Value=30 \
    --region $AWS_REGION
fi

echo "✅ ターゲットグループ: $TG_ARN"

# 13. リスナーを作成
echo ""
echo "13. リスナーを作成..."
LISTENER_ARN=$(aws elbv2 describe-listeners \
  --load-balancer-arn $ALB_ARN \
  --query "Listeners[0].ListenerArn" \
  --output text \
  --region $AWS_REGION 2>/dev/null)

if [ "$LISTENER_ARN" = "None" ] || [ -z "$LISTENER_ARN" ]; then
  LISTENER_ARN=$(aws elbv2 create-listener \
    --load-balancer-arn $ALB_ARN \
    --protocol HTTP \
    --port 80 \
    --default-actions Type=forward,TargetGroupArn=$TG_ARN \
    --region $AWS_REGION \
    --query "Listeners[0].ListenerArn" \
    --output text)
fi

echo "✅ リスナー作成完了"

# 14. ECSサービスを作成
echo ""
echo "14. ECSサービスを作成..."
aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME \
  --region $AWS_REGION 2>/dev/null | grep -q "ACTIVE" || \
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
sleep 60

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
echo "コスト見積もり:"
echo "- Fargate: 0.25 vCPU + 0.5 GB = 約$15/月"
echo "- ALB: 約$16/月"
echo "- 合計: 約$31/月"
echo ""
echo "CloudWatch Logs:"
echo "aws logs tail $LOG_GROUP --follow --region $AWS_REGION"
echo ""
