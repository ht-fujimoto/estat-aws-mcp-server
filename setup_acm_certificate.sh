#!/bin/bash
# ACMで正式な証明書を取得するスクリプト

set -e

AWS_REGION="ap-northeast-1"
ALB_ARN="arn:aws:elasticloadbalancing:ap-northeast-1:639135896267:loadbalancer/app/estat-mcp-alb/fcfeae606f00522b"

echo "=========================================="
echo "ACM証明書取得ガイド（HTTPS対応）"
echo "=========================================="
echo ""
echo "KiroはHTTPS接続を要求し、自己署名証明書を受け入れません。"
echo "正式な証明書が必要です。"
echo ""
echo "【必要なもの】"
echo "  - ドメイン名（例: estat-mcp.example.com）"
echo "  - DNSアクセス権（Route 53または他のDNSプロバイダー）"
echo ""
echo "【選択肢】"
echo "  1. 既存のドメインを使用"
echo "  2. Route 53で新しいドメインを取得（年間約1,000円〜）"
echo ""
read -p "どちらを選びますか？ (1/2): " choice

case $choice in
  1)
    echo ""
    read -p "ドメイン名を入力してください（例: estat-mcp.example.com）: " DOMAIN_NAME
    
    echo ""
    echo "=== ステップ1: ACM証明書をリクエスト ==="
    echo ""
    
    CERT_ARN=$(aws acm request-certificate \
      --domain-name $DOMAIN_NAME \
      --validation-method DNS \
      --region $AWS_REGION \
      --query 'CertificateArn' \
      --output text)
    
    echo "✅ 証明書リクエスト完了"
    echo "   証明書ARN: $CERT_ARN"
    echo ""
    
    echo "=== ステップ2: DNS検証レコードを取得 ==="
    echo ""
    echo "⏳ 証明書情報を取得中（数秒待機）..."
    sleep 5
    
    VALIDATION_RECORD=$(aws acm describe-certificate \
      --certificate-arn $CERT_ARN \
      --region $AWS_REGION \
      --query 'Certificate.DomainValidationOptions[0].ResourceRecord' \
      --output json)
    
    echo "DNS検証レコード:"
    echo "$VALIDATION_RECORD" | python3 -m json.tool
    echo ""
    
    RECORD_NAME=$(echo "$VALIDATION_RECORD" | python3 -c "import sys, json; print(json.load(sys.stdin)['Name'])")
    RECORD_VALUE=$(echo "$VALIDATION_RECORD" | python3 -c "import sys, json; print(json.load(sys.stdin)['Value'])")
    
    echo "=== ステップ3: DNSレコードを追加 ==="
    echo ""
    echo "以下のCNAMEレコードをDNSに追加してください:"
    echo ""
    echo "  名前: $RECORD_NAME"
    echo "  タイプ: CNAME"
    echo "  値: $RECORD_VALUE"
    echo ""
    
    # Route 53を使用している場合は自動追加を提案
    read -p "Route 53を使用していますか？ (y/n): " use_route53
    
    if [ "$use_route53" = "y" ]; then
      read -p "ホストゾーンIDを入力してください: " HOSTED_ZONE_ID
      
      # Route 53にレコードを追加
      cat > /tmp/change-batch.json << EOF
{
  "Changes": [{
    "Action": "CREATE",
    "ResourceRecordSet": {
      "Name": "$RECORD_NAME",
      "Type": "CNAME",
      "TTL": 300,
      "ResourceRecords": [{"Value": "$RECORD_VALUE"}]
    }
  }]
}
EOF
      
      aws route53 change-resource-record-sets \
        --hosted-zone-id $HOSTED_ZONE_ID \
        --change-batch file:///tmp/change-batch.json
      
      echo "✅ Route 53にDNS検証レコードを追加しました"
      rm /tmp/change-batch.json
    else
      echo "⚠️  DNSプロバイダーの管理画面で手動で追加してください"
    fi
    
    echo ""
    echo "=== ステップ4: 証明書の検証を待機 ==="
    echo ""
    echo "⏳ DNS検証が完了するまで待機中..."
    echo "   これには数分〜数十分かかる場合があります"
    echo ""
    
    aws acm wait certificate-validated \
      --certificate-arn $CERT_ARN \
      --region $AWS_REGION
    
    echo "✅ 証明書が検証されました！"
    echo ""
    
    echo "=== ステップ5: ALBにHTTPSリスナーを追加 ==="
    echo ""
    
    # 既存のHTTPSリスナーを削除
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
    fi
    
    # ターゲットグループARNを取得
    TG_ARN=$(aws elbv2 describe-target-groups \
      --names estat-mcp-tg \
      --region $AWS_REGION \
      --query 'TargetGroups[0].TargetGroupArn' \
      --output text)
    
    # HTTPSリスナーを作成
    LISTENER_ARN=$(aws elbv2 create-listener \
      --load-balancer-arn $ALB_ARN \
      --protocol HTTPS \
      --port 443 \
      --certificates CertificateArn=$CERT_ARN \
      --default-actions Type=forward,TargetGroupArn=$TG_ARN \
      --region $AWS_REGION \
      --query 'Listeners[0].ListenerArn' \
      --output text)
    
    echo "✅ HTTPSリスナーを追加しました"
    echo "   リスナーARN: $LISTENER_ARN"
    echo ""
    
    echo "=== ステップ6: DNSレコードを追加（ALBを指す） ==="
    echo ""
    
    ALB_DNS=$(aws elbv2 describe-load-balancers \
      --load-balancer-arns $ALB_ARN \
      --region $AWS_REGION \
      --query 'LoadBalancers[0].DNSName' \
      --output text)
    
    echo "以下のレコードをDNSに追加してください:"
    echo ""
    echo "  名前: $DOMAIN_NAME"
    echo "  タイプ: CNAME"
    echo "  値: $ALB_DNS"
    echo ""
    
    if [ "$use_route53" = "y" ]; then
      cat > /tmp/alb-record.json << EOF
{
  "Changes": [{
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": "$DOMAIN_NAME",
      "Type": "CNAME",
      "TTL": 300,
      "ResourceRecords": [{"Value": "$ALB_DNS"}]
    }
  }]
}
EOF
      
      aws route53 change-resource-record-sets \
        --hosted-zone-id $HOSTED_ZONE_ID \
        --change-batch file:///tmp/alb-record.json
      
      echo "✅ Route 53にALBレコードを追加しました"
      rm /tmp/alb-record.json
    fi
    
    echo ""
    echo "=== ステップ7: Kiro設定を更新 ==="
    echo ""
    
    python3 << EOF
import json

with open('.kiro/settings/mcp.json', 'r') as f:
    config = json.load(f)

config['mcpServers']['estat-aws-remote']['url'] = 'https://$DOMAIN_NAME'
del config['mcpServers']['estat-aws-remote']['rejectUnauthorized']

with open('.kiro/settings/mcp.json', 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print('✅ Kiro設定を更新しました')
EOF
    
    echo ""
    echo "=========================================="
    echo "✅ HTTPS設定完了！"
    echo "=========================================="
    echo ""
    echo "HTTPS URL: https://$DOMAIN_NAME"
    echo ""
    echo "動作確認:"
    echo "  curl https://$DOMAIN_NAME/health"
    echo ""
    echo "Kiroを再起動してください"
    ;;
    
  2)
    echo ""
    echo "=== Route 53でドメインを取得 ==="
    echo ""
    echo "1. AWS Console → Route 53 → ドメインの登録"
    echo "2. 希望のドメイン名を検索（例: my-estat-mcp.com）"
    echo "3. 購入手続き（年間約1,000円〜）"
    echo "4. ドメイン取得後、このスクリプトを再実行してください"
    echo ""
    echo "または、AWS CLIで取得:"
    echo ""
    read -p "ドメイン名を入力してください（例: my-estat-mcp.com）: " NEW_DOMAIN
    
    echo ""
    echo "以下のコマンドでドメインを取得できます:"
    echo ""
    echo "aws route53domains register-domain \\"
    echo "  --domain-name $NEW_DOMAIN \\"
    echo "  --duration-in-years 1 \\"
    echo "  --admin-contact FirstName=Admin,LastName=User,ContactType=PERSON,... \\"
    echo "  --registrant-contact ... \\"
    echo "  --tech-contact ..."
    echo ""
    echo "詳細: https://docs.aws.amazon.com/cli/latest/reference/route53domains/register-domain.html"
    ;;
    
  *)
    echo "無効な選択です"
    exit 1
    ;;
esac

echo ""
