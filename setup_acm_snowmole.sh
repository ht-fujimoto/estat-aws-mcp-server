#!/bin/bash
# snowmole.co.jp ドメインでACM証明書を取得

set -e

AWS_REGION="ap-northeast-1"
DOMAIN_NAME="estat-mcp.snowmole.co.jp"
ALB_ARN="arn:aws:elasticloadbalancing:ap-northeast-1:639135896267:loadbalancer/app/estat-mcp-alb/fcfeae606f00522b"

echo "=========================================="
echo "ACM証明書取得（snowmole.co.jp）"
echo "=========================================="
echo ""
echo "ドメイン: $DOMAIN_NAME"
echo ""

# ステップ1: ACM証明書をリクエスト
echo "ステップ1: ACM証明書をリクエスト中..."
CERT_ARN=$(aws acm request-certificate \
  --domain-name $DOMAIN_NAME \
  --validation-method DNS \
  --region $AWS_REGION \
  --query 'CertificateArn' \
  --output text)

echo "✅ 証明書リクエスト完了"
echo "   証明書ARN: $CERT_ARN"
echo ""

# ステップ2: DNS検証レコードを取得
echo "ステップ2: DNS検証レコードを取得中..."
echo "⏳ 証明書情報を取得（5秒待機）..."
sleep 5

VALIDATION_INFO=$(aws acm describe-certificate \
  --certificate-arn $CERT_ARN \
  --region $AWS_REGION \
  --query 'Certificate.DomainValidationOptions[0].ResourceRecord' \
  --output json)

echo "✅ DNS検証レコード取得完了"
echo ""

RECORD_NAME=$(echo "$VALIDATION_INFO" | python3 -c "import sys, json; print(json.load(sys.stdin)['Name'])")
RECORD_VALUE=$(echo "$VALIDATION_INFO" | python3 -c "import sys, json; print(json.load(sys.stdin)['Value'])")

echo "=========================================="
echo "⚠️  重要: DNSレコードを追加してください"
echo "=========================================="
echo ""
echo "snowmole.co.jp のDNS管理画面で以下のレコードを追加:"
echo ""
echo "  タイプ: CNAME"
echo "  名前: $RECORD_NAME"
echo "  値: $RECORD_VALUE"
echo "  TTL: 300（または任意）"
echo ""
echo "例（お名前.comの場合）:"
echo "  ホスト名: $(echo $RECORD_NAME | sed 's/.snowmole.co.jp.$//')"
echo "  TYPE: CNAME"
echo "  VALUE: $RECORD_VALUE"
echo ""
echo "例（Route 53の場合）:"
echo "  レコード名: $RECORD_NAME"
echo "  レコードタイプ: CNAME"
echo "  値: $RECORD_VALUE"
echo ""

read -p "DNSレコードを追加しましたか？ (y/n): " dns_added

if [ "$dns_added" != "y" ]; then
  echo ""
  echo "DNSレコードを追加してから、以下のコマンドで続きを実行してください:"
  echo ""
  echo "  export CERT_ARN=$CERT_ARN"
  echo "  ./continue_acm_setup.sh"
  echo ""
  exit 0
fi

# ステップ3: 証明書の検証を待機
echo ""
echo "ステップ3: 証明書の検証を待機中..."
echo "⏳ DNS伝播と検証には数分〜30分かかる場合があります..."
echo ""

# タイムアウト付きで待機（最大30分）
timeout 1800 aws acm wait certificate-validated \
  --certificate-arn $CERT_ARN \
  --region $AWS_REGION || {
  echo ""
  echo "⚠️  タイムアウトしました"
  echo "DNS伝播に時間がかかっている可能性があります"
  echo ""
  echo "証明書のステータスを確認:"
  echo "  aws acm describe-certificate --certificate-arn $CERT_ARN --region $AWS_REGION"
  echo ""
  echo "検証が完了したら、以下のコマンドで続きを実行:"
  echo "  export CERT_ARN=$CERT_ARN"
  echo "  ./continue_acm_setup.sh"
  echo ""
  exit 1
}

echo "✅ 証明書が検証されました！"
echo ""

# ステップ4: 既存のHTTPSリスナーを削除
echo "ステップ4: 既存のHTTPSリスナーを確認中..."
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
  echo "✅ 既存のリスナーを削除しました"
fi

# ステップ5: ターゲットグループARNを取得
echo ""
echo "ステップ5: ターゲットグループ情報を取得中..."
TG_ARN=$(aws elbv2 describe-target-groups \
  --names estat-mcp-tg \
  --region $AWS_REGION \
  --query 'TargetGroups[0].TargetGroupArn' \
  --output text)

echo "✅ ターゲットグループARN: $TG_ARN"

# ステップ6: HTTPSリスナーを作成
echo ""
echo "ステップ6: HTTPSリスナーを作成中..."
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

# ステップ7: ALBのDNS名を取得
echo ""
echo "ステップ7: ALB DNS名を取得中..."
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --load-balancer-arns $ALB_ARN \
  --region $AWS_REGION \
  --query 'LoadBalancers[0].DNSName' \
  --output text)

echo "✅ ALB DNS: $ALB_DNS"

# ステップ8: DNSレコードを追加（ALBを指す）
echo ""
echo "=========================================="
echo "⚠️  重要: ALBを指すDNSレコードを追加"
echo "=========================================="
echo ""
echo "snowmole.co.jp のDNS管理画面で以下のレコードを追加:"
echo ""
echo "  タイプ: CNAME"
echo "  名前: estat-mcp.snowmole.co.jp"
echo "  値: $ALB_DNS"
echo "  TTL: 300（または任意）"
echo ""
echo "例（お名前.comの場合）:"
echo "  ホスト名: estat-mcp"
echo "  TYPE: CNAME"
echo "  VALUE: $ALB_DNS"
echo ""
echo "例（Route 53の場合）:"
echo "  レコード名: estat-mcp.snowmole.co.jp"
echo "  レコードタイプ: CNAME"
echo "  値: $ALB_DNS"
echo ""

read -p "DNSレコードを追加しましたか？ (y/n): " alb_dns_added

# ステップ9: Kiro設定を更新
echo ""
echo "ステップ9: Kiro設定を更新中..."

python3 << EOF
import json

with open('.kiro/settings/mcp.json', 'r') as f:
    config = json.load(f)

# HTTPS URLに更新
config['mcpServers']['estat-aws-remote']['url'] = 'https://$DOMAIN_NAME'

# rejectUnauthorizedを削除（正式な証明書なので不要）
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
echo "動作確認:"
echo "  curl https://$DOMAIN_NAME/health"
echo ""
echo "DNS伝播を待ってから（数分〜10分）、Kiroを再起動してください"
echo ""
echo "証明書情報:"
echo "  証明書ARN: $CERT_ARN"
echo "  有効期限: 自動更新"
echo ""
