# MCPサーバー デプロイメント オプション 完全ガイド

## 📦 2つの配布方法

### 方法A: パッケージとして配布
ユーザーが各自の環境にインストールして使用

### 方法B: クラウドサーバーとして提供
中央サーバーを立てて、どこからでもアクセス可能

---

## 🎯 方法A: パッケージ配布

### A-1: PyPIで公開

**メリット:**
- ✅ `pip install estat-mcp-server`で簡単インストール
- ✅ 広く配布できる
- ✅ バージョン管理が容易

**手順:**
```bash
./reorganize_package.sh
./build_and_publish.sh
```

**ユーザー側の設定:**
```json
{
  "mcpServers": {
    "estat": {
      "command": "python",
      "args": ["-m", "estat_mcp_server.server"],
      "env": {"ESTAT_APP_ID": "user_api_key"}
    }
  }
}
```

**詳細:** [MCP_DEPLOYMENT_GUIDE.md](MCP_DEPLOYMENT_GUIDE.md)

---

### A-2: GitHubで公開

**メリット:**
- ✅ 無料
- ✅ オープンソース
- ✅ Issue管理

**手順:**
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/user/estat-mcp-server.git
git push -u origin main
```

**ユーザー側のインストール:**
```bash
pip install git+https://github.com/user/estat-mcp-server.git
```

**詳細:** [MCP_DEPLOYMENT_GUIDE.md](MCP_DEPLOYMENT_GUIDE.md)

---

### A-3: ローカル配布

**メリット:**
- ✅ 即座に利用可能
- ✅ カスタマイズ容易

**手順:**
```bash
pip install -e .
```

**詳細:** [QUICK_START.md](QUICK_START.md)

---

## 🌐 方法B: クラウドサーバー

### B-1: Google Cloud Run（推奨）

**メリット:**
- ✅ 最も簡単（5分でデプロイ）
- ✅ 無料枠: 200万リクエスト/月
- ✅ 自動スケーリング
- ✅ HTTPS自動設定

**コスト:** 月$0〜（無料枠内なら完全無料）

**手順:**
```bash
export ESTAT_APP_ID="your_api_key"
export GCP_PROJECT_ID="your-project-id"
./deploy_cloud_run.sh
```

**ユーザー側の設定:**
```json
{
  "mcpServers": {
    "estat-cloud": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "https://your-service.run.app/execute",
        "-H", "Content-Type: application/json",
        "-d", "@-"
      ]
    }
  }
}
```

**詳細:** [CLOUD_QUICK_START.md](CLOUD_QUICK_START.md)

---

### B-2: Heroku

**メリット:**
- ✅ Git pushだけでデプロイ
- ✅ 簡単な管理画面
- ✅ 無料枠: 550時間/月

**コスト:** 月$0〜$7

**手順:**
```bash
export ESTAT_APP_ID="your_api_key"
./deploy_heroku.sh
```

**詳細:** [CLOUD_QUICK_START.md](CLOUD_QUICK_START.md)

---

### B-3: AWS Lambda + API Gateway

**メリット:**
- ✅ サーバーレス
- ✅ 無料枠: 100万リクエスト/月
- ✅ 従量課金

**コスト:** 月$0〜

**詳細:** [CLOUD_DEPLOYMENT_GUIDE.md](CLOUD_DEPLOYMENT_GUIDE.md#2-aws-lambda--api-gateway)

---

### B-4: Docker + VPS/EC2

**メリット:**
- ✅ フルコントロール
- ✅ カスタマイズ自由
- ✅ 長期運用に適している

**コスト:** 月$5〜（VPS代）

**手順:**
```bash
export ESTAT_APP_ID="your_api_key"
./deploy_docker.sh
```

**詳細:** [CLOUD_DEPLOYMENT_GUIDE.md](CLOUD_DEPLOYMENT_GUIDE.md#6-docker--ec2vps)

---

## 📊 比較表

### パッケージ配布 vs クラウドサーバー

| 項目 | パッケージ配布 | クラウドサーバー |
|------|--------------|----------------|
| **セットアップ** | ユーザーごと | 1回だけ |
| **管理** | ユーザー各自 | 管理者が一元管理 |
| **更新** | ユーザーが手動 | 自動反映 |
| **コスト** | 無料 | 月$0〜 |
| **スケーラビリティ** | ユーザー環境依存 | 自動スケール |
| **セキュリティ** | ユーザー管理 | 中央管理 |
| **カスタマイズ** | 容易 | 制限あり |

### クラウドサービス比較

| サービス | 難易度 | 無料枠 | 月額コスト | 推奨用途 |
|---------|--------|--------|-----------|----------|
| **Google Cloud Run** | ⭐ | 200万req | $0〜 | 個人〜中規模 |
| **Heroku** | ⭐ | 550時間 | $0〜$7 | 小規模 |
| **AWS Lambda** | ⭐⭐ | 100万req | $0〜 | 大規模 |
| **AWS ECS** | ⭐⭐⭐ | なし | $20〜 | 本格運用 |
| **VPS/EC2** | ⭐⭐ | なし | $5〜 | 長期運用 |

---

## 🎯 推奨デプロイ方法

### 個人利用
→ **パッケージ配布（ローカル）**
- 最も簡単
- コスト0円
- カスタマイズ自由

### 小規模チーム（5-10人）
→ **Google Cloud Run**
- 無料枠で十分
- 管理が簡単
- 自動スケール

### 中規模組織（10-100人）
→ **Google Cloud Run** または **AWS Lambda**
- 従量課金で経済的
- 高可用性
- モニタリング充実

### 大規模組織（100人以上）
→ **AWS ECS/Fargate** または **Kubernetes**
- 本格的な運用
- 高度なカスタマイズ
- エンタープライズサポート

### オープンソースプロジェクト
→ **PyPI + GitHub**
- 広く配布
- コミュニティ貢献
- Issue管理

---

## 🚀 最速スタートガイド

### パターン1: 今すぐ使いたい（5分）

```bash
# ローカルインストール
pip install -e .

# Kiro設定
# ~/.kiro/settings/mcp.json に追加
```

### パターン2: チームで共有したい（10分）

```bash
# Google Cloud Runにデプロイ
export ESTAT_APP_ID="your_api_key"
export GCP_PROJECT_ID="your-project-id"
./deploy_cloud_run.sh

# URLをチームに共有
```

### パターン3: 世界に公開したい（30分）

```bash
# PyPIに公開
./reorganize_package.sh
./build_and_publish.sh

# GitHubに公開
git init
git add .
git commit -m "Initial commit"
git push
```

---

## 📁 ファイル構成

### パッケージ配布用
```
├── pyproject.toml          # パッケージメタデータ
├── setup.py                # セットアップスクリプト
├── reorganize_package.sh   # パッケージ構造整理
├── build_and_publish.sh    # ビルド・公開
└── estat_mcp_server/       # パッケージディレクトリ
```

### クラウドデプロイ用
```
├── Dockerfile              # Dockerイメージ定義
├── docker-compose.yml      # Docker Compose設定
├── server_http.py          # HTTPサーバー
├── nginx.conf              # Nginx設定
├── Procfile                # Heroku設定
├── deploy_cloud_run.sh     # Cloud Runデプロイ
├── deploy_heroku.sh        # Herokuデプロイ
└── deploy_docker.sh        # Dockerデプロイ
```

---

## 🔐 セキュリティ考慮事項

### パッケージ配布
- ✅ ユーザーが各自のAPIキーを管理
- ✅ ローカル実行で安全
- ⚠️ ユーザーのセキュリティ意識に依存

### クラウドサーバー
- ✅ 中央でセキュリティ管理
- ✅ HTTPS通信
- ✅ API認証追加可能
- ⚠️ サーバー管理が必要

---

## 💰 コスト試算

### パッケージ配布
- **開発コスト:** 0円
- **運用コスト:** 0円
- **ユーザーコスト:** 0円（各自のe-Stat APIキーのみ）

### クラウドサーバー（Google Cloud Run）

**小規模（月1万リクエスト）:**
- 無料枠内 → **0円**

**中規模（月100万リクエスト）:**
- 無料枠200万以内 → **0円**

**大規模（月500万リクエスト）:**
- 超過分300万 × $0.40/100万 = **$1.20/月**

---

## 🎓 学習パス

### 初心者
1. ローカルでパッケージインストール
2. 動作確認
3. 必要に応じてクラウドデプロイ

### 中級者
1. GitHubで公開
2. Google Cloud Runにデプロイ
3. カスタムドメイン設定

### 上級者
1. PyPIに公開
2. AWS ECS/Fargateにデプロイ
3. CI/CD構築
4. モニタリング・アラート設定

---

## 📚 関連ドキュメント

### パッケージ配布
- [START_HERE.md](START_HERE.md) - 最初に読むガイド
- [PACKAGE_SUMMARY.md](PACKAGE_SUMMARY.md) - パッケージ配布の概要
- [MCP_DEPLOYMENT_GUIDE.md](MCP_DEPLOYMENT_GUIDE.md) - 詳細ガイド
- [QUICK_START.md](QUICK_START.md) - クイックスタート
- [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) - チェックリスト

### クラウドデプロイ
- [CLOUD_QUICK_START.md](CLOUD_QUICK_START.md) - クラウドクイックスタート
- [CLOUD_DEPLOYMENT_GUIDE.md](CLOUD_DEPLOYMENT_GUIDE.md) - クラウド詳細ガイド

---

## 🤔 どちらを選ぶべき？

### パッケージ配布を選ぶべき場合
- ✅ 個人利用
- ✅ カスタマイズが必要
- ✅ コストを抑えたい
- ✅ オープンソースとして公開したい

### クラウドサーバーを選ぶべき場合
- ✅ チームで共有したい
- ✅ 一元管理したい
- ✅ 自動スケールが必要
- ✅ ユーザーのセットアップを簡単にしたい

### 両方やる場合
- ✅ 最大の柔軟性
- ✅ ユーザーが選択可能
- ✅ 推奨アプローチ！

---

## 🎉 まとめ

| やりたいこと | 推奨方法 | 所要時間 | コスト |
|------------|---------|---------|--------|
| 今すぐ使いたい | ローカルインストール | 5分 | 0円 |
| チームで共有 | Google Cloud Run | 10分 | 0円〜 |
| 世界に公開 | PyPI + GitHub | 30分 | 0円 |
| 本格運用 | AWS ECS + PyPI | 2時間 | $20〜/月 |

**どの方法も、このリポジトリに必要なファイルがすべて揃っています！**

---

準備はできましたか？

- パッケージ配布 → [START_HERE.md](START_HERE.md)
- クラウドデプロイ → [CLOUD_QUICK_START.md](CLOUD_QUICK_START.md)

Good luck! 🚀
