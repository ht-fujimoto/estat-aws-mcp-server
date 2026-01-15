#!/bin/bash
# ACM証明書セットアップの続き（証明書検証後）

set -e

AWS_REGION="ap-northeast-1"
DOMAIN_NAME="estat-mcp.snowmole.co.jp"
ALB_ARN="arn:aws:elasticloadbalancing:ap-northeast-1:639135896267:loadbalancer/app/estat-mcp-alb/fcfeae606f00522b"

if [ -z "$CERT_ARN" ]; then
  echo "エラー: CERT_ARN環境変数が設定されていません"
  echo ""
  echo "使用方法:"
  echo "  export CERT_ARN=<証明書ARN>"
  echo "  ./continue_acm_setup.sh"
  exit 1
fi

echo "=========================================="
echo "ACMセットアップ続行"
echo "=========================================="
echo ""
echo "証明書ARN: $CERT_ARN"
echo ""

# 証明書のステータスを確認
echo "証明書のステータスを確認中..."
CERT_STATUS=$(aws acm describe-certificate \
  --certificate-arn $CERT_ARN \
  --region $AWS_REGION \
  --query 'Certificate.Status' \
  --output text)

echo "証明書ステータス: $CERT_STATUS"
echo ""

if [ "$CERT_STATUS" != "ISSUED" ]; then
  echo "⚠️  証明書がまだ発行されていません"
  echo ""
  echo "現在のステータス: $CERT_STATUS"
  echo ""
  echo "DNS検証レコードが正しく設定されているか確認してください"
  echo ""
  echo "検証情報:"
  aws acm describe-certificate \
    --certificate-arn $CERT_ARN \
    --region $AWS_REGION \
    --query 'Certificate.DomainValidationOptions[0]'
  echo ""
  exit 1
fi

echo "✅ 証明書が発行されています"
echo ""

# 既存のHTTPSリスナーを削除
echo "既存のHTTPSリスナーを確認中..."
EXISTING_HTTPS=$(aws elbv2 describe-listeners \
  --load-balancer-arn $ALB_ARN \
  --region $AWS_REGION \
  --query 'Listeners[?Protocol==`HTTPS`].ListenerArn' \
  --output text)

if [ -n "$EXISTING_HTTPS" ]; then
  echo "既存のHTTPSリスナーを削除中..."
  aws elbv2 delete-listener \
    --listener-arn $EXISTING_HTTPS \
    --region $AWS_REGION
  echo "✅ 削除完了"
fi

# ターゲットグループARNを取得
echo ""
echo "ターゲットグループ情報を取得中..."
TG_ARN=$(aws elbv2 describe-target-groups \
  --names estat-mcp-tg \
  --region $AWS_REGION \
  --query 'TargetGroups[0].TargetGroupArn' \
  --output text)

echo "✅ ターゲットグループARN: $TG_ARN"

# HTTPSリスナーを作成
echo ""
echo "HTTPSリスナーを作成中..."
LISTENER_ARN=$(aws elbv2 create-listener \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=$CERT_ARN \
  --default-actions Type=forward,TargetGroupArn=$TG_ARN \
  --region $AWS_REGION \
  --query 'Listeners[0].ListenerArn' \
  --output text)

echo "✅ HTTPSリスナー作成完了"
echo "   リスナーARN: $LISTENER_ARN"

# ALBのDNS名を取得
echo ""
echo "ALB DNS名を取得中..."
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --load-balancer-arns $ALB_ARN \
  --region $AWS_REGION \
  --query 'LoadBalancers[0].DNSName' \
  --output text)

echo "✅ ALB DNS: $ALB_DNS"

# Kiro設定を更新
echo ""
echo "Kiro設定を更新中..."

python3 << EOF
import json

with open('.kiro/settings/mcp.json', 'r') as f:
    config = json.load(f)

config['mcpServers']['estat-aws-remote']['url'] = 'https://$DOMAIN_NAME'

if 'rejectUnauthorized' in config['mcpServers']['estat-aws-remote']:
    del config['mcpServers']['estat-aws-remote']['rejectUnauthorized']

with open('.kiro/settings/mcp.json', 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print('✅ Kiro設定を更新しました')
EOF

echo ""
echo "=========================================="
echo "✅ セットアップ完了！"
echo "=========================================="
echo ""
echo "HTTPS URL: https://$DOMAIN_NAME"
echo ""
echo "次のステップ:"
echo "1. estat-mcp.snowmole.co.jp → $ALB_DNS のCNAMEレコードを追加"
echo "2. DNS伝播を待つ（数分〜10分）"
echo "3. 動作確認: curl https://$DOMAIN_NAME/health"
echo "4. Kiroを再起動"
echo ""
