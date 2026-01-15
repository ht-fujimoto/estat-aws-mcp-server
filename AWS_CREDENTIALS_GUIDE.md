# AWS認証情報管理ガイド

## 📋 概要

このMCPサーバー（estat-aws）がAWS S3にアクセスする際の認証情報の管理方法について説明します。

---

## 🔐 現在の認証情報の保存場所

### 1. AWS標準の認証情報ファイル（推奨）

**場所**: `~/.aws/credentials`

```ini
[default]
aws_access_key_id = YOUR_AWS_ACCESS_KEY_ID
aws_secret_access_key = YOUR_AWS_SECRET_ACCESS_KEY
```

**場所**: `~/.aws/config`

```ini
[default]
region = ap-northeast-1
output = json
```

### 2. 環境変数（オプション）

`.env`ファイルには**認証情報は含まれていません**：

```bash
# .env の内容
ESTAT_APP_ID=320dd2fbff6974743e3f95505c9f346650ab635e
AWS_REGION=ap-northeast-1
S3_BUCKET=estat-data-lake
GLUE_DATABASE=estat_db
ATHENA_OUTPUT_LOCATION=s3://estat-data-lake/athena-results/
```

### 3. MCP設定ファイル

`.kiro/settings/mcp.json`にも**認証情報は含まれていません**：

```json
{
  "mcpServers": {
    "estat-aws": {
      "command": "python3",
      "args": ["mcp_aws_wrapper.py"],
      "env": {
        "ESTAT_APP_ID": "320dd2fbff6974743e3f95505c9f346650ab635e",
        "S3_BUCKET": "estat-data-lake",
        "AWS_REGION": "ap-northeast-1"
      }
    }
  }
}
```

---

## 🔍 boto3の認証情報検索順序

boto3（AWS SDK for Python）は以下の順序で認証情報を検索します：

1. **環境変数**
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_SESSION_TOKEN`（一時認証情報の場合）

2. **共有認証情報ファイル** ⭐ **現在使用中**
   - `~/.aws/credentials`
   - `~/.aws/config`

3. **IAMロール**（EC2/ECS/Lambda上で実行時）
   - インスタンスメタデータサービスから自動取得

4. **コンテナ認証情報**（ECS/Fargate上で実行時）
   - タスクロールから自動取得

---

## 🚀 他の環境でこのMCPを使用する場合

### ケース1: 同じユーザーの別マシン

**必要な情報**:
1. ✅ **e-Stat APIキー**: `ESTAT_APP_ID`
2. ✅ **AWS認証情報**: アクセスキーとシークレットキー
3. ✅ **AWS設定**: リージョン、S3バケット名

**セットアップ手順**:

```bash
# 1. AWS CLIをインストール
brew install awscli  # macOS
# または
pip install awscli

# 2. AWS認証情報を設定
aws configure
# AWS Access Key ID: YOUR_AWS_ACCESS_KEY_ID
# AWS Secret Access Key: YOUR_AWS_SECRET_ACCESS_KEY
# Default region name: ap-northeast-1
# Default output format: json

# 3. .envファイルを作成（.env.exampleをコピー）
cp .env.example .env

# 4. .envファイルを編集
# ESTAT_APP_ID=320dd2fbff6974743e3f95505c9f346650ab635e
# S3_BUCKET=estat-data-lake
# AWS_REGION=ap-northeast-1
```

### ケース2: 別のユーザー/組織

**必要な情報**:
1. ✅ **e-Stat APIキー**: 各自で取得（https://www.e-stat.go.jp/api/）
2. ✅ **AWS認証情報**: 各自のAWSアカウントで作成
3. ✅ **AWS S3バケット**: 各自で作成

**セットアップ手順**:

```bash
# 1. e-Stat APIキーを取得
# https://www.e-stat.go.jp/api/ でアカウント登録

# 2. AWSアカウントでIAMユーザーを作成
# - S3へのアクセス権限を付与
# - アクセスキーを生成

# 3. S3バケットを作成
aws s3 mb s3://your-bucket-name --region ap-northeast-1

# 4. AWS認証情報を設定
aws configure

# 5. .envファイルを編集
# ESTAT_APP_ID=your_estat_app_id
# S3_BUCKET=your-bucket-name
# AWS_REGION=ap-northeast-1

# 6. MCP設定を更新
# .kiro/settings/mcp.json の env セクションを更新
```

### ケース3: AWS ECS/Fargate上で実行

**必要な情報**:
1. ✅ **e-Stat APIキー**: 環境変数で設定
2. ❌ **AWS認証情報**: 不要（タスクロールを使用）

**セットアップ手順**:

```bash
# 1. ECSタスク定義で環境変数を設定
{
  "environment": [
    {
      "name": "ESTAT_APP_ID",
      "value": "your_estat_app_id"
    },
    {
      "name": "S3_BUCKET",
      "value": "estat-data-lake"
    },
    {
      "name": "AWS_REGION",
      "value": "ap-northeast-1"
    }
  ],
  "taskRoleArn": "arn:aws:iam::123456789012:role/ecsTaskRole"
}

# 2. タスクロールにS3アクセス権限を付与
# - AmazonS3FullAccess または
# - カスタムポリシーで必要な権限のみ
```

---

## 🔒 セキュリティのベストプラクティス

### ✅ 推奨される方法

1. **AWS認証情報ファイルを使用** (`~/.aws/credentials`)
   - ホームディレクトリに保存
   - Gitにコミットされない
   - 複数のプロファイルを管理可能

2. **環境変数を使用** (CI/CD環境)
   - `.env`ファイルは`.gitignore`に追加
   - 本番環境では環境変数で設定

3. **IAMロールを使用** (AWS上で実行)
   - 認証情報の管理不要
   - 自動ローテーション
   - 最小権限の原則

### ❌ 避けるべき方法

1. **認証情報をコードに直接記述**
   ```python
   # ❌ 絶対にやらない
   s3_client = boto3.client(
       's3',
       aws_access_key_id='YOUR_AWS_ACCESS_KEY_ID',
       aws_secret_access_key='YOUR_AWS_SECRET_ACCESS_KEY'
   )
   ```

2. **認証情報をGitにコミット**
   - `.env`ファイルは`.gitignore`に追加済み
   - `~/.aws/credentials`は自動的に除外される

3. **認証情報を共有ドキュメントに記載**
   - Slack、メール、Wikiなどに記載しない
   - 必要な場合は暗号化されたパスワードマネージャーを使用

---

## 📝 現在の設定サマリー

### 認証情報の保存場所

| 項目 | 保存場所 | 値 |
|---|---|---|
| AWS Access Key | `~/.aws/credentials` | `YOUR_AWS_ACCESS_KEY_ID` |
| AWS Secret Key | `~/.aws/credentials` | `YOUR_AWS_SECRET_ACCESS_KEY` |
| AWS Region | `~/.aws/config` | `ap-northeast-1` |
| e-Stat API Key | `.env` | `320dd2fbff6974743e3f95505c9f346650ab635e` |
| S3 Bucket | `.env` | `estat-data-lake` |

### 認証フロー

```
MCPサーバー起動
    ↓
boto3.client('s3') 呼び出し
    ↓
認証情報を検索
    ↓
~/.aws/credentials から読み込み ⭐
    ↓
S3にアクセス
```

---

## 🔧 トラブルシューティング

### エラー: "Unable to locate credentials"

**原因**: AWS認証情報が見つからない

**解決方法**:
```bash
# 認証情報を確認
cat ~/.aws/credentials

# 認証情報が無い場合は設定
aws configure
```

### エラー: "Access Denied"

**原因**: IAMユーザーに必要な権限がない

**解決方法**:
```bash
# IAMユーザーに以下の権限を付与
# - s3:GetObject
# - s3:PutObject
# - s3:ListBucket
# - athena:StartQueryExecution
# - athena:GetQueryResults
# - glue:GetTable
```

### エラー: "Bucket does not exist"

**原因**: S3バケットが存在しない

**解決方法**:
```bash
# バケットを作成
aws s3 mb s3://estat-data-lake --region ap-northeast-1

# または .env ファイルで既存のバケット名を指定
```

---

## 📚 関連ドキュメント

- [AWS認証情報の設定](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
- [boto3認証情報の設定](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)
- [e-Stat API利用ガイド](https://www.e-stat.go.jp/api/)
- [IAMベストプラクティス](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)

---

## ✅ チェックリスト: 他の環境でのセットアップ

- [ ] AWS CLIをインストール
- [ ] `aws configure`でAWS認証情報を設定
- [ ] `~/.aws/credentials`ファイルが作成されたことを確認
- [ ] e-Stat APIキーを取得
- [ ] `.env.example`を`.env`にコピー
- [ ] `.env`ファイルを編集（APIキー、バケット名、リージョン）
- [ ] S3バケットを作成（または既存のバケットを使用）
- [ ] `.kiro/settings/mcp.json`を更新
- [ ] MCPサーバーをテスト実行
- [ ] S3へのアクセスを確認

---

**重要**: このドキュメントに記載されているアクセスキーは**サンプル用**です。本番環境では必ず自分のAWS認証情報を使用してください。
