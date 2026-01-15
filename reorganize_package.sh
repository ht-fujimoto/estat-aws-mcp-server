#!/bin/bash
# MCPサーバーをパッケージ構造に再編成するスクリプト

set -e

echo "=== Reorganizing MCP Server Package Structure ==="
echo ""

# カラー定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. パッケージディレクトリの作成
echo -e "${YELLOW}Creating package directory structure...${NC}"
mkdir -p estat_mcp_server
echo -e "${GREEN}✓ Created estat_mcp_server directory${NC}"

# 2. ファイルのコピー
echo -e "${YELLOW}Copying MCP server files...${NC}"

if [ -d "mcp_servers" ]; then
    # メインサーバーファイル
    if [ -f "mcp_servers/estat_enhanced_analysis.py" ]; then
        cp mcp_servers/estat_enhanced_analysis.py estat_mcp_server/server.py
        echo "✓ Copied server.py"
    fi
    
    # HITLファイル
    if [ -f "mcp_servers/estat_analysis_hitl.py" ]; then
        cp mcp_servers/estat_analysis_hitl.py estat_mcp_server/hitl.py
        echo "✓ Copied hitl.py"
    fi
    
    # 辞書ファイル
    if [ -f "mcp_servers/estat_enhanced_dictionary.py" ]; then
        cp mcp_servers/estat_enhanced_dictionary.py estat_mcp_server/dictionary.py
        echo "✓ Copied dictionary.py"
    fi
    
    if [ -f "mcp_servers/estat_keyword_dictionary.py" ]; then
        cp mcp_servers/estat_keyword_dictionary.py estat_mcp_server/keyword_dict.py
        echo "✓ Copied keyword_dict.py"
    fi
else
    echo -e "${YELLOW}Warning: mcp_servers directory not found${NC}"
fi

# 3. __init__.py の作成
echo -e "${YELLOW}Creating __init__.py...${NC}"
cat > estat_mcp_server/__init__.py << 'EOF'
"""
e-Stat Enhanced Analysis MCP Server

A Model Context Protocol (MCP) server for accessing and analyzing
Japanese government statistics from e-Stat with enhanced features:
- Keyword suggestion with 134-term statistical dictionary
- Advanced 8-factor scoring algorithm
- AWS S3 integration for data storage
- CSV export and download capabilities
"""

__version__ = "1.0.0"
__author__ = "Yukihiro Yamashita"
__license__ = "MIT"

from .server import MCPServer

try:
    from .server import main
    __all__ = ["MCPServer", "main", "__version__"]
except ImportError:
    __all__ = ["MCPServer", "__version__"]
EOF
echo -e "${GREEN}✓ Created __init__.py${NC}"

# 4. パッケージ構造の確認
echo ""
echo -e "${YELLOW}Package structure:${NC}"
tree estat_mcp_server/ 2>/dev/null || ls -la estat_mcp_server/

echo ""
echo -e "${GREEN}=== Package reorganization completed ===${NC}"
echo ""
echo "Next steps:"
echo "1. Review the files in estat_mcp_server/"
echo "2. Update import statements if needed"
echo "3. Run: python -m build"
echo "4. Run: ./build_and_publish.sh"
