# Lambda + API Gateway デプロイ チェックリスト

## ✅ 事前確認

- [x] AWS CLI インストール済み
- [x] AWS認証情報設定済み（Account: 639135896267）
- [x] Python 3.9+ インストール済み
- [x] e-Stat APIキー確認済み

## 📋 デプロイ手順

### ステップ1: 環境変数の設定

```bash
# .envファイルから読み込み
source .env

# または直接設定
export ESTAT_APP_ID="320dd2fbff6974743e3f95505c9f346650ab635e"
export AWS_REGION="ap-northeast-1"
```

### ステップ2: デプロイスクリプトの実行

```bash
./deploy_aws_lambda.sh
```

### ステップ3: デプロイ完了後の確認

1. API URLが表示される
2. ヘルスチェックを実行
3. Kiro設定を更新

## 🎯 予想される結果

デプロイが成功すると、以下のような出力が表示されます：

```
╔══════════════════════════════════════════════════════════════╗
║                  Deployment Complete! 🎉                     ║
╚══════════════════════════════════════════════════════════════╝

Service Information:
  Function Name: estat-mcp-server
  API URL: https://xxxxx.execute-api.ap-northeast-1.amazonaws.com/prod
```

## 📊 作成されるAWSリソース

1. **IAMロール**: estat-mcp-lambda-role
2. **Lambda関数**: estat-mcp-server
3. **Lambda Layer**: estat-mcp-dependencies
4. **API Gateway**: estat-mcp-api
5. **Parameter Store**: /estat-mcp/api-key

## 💰 コスト見積もり

- Lambda: 無料枠内（月100万リクエスト）
- API Gateway: 無料枠内（月100万リクエスト）
- Parameter Store: 無料
- **合計: $0/月**（無料枠内の場合）

## 🔧 トラブルシューティング

### エラー: "Role cannot be assumed"
→ 10秒待ってから再実行

### エラー: "Function already exists"
→ 既存の関数が更新されます（問題なし）

### タイムアウト
→ インターネット接続を確認

## 📞 サポート

問題が発生した場合:
1. エラーメッセージを確認
2. AWS_QUICK_START.mdのトラブルシューティングを参照
3. CloudWatch Logsを確認
