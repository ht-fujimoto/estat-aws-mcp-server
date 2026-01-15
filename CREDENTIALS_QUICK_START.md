# AWS認証情報 クイックスタートガイド

## 🚀 3ステップで始める

### ステップ1: AWS認証情報を設定

```bash
# AWS CLIで認証情報を設定
aws configure

# 入力が求められる項目:
# AWS Access Key ID: [あなたのアクセスキー]
# AWS Secret Access Key: [あなたのシークレットキー]
# Default region name: ap-northeast-1
# Default output format: json
```

これにより、`~/.aws/credentials` と `~/.aws/config` が自動作成されます。

### ステップ2: .envファイルを設定

```bash
# .env.example をコピー
cp .env.example .env

# .env を編集
nano .env  # または vim, code など
```

最低限必要な設定:
```bash
ESTAT_APP_ID=your_estat_app_id_here  # e-Stat APIキー
S3_BUCKET=estat-data-lake            # S3バケット名
AWS_REGION=ap-northeast-1            # AWSリージョン
```

### ステップ3: セットアップスクリプトを実行

```bash
# セットアップスクリプトで環境を確認
./setup_credentials.sh
```

---

## ❓ よくある質問

### Q1: AWS認証情報はどこに保存されますか？

**A**: `~/.aws/credentials` ファイルに保存されます。

```bash
# 確認方法
cat ~/.aws/credentials
```

このファイルは:
- ✅ ホームディレクトリに保存される
- ✅ Gitにコミットされない
- ✅ boto3が自動的に読み込む

### Q2: 他の環境で使う場合、何を共有すればいいですか？

**A**: 以下の情報が必要です:

1. **e-Stat APIキー** (`.env`ファイルから)
   ```
   ESTAT_APP_ID=320dd2fbff6974743e3f95505c9f346650ab635e
   ```

2. **AWS認証情報** (各自で設定)
   - アクセスキーID
   - シークレットアクセスキー
   - リージョン

3. **S3バケット名** (`.env`ファイルから)
   ```
   S3_BUCKET=estat-data-lake
   ```

### Q3: AWS認証情報を持っていません。どうすればいいですか？

**A**: AWSコンソールでIAMユーザーを作成します:

1. [AWS IAMコンソール](https://console.aws.amazon.com/iam/)にアクセス
2. 「ユーザー」→「ユーザーを追加」
3. アクセスキーを作成
4. 必要な権限を付与:
   - `AmazonS3FullAccess` または
   - カスタムポリシーで最小権限

### Q4: .envファイルに認証情報を書いてもいいですか？

**A**: 推奨しません。

❌ **非推奨**:
```bash
# .env に直接記述（セキュリティリスク）
AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
```

✅ **推奨**:
```bash
# ~/.aws/credentials に保存（安全）
aws configure
```

理由:
- `.env`ファイルは誤ってGitにコミットされる可能性がある
- `~/.aws/credentials`はAWS標準の場所で、より安全

### Q5: 複数のAWSアカウントを使い分けたい

**A**: AWSプロファイルを使用します:

```bash
# プロファイルを指定して設定
aws configure --profile work
aws configure --profile personal

# ~/.aws/credentials の内容
[default]
aws_access_key_id = AKIA...
aws_secret_access_key = ...

[work]
aws_access_key_id = AKIA...
aws_secret_access_key = ...

[personal]
aws_access_key_id = AKIA...
aws_secret_access_key = ...

# 使用時に環境変数で指定
export AWS_PROFILE=work
python3 analyze_tokyo_birth_rate.py
```

---

## 🔒 セキュリティチェックリスト

- [ ] AWS認証情報は `~/.aws/credentials` に保存
- [ ] `.env` ファイルは `.gitignore` に追加済み
- [ ] AWS認証情報を `.env` に記述していない
- [ ] AWS認証情報をコードに直接記述していない
- [ ] IAMユーザーに最小権限のみ付与
- [ ] アクセスキーを定期的にローテーション

---

## 📁 ファイル構成

```
プロジェクトルート/
├── .env                          # 環境変数（APIキー、バケット名など）
├── .env.example                  # 環境変数のテンプレート
├── .gitignore                    # .env を除外
├── .kiro/settings/mcp.json       # MCP設定
└── ~/.aws/                       # AWS認証情報（ホームディレクトリ）
    ├── credentials               # アクセスキー、シークレットキー
    └── config                    # リージョン、出力形式
```

---

## 🛠️ トラブルシューティング

### エラー: "Unable to locate credentials"

```bash
# 認証情報を確認
cat ~/.aws/credentials

# 無い場合は設定
aws configure
```

### エラー: "Access Denied"

```bash
# IAMユーザーの権限を確認
# 必要な権限:
# - s3:GetObject
# - s3:PutObject
# - s3:ListBucket
```

### エラー: "Bucket does not exist"

```bash
# バケットを作成
aws s3 mb s3://estat-data-lake --region ap-northeast-1

# または .env で既存のバケット名を指定
```

---

## 📞 サポート

詳細なガイドは以下を参照:
- `AWS_CREDENTIALS_GUIDE.md` - 詳細な認証情報管理ガイド
- `README.md` - プロジェクト全体のドキュメント
- `ESTAT_AWS_SETUP_GUIDE.md` - セットアップガイド

---

**重要**: 認証情報は絶対に公開リポジトリにコミットしないでください！
