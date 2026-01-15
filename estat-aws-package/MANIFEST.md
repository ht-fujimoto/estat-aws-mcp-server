# estat-aws パッケージマニフェスト

## 📦 パッケージ構成

### 必須ファイル（方法1: 既存サービス使用）

```
estat-aws-package/
├── mcp_aws_wrapper.py                 # MCPブリッジ（必須）
└── .kiro/settings/
    └── mcp.json.example               # Kiro設定サンプル
```

**サイズ**: 約10 KB  
**用途**: 既存のECS Fargateサービスを使用する場合

---

### 完全パッケージ（方法2: 独自デプロイ）

```
estat-aws-package/
├── README.md                          # パッケージ説明
├── MANIFEST.md                        # このファイル
├── .env.example                       # 環境変数サンプル
│
├── mcp_aws_wrapper.py                 # MCPブリッジ
├── test_estat_aws_setup.sh            # セットアップテスト
│
├── .kiro/settings/
│   └── mcp.json.example               # Kiro設定サンプル
│
├── mcp_servers/estat_aws/             # MCPサーバー実装
│   ├── __init__.py
│   ├── server.py                      # メインサーバー（1,200行）
│   ├── keyword_dictionary.py          # 統計用語辞書（134用語）
│   ├── tests/
│   │   └── __init__.py
│   └── utils/
│       ├── __init__.py
│       ├── error_handler.py           # エラーハンドリング
│       ├── retry.py                   # リトライロジック
│       ├── logger.py                  # ロギング
│       └── response_formatter.py      # レスポンス形式統一
│
├── server_http.py                     # HTTPラッパー（350行）
├── Dockerfile                         # Docker設定
├── requirements.txt                   # Python依存関係
├── task-definition.json               # ECSタスク定義
├── deploy_ecs_fargate.sh              # デプロイスクリプト
│
└── docs/                              # ドキュメント
    ├── ESTAT_AWS_QUICK_START.md       # クイックスタート
    ├── ESTAT_AWS_SETUP_GUIDE.md       # 完全セットアップガイド
    ├── ESTAT_AWS_DEPLOYMENT_SUMMARY.md # 全体サマリー
    ├── KYOTO_LABOR_DATA_FULL_TEST_REPORT.md
    └── FIXED_TOOLS_TEST_REPORT.md
```

**総サイズ**: 約500 KB  
**総行数**: 約2,030行  
**ファイル数**: 24ファイル

---

## 📊 ファイル詳細

### コアファイル

| ファイル | 行数 | サイズ | 説明 |
|---------|------|--------|------|
| mcp_aws_wrapper.py | 180 | 6 KB | MCPプロトコルブリッジ |
| mcp_servers/estat_aws/server.py | 1,200 | 50 KB | 全10ツール実装 |
| server_http.py | 350 | 15 KB | HTTPラッパー |
| keyword_dictionary.py | 150 | 8 KB | 統計用語辞書（134用語） |

### ユーティリティ

| ファイル | 行数 | サイズ | 説明 |
|---------|------|--------|------|
| utils/error_handler.py | 80 | 3 KB | エラーハンドリング |
| utils/retry.py | 60 | 2 KB | リトライロジック |
| utils/logger.py | 50 | 2 KB | ロギング設定 |
| utils/response_formatter.py | 40 | 2 KB | レスポンス形式統一 |

### 設定ファイル

| ファイル | サイズ | 説明 |
|---------|--------|------|
| .kiro/settings/mcp.json.example | 1 KB | Kiro設定サンプル |
| .env.example | 0.5 KB | 環境変数サンプル |
| requirements.txt | 0.5 KB | Python依存関係 |
| Dockerfile | 1 KB | Docker設定 |
| task-definition.json | 2 KB | ECSタスク定義 |

### ドキュメント

| ファイル | サイズ | 説明 |
|---------|--------|------|
| README.md | 8 KB | パッケージ説明 |
| docs/ESTAT_AWS_QUICK_START.md | 12 KB | クイックスタート |
| docs/ESTAT_AWS_SETUP_GUIDE.md | 35 KB | 完全セットアップガイド |
| docs/ESTAT_AWS_DEPLOYMENT_SUMMARY.md | 20 KB | 全体サマリー |
| docs/KYOTO_LABOR_DATA_FULL_TEST_REPORT.md | 15 KB | テストレポート |
| docs/FIXED_TOOLS_TEST_REPORT.md | 18 KB | 修正レポート |

### スクリプト

| ファイル | サイズ | 説明 |
|---------|--------|------|
| test_estat_aws_setup.sh | 5 KB | セットアップテスト |
| deploy_ecs_fargate.sh | 8 KB | デプロイスクリプト |

---

## 🎯 使用方法別の必要ファイル

### 方法1: 既存サービス使用（推奨）

**必要なファイル**:
- ✅ mcp_aws_wrapper.py
- ✅ .kiro/settings/mcp.json.example → mcp.json

**オプション**:
- test_estat_aws_setup.sh（動作確認用）
- docs/ESTAT_AWS_QUICK_START.md（手順書）

**総サイズ**: 約10 KB

---

### 方法2: 独自AWS環境にデプロイ

**必要なファイル**:
- ✅ 全ファイル

**総サイズ**: 約500 KB

---

### 方法3: ローカル開発環境

**必要なファイル**:
- ✅ mcp_servers/estat_aws/ （全ファイル）
- ✅ server_http.py
- ✅ requirements.txt
- ✅ mcp_aws_wrapper.py
- ✅ .kiro/settings/mcp.json.example → mcp.json

**オプション**:
- .env.example → .env（環境変数管理用）

**総サイズ**: 約100 KB

---

## 📋 依存関係

### Python依存関係（requirements.txt）

```
aiohttp>=3.9.0
requests>=2.31.0
pandas>=2.1.0
pyarrow>=14.0.0
boto3>=1.34.0
```

### システム要件

- Python 3.11以上
- Kiro IDE
- e-Stat APIキー

### AWS要件（方法2のみ）

- AWSアカウント
- AWS CLI設定済み
- 以下のサービスへのアクセス権限：
  - ECS
  - ECR
  - ALB
  - IAM
  - S3
  - Athena
  - Glue

---

## 🔐 セキュリティ

### 機密情報

以下のファイルには機密情報が含まれる可能性があります：

- `.kiro/settings/mcp.json` - e-Stat APIキー
- `.env` - 環境変数
- `task-definition.json` - AWSアカウント情報

**重要**: これらのファイルをGitにコミットしないでください！

### .gitignore推奨設定

```gitignore
# 機密情報
.kiro/settings/mcp.json
.env

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# AWS
task-definition.json
```

---

## 📦 配布方法

### ZIP形式で配布

```bash
# パッケージをZIP化
zip -r estat-aws-package.zip estat-aws-package/ \
  -x "*.pyc" -x "*__pycache__*" -x "*.DS_Store"
```

### Git経由で配布

```bash
# リポジトリをクローン
git clone <repository-url>
cd estat-aws-package

# 設定ファイルを作成
cp .kiro/settings/mcp.json.example .kiro/settings/mcp.json
cp .env.example .env

# APIキーを設定
# mcp.json と .env を編集
```

---

## ✅ チェックリスト

### 配布前

- [ ] 機密情報を削除した
- [ ] .example ファイルを用意した
- [ ] README.md を更新した
- [ ] ドキュメントを確認した
- [ ] test_estat_aws_setup.sh が動作する

### 受け取り後

- [ ] パッケージを展開した
- [ ] README.md を読んだ
- [ ] .example ファイルをコピーした
- [ ] APIキーを設定した
- [ ] test_estat_aws_setup.sh を実行した

---

**バージョン**: 1.1.0  
**最終更新**: 2026年1月9日  
**パッケージサイズ**: 約500 KB  
**ファイル数**: 24ファイル
