# 更新されたKiro MCP設定

## ファイルパス
`~/.kiro/settings/mcp.json`

## 設定内容

```json
{
  "mcpServers": {
    "aws-docs": {
      "command": "uvx",
      "args": [
        "awslabs.aws-documentation-mcp-server@latest"
      ],
      "env": {
        "FASTMCP_LOG_LEVEL": "ERROR"
      },
      "disabled": false,
      "autoApprove": []
    },
    "estat-enhanced": {
      "command": "python3",
      "args": [
        "/Users/yamashitayukihiro/Desktop/estat_enhanced_mcp_package_20260105_213238/mcp_servers/estat_enhanced_analysis.py"
      ],
      "env": {
        "ESTAT_APP_ID": "320dd2fbff6974743e3f95505c9f346650ab635e",
        "S3_BUCKET": "estat-data-lake",
        "AWS_REGION": "ap-northeast-1"
      },
      "disabled": false,
      "autoApprove": [
        "search_estat_data",
        "apply_keyword_suggestions",
        "fetch_dataset_auto",
        "fetch_dataset_filtered",
        "transform_to_parquet",
        "load_to_iceberg",
        "analyze_with_athena",
        "fetch_large_dataset_complete",
        "save_dataset_as_csv",
        "download_csv_from_s3"
      ]
    },
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

## 設定されたMCPサーバー

### 1. aws-docs
- **説明**: AWS公式ドキュメントMCPサーバー
- **タイプ**: uvxパッケージ
- **ステータス**: 有効

### 2. estat-enhanced（ローカル）
- **説明**: e-Stat Enhanced Analysis（ローカル実行）
- **タイプ**: Python スクリプト
- **ステータス**: 有効
- **自動承認**: 10個のツール

### 3. estat-aws（新規追加）✨
- **説明**: e-Stat MCP Server（AWS Lambda）
- **タイプ**: クラウドAPI（curl経由）
- **エンドポイント**: https://pc6a551m8k.execute-api.ap-northeast-1.amazonaws.com/prod/execute
- **ステータス**: 有効
- **特徴**: 
  - サーバーレス
  - どこからでもアクセス可能
  - 自動スケーリング
  - 無料枠内で運用可能

## 使い分け

### estat-enhanced（ローカル）を使う場合
- ローカルで完結したい
- カスタマイズが必要
- 開発・テスト

### estat-aws（クラウド）を使う場合
- どこからでもアクセスしたい
- チームで共有したい
- サーバー管理不要
- 本番運用

## 次のステップ

1. ✅ 設定ファイルが更新されました
2. 🔄 Kiroを再起動してください
3. 🧪 以下のコマンドで試してください：
   - 「世田谷区の人口データを検索してください」
   - 「東京都の統計データを取得してください」

## 確認方法

Kiro再起動後、MCPサーバーが認識されているか確認：
- Kiroのコマンドパレットで「MCP」を検索
- または、直接データ検索を試す

## トラブルシューティング

### estat-awsが動作しない場合

1. **ネットワーク接続を確認**
   ```bash
   curl https://pc6a551m8k.execute-api.ap-northeast-1.amazonaws.com/prod/health
   ```

2. **Lambda関数の状態を確認**
   ```bash
   aws lambda get-function --function-name estat-mcp-server --region ap-northeast-1
   ```

3. **CloudWatch Logsを確認**
   ```bash
   aws logs tail /aws/lambda/estat-mcp-server --follow --region ap-northeast-1
   ```

### estat-enhancedとの違い

| 項目 | estat-enhanced | estat-aws |
|------|---------------|-----------|
| 実行場所 | ローカル | AWS Lambda |
| 起動時間 | 即座 | 初回は数秒 |
| 依存関係 | ローカルに必要 | 不要 |
| カスタマイズ | 容易 | 制限あり |
| コスト | 0円 | 0円（無料枠内） |

---

**設定完了！** 🎉

Kiroを再起動して、クラウドMCPサーバーを使ってみてください！
