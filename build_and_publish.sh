#!/bin/bash
# MCPサーバーのビルドと公開スクリプト

set -e

echo "=== e-Stat MCP Server Build & Publish Script ==="
echo ""

# カラー定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. 環境チェック
echo -e "${YELLOW}Step 1: Checking environment...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

if ! command -v pip &> /dev/null; then
    echo -e "${RED}Error: pip is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python and pip are installed${NC}"
echo ""

# 2. 必要なツールのインストール
echo -e "${YELLOW}Step 2: Installing build tools...${NC}"
pip install --upgrade pip setuptools wheel build twine
echo -e "${GREEN}✓ Build tools installed${NC}"
echo ""

# 3. 古いビルドファイルのクリーンアップ
echo -e "${YELLOW}Step 3: Cleaning up old build files...${NC}"
rm -rf build/ dist/ *.egg-info
echo -e "${GREEN}✓ Cleaned up${NC}"
echo ""

# 4. パッケージのビルド
echo -e "${YELLOW}Step 4: Building package...${NC}"
python -m build
echo -e "${GREEN}✓ Package built successfully${NC}"
echo ""

# 5. ビルド結果の確認
echo -e "${YELLOW}Step 5: Checking build results...${NC}"
ls -lh dist/
echo ""

# 6. パッケージの検証
echo -e "${YELLOW}Step 6: Validating package...${NC}"
twine check dist/*
echo -e "${GREEN}✓ Package validation passed${NC}"
echo ""

# 7. 公開先の選択
echo -e "${YELLOW}Step 7: Choose publishing destination${NC}"
echo "1) TestPyPI (recommended for testing)"
echo "2) PyPI (production)"
echo "3) Skip publishing"
read -p "Enter your choice (1-3): " choice

case $choice in
    1)
        echo -e "${YELLOW}Publishing to TestPyPI...${NC}"
        twine upload --repository testpypi dist/*
        echo -e "${GREEN}✓ Published to TestPyPI${NC}"
        echo ""
        echo "Install with:"
        echo "pip install -i https://test.pypi.org/simple/ estat-mcp-server"
        ;;
    2)
        echo -e "${YELLOW}Publishing to PyPI...${NC}"
        read -p "Are you sure you want to publish to production PyPI? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            twine upload dist/*
            echo -e "${GREEN}✓ Published to PyPI${NC}"
            echo ""
            echo "Install with:"
            echo "pip install estat-mcp-server"
        else
            echo "Publishing cancelled"
        fi
        ;;
    3)
        echo "Skipping publishing"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}=== Build process completed ===${NC}"
