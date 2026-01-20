#!/bin/bash

# E-stat Data Lake MCP Server セットアップスクリプト

echo "========================================="
echo "E-stat Data Lake MCP Server セットアップ"
echo "========================================="
echo ""

# 1. 依存パッケージのインストール
echo "ステップ1: 依存パッケージのインストール"
echo "-----------------------------------------"
pip3 install boto3 pandas pyarrow pyyaml
echo ""
echo "注: MCPパッケージは不要です（stdioプロトコルを直接実装）"
echo ""

# 2. 環境変数の確認
echo "ステップ2: 環境変数の確認"
echo "-----------------------------------------"

if [ -z "$AWS_ACCESS_KEY_ID" ]; then
    echo "⚠️  AWS_ACCESS_KEY_ID が設定されていません"
    echo "   export AWS_ACCESS_KEY_ID=your_access_key"
else
    echo "✅ AWS_ACCESS_KEY_ID: 設定済み"
fi

if [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "⚠️  AWS_SECRET_ACCESS_KEY が設定されていません"
    echo "   export AWS_SECRET_ACCESS_KEY=your_secret_key"
else
    echo "✅ AWS_SECRET_ACCESS_KEY: 設定済み"
fi

if [ -z "$AWS_REGION" ]; then
    echo "⚠️  AWS_REGION が設定されていません（デフォルト: ap-northeast-1）"
    export AWS_REGION=ap-northeast-1
else
    echo "✅ AWS_REGION: $AWS_REGION"
fi

echo ""

# 3. S3バケットの確認
echo "ステップ3: S3バケットの確認"
echo "-----------------------------------------"

BUCKET_NAME="estat-iceberg-datalake"

if aws s3 ls "s3://$BUCKET_NAME" 2>/dev/null; then
    echo "✅ S3バケット '$BUCKET_NAME' は存在します"
else
    echo "⚠️  S3バケット '$BUCKET_NAME' が見つかりません"
    echo ""
    read -p "バケットを作成しますか？ (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        aws s3 mb "s3://$BUCKET_NAME" --region $AWS_REGION
        echo "✅ S3バケット '$BUCKET_NAME' を作成しました"
    fi
fi

echo ""

# 4. Glueデータベースの確認
echo "ステップ4: Glueデータベースの確認"
echo "-----------------------------------------"

DATABASE_NAME="estat_iceberg_db"

if aws glue get-database --name $DATABASE_NAME 2>/dev/null; then
    echo "✅ Glueデータベース '$DATABASE_NAME' は存在します"
else
    echo "⚠️  Glueデータベース '$DATABASE_NAME' が見つかりません"
    echo ""
    read -p "データベースを作成しますか？ (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        aws glue create-database \
            --database-input "{\"Name\":\"$DATABASE_NAME\",\"Description\":\"E-stat Iceberg Data Lake\"}" \
            --region $AWS_REGION
        echo "✅ Glueデータベース '$DATABASE_NAME' を作成しました"
    fi
fi

echo ""

# 5. MCP設定の確認
echo "ステップ5: MCP設定の確認"
echo "-----------------------------------------"

MCP_CONFIG=".kiro/settings/mcp.json"

if [ -f "$MCP_CONFIG" ]; then
    if grep -q "estat-datalake" "$MCP_CONFIG"; then
        echo "✅ MCP設定に 'estat-datalake' が存在します"
    else
        echo "⚠️  MCP設定に 'estat-datalake' が見つかりません"
        echo "   手動で追加してください"
    fi
else
    echo "⚠️  MCP設定ファイルが見つかりません: $MCP_CONFIG"
fi

echo ""

# 6. 完了
echo "========================================="
echo "セットアップ完了"
echo "========================================="
echo ""
echo "次のステップ:"
echo "1. Kiroを再起動してMCPサーバーを読み込む"
echo "2. 'estat-datalake' MCPサーバーが利用可能か確認"
echo "3. テストデータで動作確認"
echo ""
echo "使用例:"
echo "  ingest_dataset_complete("
echo "    s3_input_path=\"s3://estat-data-lake/raw/data/0004021107_20260119_052606.json\","
echo "    dataset_id=\"0004021107\","
echo "    dataset_name=\"年齢（各歳），男女別人口及び人口性比\","
echo "    domain=\"population\""
echo "  )"
echo ""
