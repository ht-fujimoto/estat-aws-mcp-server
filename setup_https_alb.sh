#!/bin/bash
# ALBにHTTPS（SSL/TLS）を設定するスクリプト

set -e

AWS_REGION="ap-northeast-1"
ALB_ARN="arn:aws:elasticloadbalancing:ap-northeast-1:639135896267:loadbalancer/app/estat-mcp-alb/3c8e9f5b4d2a1c0b"

echo "=========================================="
echo "ALB HTTPS設定ガイド"
echo "=========================================="
echo ""
echo "Kiroはセキュリティ上の理由から、リモートMCPサーバーに"
echo "HTTPS接続を要求します。"
echo ""
echo "以下の2つの方法があります:"
echo ""
echo "【方法1】AWS Certificate Manager (ACM) を使用（推奨）"
echo "  1. ドメイン名を取得（例: estat-mcp.example.com）"
echo "  2. Route 53でホストゾーンを作成"
echo "  3. ACMで証明書をリクエスト"
echo "  4. ALBにHTTPSリスナーを追加"
echo ""
echo "【方法2】自己署名証明書を使用（開発/テスト用）"
echo "  1. 自己署名証明書を生成"
echo "  2. ACMにインポート"
echo "  3. ALBにHTTPSリスナーを追加"
echo "  4. Kiroで証明書検証を無効化（非推奨）"
echo ""
echo "【方法3】ローカルwrapperを使用（現在の設定）"
echo "  - mcp_aws_wrapper.pyがHTTP接続を処理"
echo "  - Kiroからはローカルプロセスとして見える"
echo "  - 最もシンプルで現在動作中"
echo ""
read -p "どの方法を選びますか？ (1/2/3): " choice

case $choice in
  1)
    echo ""
    echo "=== 方法1: ACM証明書を使用 ==="
    echo ""
    read -p "ドメイン名を入力してください（例: estat-mcp.example.com）: " DOMAIN_NAME
    
    echo ""
    echo "1. ACMで証明書をリクエスト..."
    CERT_ARN=$(aws acm request-certificate \
      --domain-name $DOMAIN_NAME \
      --validation-method DNS \
      --region $AWS_REGION \
      --query 'CertificateArn' \
      --output text)
    
    echo "証明書ARN: $CERT_ARN"
    echo ""
    echo "2. DNS検証レコードを取得..."
    aws acm describe-certificate \
      --certificate-arn $CERT_ARN \
      --region $AWS_REGION \
      --query 'Certificate.DomainValidationOptions[0].ResourceRecord'
    
    echo ""
    echo "3. Route 53またはDNSプロバイダーに上記のレコードを追加してください"
    echo ""
    echo "4. 証明書が発行されたら、以下のコマンドでHTTPSリスナーを追加:"
    echo ""
    echo "aws elbv2 create-listener \\"
    echo "  --load-balancer-arn $ALB_ARN \\"
    echo "  --protocol HTTPS \\"
    echo "  --port 443 \\"
    echo "  --certificates CertificateArn=$CERT_ARN \\"
    echo "  --default-actions Type=forward,TargetGroupArn=<TARGET_GROUP_ARN> \\"
    echo "  --region $AWS_REGION"
    echo ""
    echo "5. .kiro/settings/mcp.jsonを更新:"
    echo "   \"url\": \"https://$DOMAIN_NAME/mcp\""
    ;;
    
  2)
    echo ""
    echo "=== 方法2: 自己署名証明書を使用 ==="
    echo ""
    echo "1. 自己署名証明書を生成..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout selfsigned.key -out selfsigned.crt \
      -subj "/C=JP/ST=Tokyo/L=Tokyo/O=Development/CN=estat-mcp-local"
    
    echo ""
    echo "2. ACMにインポート..."
    CERT_ARN=$(aws acm import-certificate \
      --certificate fileb://selfsigned.crt \
      --private-key fileb://selfsigned.key \
      --region $AWS_REGION \
      --query 'CertificateArn' \
      --output text)
    
    echo "証明書ARN: $CERT_ARN"
    echo ""
    echo "3. HTTPSリスナーを追加..."
    
    # Get target group ARN
    TG_ARN=$(aws elbv2 describe-target-groups \
      --names estat-mcp-tg \
      --region $AWS_REGION \
      --query 'TargetGroups[0].TargetGroupArn' \
      --output text)
    
    aws elbv2 create-listener \
      --load-balancer-arn $ALB_ARN \
      --protocol HTTPS \
      --port 443 \
      --certificates CertificateArn=$CERT_ARN \
      --default-actions Type=forward,TargetGroupArn=$TG_ARN \
      --region $AWS_REGION
    
    echo ""
    echo "✅ HTTPSリスナーを追加しました"
    echo ""
    echo "4. ALBのDNS名を取得..."
    ALB_DNS=$(aws elbv2 describe-load-balancers \
      --load-balancer-arns $ALB_ARN \
      --region $AWS_REGION \
      --query 'LoadBalancers[0].DNSName' \
      --output text)
    
    echo "ALB DNS: $ALB_DNS"
    echo ""
    echo "5. .kiro/settings/mcp.jsonを更新:"
    echo "   \"url\": \"https://$ALB_DNS/mcp\""
    echo ""
    echo "⚠️  注意: 自己署名証明書のため、証明書エラーが発生する可能性があります"
    ;;
    
  3)
    echo ""
    echo "=== 方法3: ローカルwrapperを使用（現在の設定） ==="
    echo ""
    echo "✅ 既に設定済みです！"
    echo ""
    echo "現在の設定:"
    echo "  - estat-aws-local: 有効（ローカルwrapper経由）"
    echo "  - estat-aws-remote: 無効（HTTP接続のため）"
    echo ""
    echo "この方法では:"
    echo "  - Kiro → python3 mcp_aws_wrapper.py → HTTP → ECS"
    echo "  - ローカルプロセスがHTTP接続を処理"
    echo "  - 追加設定不要で動作"
    echo ""
    echo "動作確認:"
    echo "  Kiroで「東京都の人口データを検索してください」と試してみてください"
    ;;
    
  *)
    echo "無効な選択です"
    exit 1
    ;;
esac

echo ""
echo "=========================================="
echo "完了"
echo "=========================================="
