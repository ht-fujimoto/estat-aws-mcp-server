#!/bin/bash
# 一時的にHTTPに戻すスクリプト

echo "HTTPに切り替え中..."

# Kiro設定を更新
python3 << 'EOF'
import json

with open('.kiro/settings/mcp.json', 'r') as f:
    config = json.load(f)

# HTTPに変更
config['mcpServers']['estat-aws-remote']['url'] = 'http://estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com'

with open('.kiro/settings/mcp.json', 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print('✅ HTTPに切り替えました')
print('   URL: http://estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com')
EOF

echo ""
echo "Kiroを再起動してください"
