# MCPのHTTPトランスポート（url/httpUrl型）への移行ガイド

## 概要

e-Stat AWS MCPサーバーを **command/args型（ローカルプロセス）** から **url/httpUrl型（HTTPトランスポート）** に移行しました。

## 変更内容

### 1. トランスポート方式の違い

#### 従来（command/args型）
```
Kiro → python3 mcp_aws_wrapper.py (ローカル) → HTTP → ECS Fargate
```
- Kiroがローカルでwrapperプロセスを起動
- wrapperがHTTP経由でECSに接続
- ローカルにPython環境が必要

#### 新方式（url/httpUrl型）
```
Kiro → HTTP (streamable-http) → ECS Fargate (直接)
```
- Kiroが直接HTTPでECSに接続
- ローカルプロセス不要
- `mcp_aws_wrapper.py` 不要

### 2. 実装の変更

#### server_http.py
- **FastMCP SDK** を使用してMCPのHTTPトランスポート仕様に準拠
- `@mcp.tool()` デコレーターでツールを登録
- `mcp.run(transport="streamable-http")` でサーバー起動

#### 環境変数の追加
```bash
TRANSPORT_MODE=streamable-http
TRANSPORT_HOST=0.0.0.0
PORT=8080
MCP_SESSION_MODE=stateless
```

#### requirements.txt
```
mcp>=1.0.0  # FastMCP SDK
```

### 3. Kiro設定の変更

#### 従来の設定（.kiro/settings/mcp.json）
```json
{
  "mcpServers": {
    "estat-aws": {
      "command": "python3",
      "args": ["mcp_aws_wrapper.py"],
      "env": { ... }
    }
  }
}
```

#### 新しい設定
```json
{
  "mcpServers": {
    "estat-aws-remote": {
      "transport": "streamable-http",
      "url": "http://estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com/mcp",
      "disabled": false,
      "autoApprove": [
        "search_estat_data",
        "apply_keyword_suggestions",
        "fetch_dataset_auto",
        "fetch_large_dataset_complete",
        "fetch_dataset_filtered",
        "transform_to_parquet",
        "load_to_iceberg",
        "analyze_with_athena",
        "save_dataset_as_csv",
        "download_csv_from_s3"
      ]
    }
  }
}
```

## デプロイ手順

### 1. 更新スクリプトの実行

```bash
./update_ecs_mcp.sh
```

このスクリプトは以下を実行します:
1. Dockerイメージをビルド（amd64アーキテクチャ）
2. ECRにログイン
3. イメージをECRにプッシュ
4. タスク定義を更新
5. ECSサービスを更新（新しいデプロイを強制）
6. デプロイ完了を待機

### 2. 動作確認

#### ヘルスチェック
```bash
curl http://estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com/health
```

期待される出力:
```json
{
  "status": "ok",
  "service": "estat-aws",
  "transport": "streamable-http"
}
```

#### Kiroでの確認
1. Kiroを再起動
2. MCPサーバーが接続されていることを確認
3. 「東京都の人口データを検索してください」などのクエリを試す

### 3. ログ確認

```bash
aws logs tail /ecs/estat-mcp --follow --region ap-northeast-1
```

## メリット

### 1. シンプルな構成
- ローカルプロセス不要
- `mcp_aws_wrapper.py` 不要
- Python環境の依存関係が減少

### 2. 標準準拠
- MCPの公式HTTPトランスポート仕様に準拠
- 他のMCPクライアントとの互換性向上

### 3. スケーラビリティ
- ECS Fargateで自動スケーリング可能
- 複数のクライアントから同時接続可能

### 4. 保守性
- 設定がシンプル
- デバッグが容易

## トラブルシューティング

### 問題1: 接続できない

**確認事項:**
1. ECSタスクが実行中か確認
   ```bash
   aws ecs describe-services \
     --cluster estat-mcp-cluster \
     --services estat-mcp-service \
     --region ap-northeast-1
   ```

2. ALBのヘルスチェックが成功しているか確認
   ```bash
   aws elbv2 describe-target-health \
     --target-group-arn arn:aws:elasticloadbalancing:ap-northeast-1:639135896267:targetgroup/estat-mcp-tg/11ae590cef59f39f \
     --region ap-northeast-1
   ```

3. セキュリティグループでポート80が開いているか確認

### 問題2: ツールが表示されない

**確認事項:**
1. FastMCP SDKがインストールされているか
   ```bash
   docker exec <container-id> pip list | grep mcp
   ```

2. ログでエラーが出ていないか確認
   ```bash
   aws logs tail /ecs/estat-mcp --region ap-northeast-1
   ```

### 問題3: タイムアウトエラー

**確認事項:**
1. ALBのタイムアウト設定を確認（デフォルト60秒）
2. 必要に応じてタイムアウトを延長
   ```bash
   aws elbv2 modify-target-group-attributes \
     --target-group-arn <ARN> \
     --attributes Key=deregistration_delay.timeout_seconds,Value=300 \
     --region ap-northeast-1
   ```

## ロールバック方法

もし問題が発生した場合、従来の方式に戻すことができます:

1. `.kiro/settings/mcp.json` を編集
   ```json
   {
     "mcpServers": {
       "estat-aws-local": {
         "command": "python3",
         "args": ["mcp_aws_wrapper.py"],
         "disabled": false
       },
       "estat-aws-remote": {
         "disabled": true
       }
     }
   }
   ```

2. Kiroを再起動

## 参考資料

- [MCP公式ドキュメント](https://modelcontextprotocol.io/)
- [FastMCP SDK](https://github.com/jlowin/fastmcp)
- [Terraform MCP ServerをECSにデプロイ](https://dev.classmethod.jp/articles/terraform-mcp-ecs-deploy-remote/)
- [リモートMCPサーバーをECSでたててみよう](https://qiita.com/yu-Matsu/items/f27ab9ecf3b9979fa5fb)

## まとめ

| 項目 | command/args型 | url/httpUrl型 |
|------|---------------|---------------|
| **接続方式** | ローカルプロセス + HTTP | HTTP直接 |
| **ローカル環境** | Python必要 | 不要 |
| **設定** | command + args | transport + url |
| **スケーラビリティ** | 低 | 高 |
| **保守性** | 中 | 高 |
| **標準準拠** | 部分的 | 完全 |

url/httpUrl型への移行により、よりシンプルで標準準拠したMCPサーバー構成になりました。
