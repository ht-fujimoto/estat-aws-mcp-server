#!/bin/bash
# Athenaワークグループのセットアップスクリプト
# estat-data-lakeバケットを出力先として使用するワークグループを作成

set -e

AWS_REGION="ap-northeast-1"
S3_BUCKET="estat-data-lake"
WORKGROUP_NAME="estat-mcp-workgroup"

echo "=========================================="
echo "Athenaワークグループのセットアップ"
echo "=========================================="
echo "リージョン: $AWS_REGION"
echo "S3バケット: $S3_BUCKET"
echo "ワークグループ: $WORKGROUP_NAME"
echo ""

# 1. S3バケットにAthena結果ディレクトリを作成
echo "1. S3バケットにAthena結果ディレクトリを作成..."
aws s3api put-object \
  --bucket $S3_BUCKET \
  --key athena-results/.keep \
  --region $AWS_REGION
echo "✅ athena-resultsディレクトリ作成完了"

# 2. 既存のワークグループを確認
echo ""
echo "2. 既存のワークグループを確認..."
EXISTING_WG=$(aws athena get-work-group \
  --work-group $WORKGROUP_NAME \
  --region $AWS_REGION 2>/dev/null || echo "")

if [ -n "$EXISTING_WG" ]; then
  echo "⚠️  ワークグループ '$WORKGROUP_NAME' は既に存在します"
  echo "既存のワークグループを削除して再作成しますか? (y/N)"
  read -r response
  if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "既存のワークグループを削除中..."
    aws athena delete-work-group \
      --work-group $WORKGROUP_NAME \
      --recursive-delete-option \
      --region $AWS_REGION
    echo "✅ 削除完了"
    sleep 2
  else
    echo "既存のワークグループを使用します"
    exit 0
  fi
fi

# 3. 新しいワークグループを作成
echo ""
echo "3. 新しいワークグループを作成..."
aws athena create-work-group \
  --name $WORKGROUP_NAME \
  --configuration "ResultConfiguration={OutputLocation=s3://$S3_BUCKET/athena-results/},EnforceWorkGroupConfiguration=true" \
  --description "e-Stat MCP Server用のAthenaワークグループ" \
  --region $AWS_REGION

echo "✅ ワークグループ作成完了"

# 4. ワークグループの設定を確認
echo ""
echo "4. ワークグループの設定を確認..."
aws athena get-work-group \
  --work-group $WORKGROUP_NAME \
  --region $AWS_REGION \
  --query 'WorkGroup.Configuration.ResultConfiguration.OutputLocation' \
  --output text

echo ""
echo "=========================================="
echo "✅ セットアップ完了！"
echo "=========================================="
echo ""
echo "ワークグループ名: $WORKGROUP_NAME"
echo "出力場所: s3://$S3_BUCKET/athena-results/"
echo ""
echo "次のステップ:"
echo "1. mcp_servers/estat_aws/server.pyを更新してワークグループを使用"
echo "2. ローカルでテスト実行"
echo "3. ECSサービスを更新"
echo ""
