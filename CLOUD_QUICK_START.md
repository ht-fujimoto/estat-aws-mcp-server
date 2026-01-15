# クラウドデプロイ クイックスタート

MCPサーバーをクラウドにデプロイして、どこからでもアクセスできるようにする最速の方法。

## 🎯 3つの選択肢

### 1️⃣ Google Cloud Run（最も簡単・推奨）

**所要時間: 5分**

```bash
# 環境変数を設定
export ESTAT_APP_ID="your_api_key"
export GCP_PROJECT_ID="your-project-id"

# デプロイ実行
./deploy_cloud_run.sh
```

**メリット:**
- ✅ 最も簡単（コマンド1つ）
- ✅ 無料枠あり
- ✅ 自動スケーリング
- ✅ HTTPS自動設定

**コスト:** 月$0〜（無料枠: 200万リクエスト/月）

---

### 2️⃣ Heroku（Git pushだけ）

**所要時間: 10分**

```bash
# 環境変数を設定
export ESTAT_APP_ID="your_api_key"
export HEROKU_APP_NAME="your-app-name"

# デプロイ実行
./deploy_heroku.sh
```

**メリット:**
- ✅ Git pushだけでデプロイ
- ✅ 簡単な管理画面
- ✅ 無料枠あり（制限付き）

**コスト:** 月$0〜$7（無料枠: 550時間/月）

---

### 3️⃣ Docker（ローカル/VPS）

**所要時間: 15分**

```bash
# 環境変数を設定
export ESTAT_APP_ID="your_api_key"

# ローカルでテスト
./deploy_docker.sh

# VPS/EC2にデプロイする場合
scp -r . user@your-server:/path/to/app
ssh user@your-server "cd /path/to/app && ./deploy_docker.sh"
```

**メリット:**
- ✅ フルコントロール
- ✅ どこでも動く
- ✅ カスタマイズ自由

**コスト:** VPS代（月$5〜）

---

## 📋 事前準備

### 必須
- [ ] e-Stat APIキー（[取得方法](https://www.e-stat.go.jp/api/)）
- [ ] ターミナル/コマンドライン

### Google Cloud Runの場合
- [ ] [Google Cloud アカウント](https://cloud.google.com/)
- [ ] [gcloud CLI](https://cloud.google.com/sdk/docs/install)

### Herokuの場合
- [ ] [Herokuアカウント](https://signup.heroku.com/)
- [ ] [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli)

### Dockerの場合
- [ ] [Docker](https://docs.docker.com/get-docker/)
- [ ] [Docker Compose](https://docs.docker.com/compose/install/)

---

## 🚀 最速デプロイ（Google Cloud Run）

### ステップ1: Google Cloud SDKのインストール

**Mac:**
```bash
brew install --cask google-cloud-sdk
```

**Linux:**
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

**Windows:**
[インストーラーをダウンロード](https://cloud.google.com/sdk/docs/install)

### ステップ2: 初期設定

```bash
# ログイン
gcloud auth login

# プロジェクト作成（初回のみ）
gcloud projects create your-project-id --name="e-Stat MCP Server"

# プロジェクト設定
gcloud config set project your-project-id
```

### ステップ3: デプロイ

```bash
# 環境変数を設定
export ESTAT_APP_ID="your_estat_api_key"
export GCP_PROJECT_ID="your-project-id"

# デプロイスクリプトを実行
chmod +x deploy_cloud_run.sh
./deploy_cloud_run.sh
```

### ステップ4: 完了！

デプロイが完了すると、URLが表示されます：
```
Service URL: https://estat-mcp-server-xxxxx-an.a.run.app
```

---

## 🧪 動作確認

### ヘルスチェック

```bash
curl https://your-service-url/health
```

**期待される出力:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-08T12:00:00"
}
```

### ツール一覧の取得

```bash
curl https://your-service-url/tools
```

### ツールの実行

```bash
curl -X POST https://your-service-url/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "search_estat_data",
    "arguments": {
      "query": "人口",
      "max_results": 5
    }
  }'
```

---

## ⚙️ Kiro/Clineでの設定

デプロイ完了後、Kiro/Clineの設定ファイルを更新：

### Kiro設定（~/.kiro/settings/mcp.json）

```json
{
  "mcpServers": {
    "estat-cloud": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "https://your-service-url/execute",
        "-H", "Content-Type: application/json",
        "-d", "@-"
      ],
      "disabled": false
    }
  }
}
```

### Cline設定（.cline/mcp.json）

```json
{
  "mcpServers": {
    "estat-cloud": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "https://your-service-url/execute",
        "-H", "Content-Type: application/json",
        "-d", "@-"
      ]
    }
  }
}
```

---

## 💰 コスト比較

| サービス | 無料枠 | 有料プラン | 推奨用途 |
|---------|--------|-----------|----------|
| **Google Cloud Run** | 200万リクエスト/月 | $0.40/100万リクエスト | 個人〜中規模 |
| **Heroku** | 550時間/月 | $7/月〜 | 小規模 |
| **AWS Lambda** | 100万リクエスト/月 | $0.20/100万リクエスト | 大規模 |
| **VPS (DigitalOcean)** | なし | $5/月〜 | 長期運用 |

---

## 🔒 セキュリティ設定（オプション）

### API認証の追加

環境変数にAPIキーを追加：

```bash
# Google Cloud Run
gcloud run services update estat-mcp-server \
  --update-env-vars MCP_API_KEY=your_secret_key

# Heroku
heroku config:set MCP_API_KEY=your_secret_key
```

クライアント側でAPIキーを送信：

```json
{
  "mcpServers": {
    "estat-cloud": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "https://your-service-url/execute",
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

### Google Cloud Run

```bash
# ログの確認
gcloud run services logs read estat-mcp-server --region asia-northeast1

# メトリクスの確認
gcloud run services describe estat-mcp-server --region asia-northeast1
```

### Heroku

```bash
# ログの確認
heroku logs --tail --app your-app-name

# メトリクスの確認
heroku ps --app your-app-name
```

### Docker

```bash
# ログの確認
docker-compose logs -f

# コンテナの状態確認
docker-compose ps
```

---

## 🆘 トラブルシューティング

### デプロイが失敗する

**Google Cloud Run:**
```bash
# APIが有効か確認
gcloud services list --enabled

# Cloud Run APIを有効化
gcloud services enable run.googleapis.com
```

**Heroku:**
```bash
# ログを確認
heroku logs --tail --app your-app-name

# ビルドパックを確認
heroku buildpacks --app your-app-name
```

### サービスが起動しない

```bash
# ヘルスチェックを確認
curl https://your-service-url/health

# ログを確認（各サービスのログコマンドを使用）
```

### 環境変数が反映されない

```bash
# Google Cloud Run
gcloud run services describe estat-mcp-server --region asia-northeast1 --format="value(spec.template.spec.containers[0].env)"

# Heroku
heroku config --app your-app-name
```

---

## 🎉 次のステップ

デプロイが完了したら：

1. ✅ Kiro/Clineで動作確認
2. ✅ カスタムドメインの設定（オプション）
3. ✅ モニタリングの設定
4. ✅ バックアップの設定

---

## 📚 詳細ドキュメント

- [完全なクラウドデプロイガイド](CLOUD_DEPLOYMENT_GUIDE.md)
- [セキュリティ設定](CLOUD_DEPLOYMENT_GUIDE.md#7-セキュリティ設定)
- [コスト最適化](CLOUD_DEPLOYMENT_GUIDE.md#82-コスト最適化)

---

**準備はできましたか？**

まずは **Google Cloud Run** で試してみましょう！
最も簡単で、無料枠も充実しています。

```bash
export ESTAT_APP_ID="your_api_key"
export GCP_PROJECT_ID="your-project-id"
./deploy_cloud_run.sh
```

Good luck! 🚀
