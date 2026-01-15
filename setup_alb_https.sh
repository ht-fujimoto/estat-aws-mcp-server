#!/bin/bash
# ALBにHTTPS（自己署名証明書）を設定

set -e

AWS_REGION="ap-northeast-1"
ALB_NAME="estat-mcp-alb"

echo "=========================================="
echo "ALB HTTPS設定（自己署名証明書）"
echo "=========================================="
echo ""

# 1. 自己署名証明書を生成
echo "1. 自己署名証明書を生成中..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout estat-mcp-selfsigned.key \
  -out estat-mcp-selfsigned.crt \
  -subj "/C=JP/ST=Tokyo/L=Tokyo/O=Development/CN=estat-mcp.local" \
  2>/dev/null

echo "✅ 証明書生成完了"
echo "   - estat-mcp-selfsigned.crt"
echo "   - estat-mcp-selfsigned.key"

# 2. ACMにインポート
echo ""
echo "2. ACMに証明書をインポート中..."
CERT_ARN=$(aws acm import-certificate \
  --certificate fileb://estat-mcp-selfsigned.crt \
  --private-key fileb://estat-mcp-selfsigned.key \
  --region $AWS_REGION \
  --query 'CertificateArn' \
  --output text)

echo "✅ 証明書インポート完了"
echo "   証明書ARN: $CERT_ARN"

# 3. ALB ARNを取得
echo ""
echo "3. ALB情報を取得中..."
ALB_ARN=$(aws elbv2 describe-load-balancers \
  --names $ALB_NAME \
  --region $AWS_REGION \
  --query 'LoadBalancers[0].LoadBalancerArn' \
  --output text)

ALB_DNS=$(aws elbv2 describe-load-balancers \
  --names $ALB_NAME \
  --region $AWS_REGION \
  --query 'LoadBalancers[0].DNSName' \
  --output text)

echo "✅ ALB情報取得完了"
echo "   ALB ARN: $ALB_ARN"
echo "   ALB DNS: $ALB_DNS"

# 4. ターゲットグループARNを取得
echo ""
echo "4. ターゲットグループ情報を取得中..."
TG_ARN=$(aws elbv2 describe-target-groups \
  --names estat-mcp-tg \
  --region $AWS_REGION \
  --query 'TargetGroups[0].TargetGroupArn' \
  --output text)

echo "✅ ターゲットグループARN: $TG_ARN"

# 5. 既存のHTTPSリスナーを確認
echo ""
echo "5. 既存のHTTPSリスナーを確認中..."
EXISTING_HTTPS=$(aws elbv2 describe-listeners \
  --load-balancer-arn $ALB_ARN \
  --region $AWS_REGION \
  --query 'Listeners[?Protocol==`HTTPS`].ListenerArn' \
  --output text)

if [ -n "$EXISTING_HTTPS" ]; then
  echo "⚠️  既存のHTTPSリスナーが見つかりました: $EXISTING_HTTPS"
  read -p "削除して再作成しますか？ (y/n): " confirm
  if [ "$confirm" = "y" ]; then
    aws elbv2 delete-listener \
      --listener-arn $EXISTING_HTTPS \
      --region $AWS_REGION
    echo "✅ 既存のリスナーを削除しました"
  else
    echo "❌ 処理を中止しました"
    exit 1
  fi
fi

# 6. HTTPSリスナーを作成
echo ""
echo "6. HTTPSリスナーを作成中..."
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

# 7. セキュリティグループを確認
echo ""
echo "7. セキュリティグループを確認中..."
SG_ID=$(aws elbv2 describe-load-balancers \
  --load-balancer-arns $ALB_ARN \
  --region $AWS_REGION \
  --query 'LoadBalancers[0].SecurityGroups[0]' \
  --output text)

echo "   セキュリティグループID: $SG_ID"

# ポート443が開いているか確認
HTTPS_RULE=$(aws ec2 describe-security-groups \
  --group-ids $SG_ID \
  --region $AWS_REGION \
  --query 'SecurityGroups[0].IpPermissions[?FromPort==`443`]' \
  --output text)

if [ -z "$HTTPS_RULE" ]; then
  echo "⚠️  ポート443が開いていません。追加します..."
  aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 443 \
    --cidr 0.0.0.0/0 \
    --region $AWS_REGION
  echo "✅ ポート443を開放しました"
else
  echo "✅ ポート443は既に開放されています"
fi

echo ""
echo "=========================================="
echo "✅ HTTPS設定完了！"
echo "=========================================="
echo ""
echo "HTTPS URL: https://$ALB_DNS/mcp"
echo ""
echo "次のステップ:"
echo "1. .kiro/settings/mcp.jsonを更新"
echo "2. Kiroを再起動"
echo "3. 動作確認"
echo ""
echo "動作確認コマンド:"
echo "curl -k https://$ALB_DNS/health"
echo ""
echo "⚠️  注意: 自己署名証明書のため、-k オプション（証明書検証スキップ）が必要です"
echo ""

# 8. Kiro設定ファイルを更新
echo "8. Kiro設定を更新しますか？ (y/n): "
read -p "" update_config

if [ "$update_config" = "y" ]; then
  echo ""
  echo ".kiro/settings/mcp.jsonを更新中..."
  
  # バックアップを作成
  cp .kiro/settings/mcp.json .kiro/settings/mcp.json.backup
  
  # 設定を更新（Pythonで処理）
  python3 << EOF
import json

with open('.kiro/settings/mcp.json', 'r') as f:
    config = json.load(f)

# estat-aws-remoteを有効化
config['mcpServers']['estat-aws-remote']['url'] = 'https://$ALB_DNS/mcp'
config['mcpServers']['estat-aws-remote']['disabled'] = False

# estat-aws-localを無効化
config['mcpServers']['estat-aws-local']['disabled'] = True

with open('.kiro/settings/mcp.json', 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print('✅ 設定ファイルを更新しました')
print('   バックアップ: .kiro/settings/mcp.json.backup')
EOF

  echo ""
  echo "✅ 完了！Kiroを再起動してください"
else
  echo ""
  echo "手動で .kiro/settings/mcp.json を更新してください:"
  echo ""
  echo '  "estat-aws-remote": {'
  echo '    "transport": "streamable-http",'
  echo "    \"url\": \"https://$ALB_DNS/mcp\","
  echo '    "disabled": false'
  echo '  }'
  echo ""
  echo '  "estat-aws-local": {'
  echo '    "disabled": true'
  echo '  }'
fi

echo ""
