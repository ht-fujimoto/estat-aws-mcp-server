# 🎉 AWS Lambda デプロイ成功！

## ✅ デプロイ完了

MCPサーバーがAWS Lambda + API Gatewayに正常にデプロイされました。

### 📊 デプロイ情報

- **Lambda関数名**: estat-mcp-server
- **API ID**: pc6a551m8k
- **リージョン**: ap-northeast-1（東京）
- **API URL**: https://pc6a551m8k.execute-api.ap-northeast-1.amazonaws.com/prod

### ✅ 動作確認済み

- ヘルスチェック: ✅ 正常
- ツール一覧取得: ✅ 正常

## 🔧 Kiro設定

`~/.kiro/settings/mcp.json`に以下を追加してください：

```json
{
  "mcpServers": {
    "estat-aws": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "https://pc6a551m8k.execute-api.ap-northeast-1.amazonaws.com/prod/execute",
        "-H", "Content-Type: application/json",
        "-d", "@-"
      ],
      "disabled": false
    }
  }
}
```

## 🧪 テストコマンド

### ヘルスチェック
```bash
curl https://pc6a551m8k.execute-api.ap-northeast-1.amazonaws.com/prod/health
```

### ツール一覧
```bash
curl https://pc6a551m8k.execute-api.ap-northeast-1.amazonaws.com/prod/tools
```

### データ検索（例）
```bash
curl -X POST https://pc6a551m8k.execute-api.ap-northeast-1.amazonaws.com/prod/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "tool_name": "search_estat_data",
    "arguments": {
      "query": "世田谷区 人口",
      "max_results": 5
    }
  }'
```

## 📊 作成されたAWSリソース

1. **IAMロール**: estat-mcp-lambda-role
   - Lambda実行権限
   - S3アクセス権限
   - Systems Manager読み取り権限

2. **Lambda関数**: estat-mcp-server
   - ランタイム: Python 3.11
   - メモリ: 512 MB
   - タイムアウト: 30秒

3. **Lambda Layer**: estat-mcp-dependencies (version 2)
   - requests
   - boto3

4. **API Gateway**: estat-mcp-api
   - REST API
   - プロキシ統合
   - CORS有効

5. **Parameter Store**: /estat-mcp/api-key
   - e-Stat APIキー（暗号化済み）

## 💰 コスト見積もり

### 無料枠（12ヶ月間）
- Lambda: 月100万リクエスト
- API Gateway: 月100万リクエスト

### 無料枠超過後
- Lambda: $0.20/100万リクエスト
- API Gateway: $3.50/100万リクエスト

**予想コスト（月10万リクエスト）**: $0（無料枠内）

## 🔗 AWS Console リンク

- [Lambda関数](https://ap-northeast-1.console.aws.amazon.com/lambda/home?region=ap-northeast-1#/functions/estat-mcp-server)
- [API Gateway](https://ap-northeast-1.console.aws.amazon.com/apigateway/home?region=ap-northeast-1#/apis/pc6a551m8k)
- [CloudWatch Logs](https://ap-northeast-1.console.aws.amazon.com/cloudwatch/home?region=ap-northeast-1#logsV2:log-groups/log-group/$252Faws$252Flambda$252Festat-mcp-server)

## 📈 モニタリング

### CloudWatch Logsの確認
```bash
aws logs tail /aws/lambda/estat-mcp-server --follow --region ap-northeast-1
```

### メトリクスの確認
AWS Console → CloudWatch → Metrics → Lambda

## 🔄 更新方法

コードを修正した後：

```bash
# Lambda関数の更新
rm -rf lambda_package function.zip
mkdir -p lambda_package
cp lambda_handler.py lambda_package/
cd lambda_package && zip -r ../function.zip . && cd ..
aws lambda update-function-code \
  --function-name estat-mcp-server \
  --zip-file fileb://function.zip \
  --region ap-northeast-1
```

## 🗑️ 削除方法

リソースを削除する場合：

```bash
# Lambda関数の削除
aws lambda delete-function \
  --function-name estat-mcp-server \
  --region ap-northeast-1

# API Gatewayの削除
aws apigateway delete-rest-api \
  --rest-api-id pc6a551m8k \
  --region ap-northeast-1

# IAMロールの削除
aws iam detach-role-policy \
  --role-name estat-mcp-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam detach-role-policy \
  --role-name estat-mcp-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

aws iam detach-role-policy \
  --role-name estat-mcp-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess

aws iam delete-role \
  --role-name estat-mcp-lambda-role
```

## 🎯 次のステップ

1. ✅ Kiro設定を更新
2. ✅ Kiroを再起動
3. ✅ Kiroで「世田谷区の人口データを検索してください」と試す
4. ⬜ カスタムドメインの設定（オプション）
5. ⬜ CloudWatch Alarmsの設定（オプション）

---

**デプロイ完了日時**: 2026-01-08 15:51 JST
**デプロイ所要時間**: 約10分
**ステータス**: ✅ 成功
