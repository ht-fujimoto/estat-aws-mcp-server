#!/bin/bash
# ACM証明書のステータスを確認

CERT_ARN="arn:aws:acm:ap-northeast-1:639135896267:certificate/01bd1f7b-7b80-447d-81e2-e86e79974055"
AWS_REGION="ap-northeast-1"

echo "=========================================="
echo "ACM証明書ステータス確認"
echo "=========================================="
echo ""
echo "証明書ARN: $CERT_ARN"
echo ""

while true; do
  STATUS=$(aws acm describe-certificate \
    --certificate-arn $CERT_ARN \
    --region $AWS_REGION \
    --query 'Certificate.Status' \
    --output text)
  
  TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
  
  echo "[$TIMESTAMP] ステータス: $STATUS"
  
  if [ "$STATUS" = "ISSUED" ]; then
    echo ""
    echo "=========================================="
    echo "✅ 証明書が発行されました！"
    echo "=========================================="
    echo ""
    echo "次のステップ:"
    echo "  export CERT_ARN=$CERT_ARN"
    echo "  ./continue_acm_setup.sh"
    echo ""
    break
  elif [ "$STATUS" = "FAILED" ]; then
    echo ""
    echo "❌ 証明書の発行に失敗しました"
    echo ""
    echo "詳細:"
    aws acm describe-certificate \
      --certificate-arn $CERT_ARN \
      --region $AWS_REGION \
      --query 'Certificate.DomainValidationOptions[0]'
    echo ""
    break
  fi
  
  echo "   ⏳ 30秒後に再確認..."
  sleep 30
done
