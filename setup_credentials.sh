#!/bin/bash
# estat-aws MCP セットアップスクリプト
# 他の環境でこのMCPを使用する際の初期設定を支援

set -e

echo "=========================================="
echo "estat-aws MCP セットアップ"
echo "=========================================="
echo ""

# カラー定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. AWS CLIの確認
echo -e "${BLUE}[1/6] AWS CLIの確認${NC}"
if command -v aws &> /dev/null; then
    AWS_VERSION=$(aws --version)
    echo -e "${GREEN}✓ AWS CLI がインストールされています: ${AWS_VERSION}${NC}"
else
    echo -e "${RED}✗ AWS CLI がインストールされていません${NC}"
    echo ""
    echo "AWS CLIをインストールしてください:"
    echo "  macOS:   brew install awscli"
    echo "  Linux:   pip install awscli"
    echo "  Windows: https://aws.amazon.com/cli/"
    exit 1
fi
echo ""

# 2. AWS認証情報の確認
echo -e "${BLUE}[2/6] AWS認証情報の確認${NC}"
if [ -f ~/.aws/credentials ]; then
    echo -e "${GREEN}✓ ~/.aws/credentials が存在します${NC}"
    
    # プロファイルを確認
    if grep -q "\[default\]" ~/.aws/credentials; then
        echo -e "${GREEN}✓ [default] プロファイルが設定されています${NC}"
    else
        echo -e "${YELLOW}⚠ [default] プロファイルが見つかりません${NC}"
    fi
else
    echo -e "${YELLOW}⚠ ~/.aws/credentials が見つかりません${NC}"
    echo ""
    read -p "AWS認証情報を設定しますか？ (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        aws configure
    else
        echo -e "${RED}AWS認証情報の設定をスキップしました${NC}"
        echo "後で 'aws configure' を実行してください"
    fi
fi
echo ""

# 3. .envファイルの確認
echo -e "${BLUE}[3/6] .envファイルの確認${NC}"
if [ -f .env ]; then
    echo -e "${GREEN}✓ .env ファイルが存在します${NC}"
    
    # 必須項目の確認
    if grep -q "ESTAT_APP_ID=" .env; then
        ESTAT_APP_ID=$(grep "ESTAT_APP_ID=" .env | cut -d '=' -f2)
        if [ "$ESTAT_APP_ID" != "your_estat_app_id_here" ] && [ -n "$ESTAT_APP_ID" ]; then
            echo -e "${GREEN}✓ ESTAT_APP_ID が設定されています${NC}"
        else
            echo -e "${YELLOW}⚠ ESTAT_APP_ID が未設定です${NC}"
        fi
    fi
    
    if grep -q "S3_BUCKET=" .env; then
        S3_BUCKET=$(grep "S3_BUCKET=" .env | cut -d '=' -f2)
        echo -e "${GREEN}✓ S3_BUCKET: ${S3_BUCKET}${NC}"
    fi
    
    if grep -q "AWS_REGION=" .env; then
        AWS_REGION=$(grep "AWS_REGION=" .env | cut -d '=' -f2)
        echo -e "${GREEN}✓ AWS_REGION: ${AWS_REGION}${NC}"
    fi
else
    echo -e "${YELLOW}⚠ .env ファイルが見つかりません${NC}"
    
    if [ -f .env.example ]; then
        read -p ".env.example から .env を作成しますか？ (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cp .env.example .env
            echo -e "${GREEN}✓ .env ファイルを作成しました${NC}"
            echo -e "${YELLOW}⚠ .env ファイルを編集して、必要な値を設定してください${NC}"
        fi
    else
        echo -e "${RED}✗ .env.example も見つかりません${NC}"
    fi
fi
echo ""

# 4. Python環境の確認
echo -e "${BLUE}[4/6] Python環境の確認${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✓ Python3 がインストールされています: ${PYTHON_VERSION}${NC}"
else
    echo -e "${RED}✗ Python3 がインストールされていません${NC}"
    exit 1
fi

# 必須パッケージの確認
echo "必須パッケージの確認中..."
MISSING_PACKAGES=()

python3 -c "import boto3" 2>/dev/null || MISSING_PACKAGES+=("boto3")
python3 -c "import requests" 2>/dev/null || MISSING_PACKAGES+=("requests")
python3 -c "import pandas" 2>/dev/null || MISSING_PACKAGES+=("pandas")

if [ ${#MISSING_PACKAGES[@]} -eq 0 ]; then
    echo -e "${GREEN}✓ すべての必須パッケージがインストールされています${NC}"
else
    echo -e "${YELLOW}⚠ 以下のパッケージがインストールされていません: ${MISSING_PACKAGES[*]}${NC}"
    read -p "インストールしますか？ (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pip3 install "${MISSING_PACKAGES[@]}"
    fi
fi
echo ""

# 5. S3バケットの確認
echo -e "${BLUE}[5/6] S3バケットの確認${NC}"
if [ -f .env ]; then
    S3_BUCKET=$(grep "S3_BUCKET=" .env | cut -d '=' -f2)
    AWS_REGION=$(grep "AWS_REGION=" .env | cut -d '=' -f2 || echo "ap-northeast-1")
    
    if [ -n "$S3_BUCKET" ] && [ "$S3_BUCKET" != "your-bucket-name" ]; then
        if aws s3 ls "s3://${S3_BUCKET}" --region "${AWS_REGION}" 2>/dev/null; then
            echo -e "${GREEN}✓ S3バケット '${S3_BUCKET}' にアクセスできます${NC}"
        else
            echo -e "${YELLOW}⚠ S3バケット '${S3_BUCKET}' にアクセスできません${NC}"
            read -p "バケットを作成しますか？ (y/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                aws s3 mb "s3://${S3_BUCKET}" --region "${AWS_REGION}"
                echo -e "${GREEN}✓ S3バケットを作成しました${NC}"
            fi
        fi
    else
        echo -e "${YELLOW}⚠ S3_BUCKET が設定されていません${NC}"
    fi
else
    echo -e "${YELLOW}⚠ .env ファイルが見つかりません${NC}"
fi
echo ""

# 6. MCP設定の確認
echo -e "${BLUE}[6/6] MCP設定の確認${NC}"
if [ -f .kiro/settings/mcp.json ]; then
    echo -e "${GREEN}✓ .kiro/settings/mcp.json が存在します${NC}"
    
    # estat-awsサーバーの確認
    if grep -q "estat-aws" .kiro/settings/mcp.json; then
        echo -e "${GREEN}✓ estat-aws サーバーが設定されています${NC}"
    else
        echo -e "${YELLOW}⚠ estat-aws サーバーが見つかりません${NC}"
    fi
else
    echo -e "${YELLOW}⚠ .kiro/settings/mcp.json が見つかりません${NC}"
fi
echo ""

# サマリー
echo "=========================================="
echo -e "${GREEN}セットアップチェック完了${NC}"
echo "=========================================="
echo ""
echo "次のステップ:"
echo "1. .env ファイルを編集して、e-Stat APIキーを設定"
echo "   ESTAT_APP_ID=your_estat_app_id_here"
echo ""
echo "2. 必要に応じて S3_BUCKET と AWS_REGION を変更"
echo ""
echo "3. MCPサーバーをテスト:"
echo "   python3 mcp_aws_wrapper.py"
echo ""
echo "詳細は AWS_CREDENTIALS_GUIDE.md を参照してください"
echo ""
