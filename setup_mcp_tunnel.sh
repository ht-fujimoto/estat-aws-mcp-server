#!/bin/bash
# SSH tunnel to make remote MCP server accessible via localhost

set -e

echo "Setting up SSH tunnel for MCP server..."
echo ""
echo "This will create a tunnel: localhost:8080 -> ALB:80"
echo ""

# Get ALB DNS name
ALB_DNS="estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com"

# Get one of the ECS task IPs (we'll use AWS SSM Session Manager)
CLUSTER_NAME="estat-mcp-cluster"
SERVICE_NAME="estat-mcp-service"

echo "Getting ECS task information..."
TASK_ARN=$(aws ecs list-tasks \
  --cluster $CLUSTER_NAME \
  --service-name $SERVICE_NAME \
  --region ap-northeast-1 \
  --query 'taskArns[0]' \
  --output text)

if [ -z "$TASK_ARN" ] || [ "$TASK_ARN" = "None" ]; then
  echo "❌ No running tasks found"
  exit 1
fi

echo "Task ARN: $TASK_ARN"
echo ""
echo "Creating port forward using AWS SSM..."
echo "This will map localhost:8080 to the ECS task"
echo ""
echo "Keep this terminal open while using the MCP server"
echo "Press Ctrl+C to stop the tunnel"
echo ""

# Use AWS SSM to create port forward
aws ecs execute-command \
  --cluster $CLUSTER_NAME \
  --task $TASK_ARN \
  --container estat-mcp-container \
  --interactive \
  --command "/bin/sh" \
  --region ap-northeast-1
