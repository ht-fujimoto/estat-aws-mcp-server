#!/bin/bash
# DNSとHTTPSの動作確認

DOMAIN="estat-mcp.snowmole.co.jp"

echo "=========================================="
echo "DNS & HTTPS 動作確認"
echo "=========================================="
echo ""
echo "ドメイン: $DOMAIN"
echo ""

while true; do
  TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
  
  # DNS確認
  DNS_RESULT=$(host $DOMAIN 2>&1)
  
  if echo "$DNS_RESULT" | grep -q "has address\|is an alias"; then
    echo "[$TIMESTAMP] ✅ DNS解決成功"
    echo "$DNS_RESULT"
    echo ""
    
    # HTTPS確認
    echo "HTTPS接続を確認中..."
    HTTPS_RESULT=$(curl -s -o /dev/null -w "%{http_code}" https://$DOMAIN/health 2>&1)
    
    if [ "$HTTPS_RESULT" = "200" ]; then
      echo "✅ HTTPS接続成功！"
      echo ""
      
      # 詳細確認
      echo "詳細情報:"
      curl -s https://$DOMAIN/health | python3 -m json.tool
      echo ""
      
      echo "=========================================="
      echo "✅ すべて正常に動作しています！"
      echo "=========================================="
      echo ""
      echo "次のステップ:"
      echo "  Kiroを再起動してください"
      echo ""
      break
    else
      echo "⚠️  HTTPS接続失敗（HTTPステータス: $HTTPS_RESULT）"
      echo "   30秒後に再確認..."
      sleep 30
    fi
  else
    echo "[$TIMESTAMP] ⏳ DNS未解決"
    echo "   30秒後に再確認..."
    sleep 30
  fi
done
