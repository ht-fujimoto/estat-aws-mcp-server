#!/bin/bash
# ローカルwrapperに戻すスクリプト

echo "ローカルwrapperに切り替え中..."

# Kiro設定を更新
python3 << 'EOF'
import json

with open('.kiro/settings/mcp.json', 'r') as f:
    config = json.load(f)

# ローカルを有効化、リモートを無効化
config['mcpServers']['estat-aws-local']['disabled'] = False
config['mcpServers']['estat-aws-remote']['disabled'] = True

with open('.kiro/settings/mcp.json', 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print('✅ ローカルwrapperに切り替えました')
print('   Kiro → mcp_aws_wrapper.py → HTTP → ECS Fargate')
EOF

echo ""
echo "Kiroを再起動してください"
