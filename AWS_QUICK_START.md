# AWS デプロイ クイックスタート

MCPサーバーをAWSにデプロイする最速の方法。

## 🎯 3つのAWSデプロイオプション

| 方法 | 難易度 | 所要時間 | 月額コスト | 推奨用途 |
|------|--------|---------|-----------|----------|
| **Lambda + API Gateway** | ⭐⭐ | 10分 | $0〜$10 | 小〜中規模（推奨） |
| **App Runner** | ⭐ | 15分 | $5〜$20 | 最も簡単 |
| **ECS Fargate** | ⭐⭐⭐ | 30分 | $15〜$50 | 本格運用 |

---

## 🚀 方法1: Lambda + API Gateway（推奨）

### メリット
- ✅ サーバーレス（管理不要）
- ✅ 従量課金（使った分だけ）
- ✅ 無料枠: 月100万リクエスト
- ✅ 自動スケーリング

### 事前準備

1. **AWS CLIのインストール**

**Mac:**
```bash
brew install awscli
```

**Linux:**
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

**Windows:**
[インストーラーをダウンロード](https://aws.amazon.com/cli/)

2. **AWS認証情報の設定**

```bash
aws configure
```

入力項目:
- AWS Access Key ID: `your_access_key`
- AWS Secret Access Key: `your_secret_key`
- Default region name: `ap-northeast-1`
- Default output format: `json`

### デプロイ手順

```bash
# 1. 環境変数を設定
export ESTAT_APP_ID="your_estat_api_key"
export AWS_REGION="ap-northeast-1"  # 東京リージョン

# 2. デプロイスクリプトを実行
chmod +x deploy_aws_lambda.sh
./deploy_aws_lambda.sh
```

### 完了！

デプロイが完了すると、以下のような出力が表示されます：

```
╔══════════════════════════════════════════════════════════════╗
║                  Deployment Complete! 🎉                     ║
╚══════════════════════════════════════════════════════════════╝

Service Information:
  Function Name: estat-mcp-server
  API URL: https://xxxxx.execute-api.ap-northeast-1.amazonaws.com/prod
```

---

## 🌟 方法2: App Runner（最も簡単）

### メリット
- ✅ **最も簡単**（Dockerfileから自動デプロイ）
- ✅ HTTPS自動設定
- ✅ 自動スケーリング
- ✅ ヘルスチェック自動設定

### 事前準備

- AWS CLI（上記参照）
- Docker（[インストール](https://docs.docker.com/get-docker/)）

### デプロイ手順

```bash
# 1. 環境変数を設定
export ESTAT_APP_ID="your_estat_api_key"
export AWS_REGION="ap-northeast-1"

# 2. デプロイスクリプトを実行
chmod +x deploy_aws_apprunner.sh
./deploy_aws_apprunner.sh
```

### 完了！

3-5分でデプロイが完了し、HTTPSのURLが発行されます。

---

## 📊 コスト試算

### Lambda + API Gateway

**小規模（月1万リクエスト）:**
- Lambda: 無料枠内 → $0
- API Gateway: 無料枠内 → $0
- **合計: $0/月**

**中規模（月100万リクエスト）:**
- Lambda: 無料枠内 → $0
- API Gateway: 無料枠内 → $0
- **合計: $0/月**

**大規模（月1000万リクエスト）:**
- Lambda: $2
- API Gateway: $3.50
- **合計: $5.50/月**

### App Runner

**常時稼働:**
- 基本料金: $5/月（0.25 vCPU, 0.5 GB）
- リクエスト料金: ほぼ無料
- **合計: $5〜$10/月**

### ECS Fargate

**常時稼働（1タスク）:**
- 0.25 vCPU: $7.20/月
- 0.5 GB メモリ: $0.80/月
- ALB: $16/月
- **合計: $24/月**

---

## 🧪 動作確認

### ヘルスチェック

```bash
# Lambda
curl https://your-api-id.execute-api.ap-northeast-1.amazonaws.com/prod/health

# App Runner
curl https://your-service-url.ap-northeast-1.awsapprunner.com/health
```

**期待される出力:**
```json
{
  "status": "healthy",
  "service": "e-Stat MCP Server",
  "version": "1.0.0",
  "timestamp": "2026-01-08T12:00:00"
}
```

### ツール一覧の取得

```bash
curl https://your-api-url/tools
```

### ツールの実行

```bash
curl -X POST https://your-api-url/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "search_estat_data",
    "arguments": {
      "query": "世田谷区 人口",
      "max_results": 5
    }
  }'
```

---

## ⚙️ Kiro設定

デプロイ完了後、`~/.kiro/settings/mcp.json`に追加：

```json
{
  "mcpServers": {
    "estat-aws": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "https://your-api-url/execute",
        "-H", "Content-Type: application/json",
        "-d", "@-"
      ],
      "disabled": false
    }
  }
}
```

Kiroを再起動して、以下のように使用：

```
世田谷区の人口データを検索してください
```

---

## 🔒 セキュリティ設定（オプション）

### API認証の追加

#### 1. Parameter StoreにAPIキーを保存

```bash
aws ssm put-parameter \
  --name "/estat-mcp/client-api-key" \
  --value "your_secret_key" \
  --type "SecureString" \
  --region ap-northeast-1
```

#### 2. Lambda環境変数に追加

```bash
aws lambda update-function-configuration \
  --function-name estat-mcp-server \
  --environment "Variables={MCP_API_KEY=your_secret_key}" \
  --region ap-northeast-1
```

#### 3. Kiro設定を更新

```json
{
  "mcpServers": {
    "estat-aws": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "https://your-api-url/execute",
        "-H", "Content-Type: application/json",
        "-H", "X-API-Key: your_secret_key",
        "-d", "@-"
      ]
    }
  }
}
```

---

## 📊 モニタリング

### CloudWatch Logs

```bash
# ログの確認
aws logs tail /aws/lambda/estat-mcp-server --follow --region ap-northeast-1
```

### CloudWatch Metrics

AWS Console → CloudWatch → Metrics → Lambda/API Gateway

主要メトリクス:
- Invocations（実行回数）
- Duration（実行時間）
- Errors（エラー数）
- Throttles（スロットル数）

---

## 🔄 更新方法

### コードの更新

```bash
# 1. コードを修正

# 2. 再デプロイ
./deploy_aws_lambda.sh
```

Lambda関数は自動的に更新されます。

### 環境変数の更新

```bash
aws lambda update-function-configuration \
  --function-name estat-mcp-server \
  --environment "Variables={ESTAT_APP_ID=new_api_key}" \
  --region ap-northeast-1
```

---

## 🗑️ 削除方法

### Lambda + API Gateway

```bash
# Lambda関数の削除
aws lambda delete-function \
  --function-name estat-mcp-server \
  --region ap-northeast-1

# API Gatewayの削除
aws apigateway delete-rest-api \
  --rest-api-id your-api-id \
  --region ap-northeast-1

# IAMロールの削除
aws iam detach-role-policy \
  --role-name estat-mcp-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam delete-role \
  --role-name estat-mcp-lambda-role
```

### App Runner

```bash
aws apprunner delete-service \
  --service-arn your-service-arn \
  --region ap-northeast-1
```

---

## 🆘 トラブルシューティング

### エラー: "User is not authorized"

**原因:** AWS認証情報が正しくない

**解決方法:**
```bash
aws configure
# 正しいAccess KeyとSecret Keyを入力
```

### エラー: "Role cannot be assumed"

**原因:** IAMロールの作成直後

**解決方法:**
```bash
# 10秒待ってから再実行
sleep 10
./deploy_aws_lambda.sh
```

### Lambda関数がタイムアウトする

**原因:** 処理時間が30秒を超えている

**解決方法:**
```bash
aws lambda update-function-configuration \
  --function-name estat-mcp-server \
  --timeout 60 \
  --region ap-northeast-1
```

### API Gatewayが502エラーを返す

**原因:** Lambda関数のレスポンス形式が正しくない

**解決方法:**
```bash
# CloudWatch Logsでエラーを確認
aws logs tail /aws/lambda/estat-mcp-server --follow
```

---

## 💡 ベストプラクティス

### 1. リージョンの選択

- **ap-northeast-1（東京）:** 日本からのアクセスに最適
- **us-east-1（バージニア）:** グローバル展開に最適

### 2. コスト最適化

- Lambda: メモリサイズを最適化（512MB推奨）
- API Gateway: キャッシュを有効化
- CloudWatch: ログ保持期間を設定（7日推奨）

### 3. セキュリティ

- Parameter Storeで機密情報を管理
- API認証を有効化
- VPC内にLambdaを配置（オプション）

### 4. モニタリング

- CloudWatch Alarmsを設定
- エラー率が5%を超えたら通知
- レスポンスタイムが3秒を超えたら通知

---

## 📚 関連ドキュメント

- [AWS完全デプロイガイド](AWS_DEPLOYMENT_GUIDE.md)
- [クラウドデプロイガイド](CLOUD_DEPLOYMENT_GUIDE.md)
- [セキュリティ設定](AWS_DEPLOYMENT_GUIDE.md#7-セキュリティ設定)

---

## 🎉 まとめ

| やりたいこと | 推奨方法 | コマンド |
|------------|---------|---------|
| 最も簡単にデプロイ | App Runner | `./deploy_aws_apprunner.sh` |
| コストを抑えたい | Lambda | `./deploy_aws_lambda.sh` |
| 本格的に運用 | ECS Fargate | [詳細ガイド参照](AWS_DEPLOYMENT_GUIDE.md) |

**まずはLambdaから始めることをお勧めします！**

無料枠が充実しており、小〜中規模なら完全無料で運用できます。

```bash
export ESTAT_APP_ID="your_api_key"
./deploy_aws_lambda.sh
```

Good luck! 🚀
