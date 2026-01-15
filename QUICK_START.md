# クイックスタートガイド

このガイドでは、e-Stat MCP Serverを最速でセットアップして使い始める方法を説明します。

## 📦 インストール方法（3つの選択肢）

### オプション1: PyPIからインストール（最も簡単）

```bash
pip install estat-mcp-server
```

### オプション2: GitHubからインストール

```bash
pip install git+https://github.com/yourusername/estat-mcp-server.git
```

### オプション3: ローカル開発モード

```bash
# リポジトリをクローン
git clone https://github.com/yourusername/estat-mcp-server.git
cd estat-mcp-server

# 開発モードでインストール
pip install -e .
```

## 🔑 e-Stat APIキーの取得

1. [e-Stat API](https://www.e-stat.go.jp/api/)にアクセス
2. アカウント登録（無料）
3. APIキー（appId）を取得

## ⚙️ 設定

### 環境変数の設定

```bash
# .envファイルを作成
cp .env.example .env

# エディタで編集
nano .env
```

`.env`ファイルの内容：
```bash
ESTAT_APP_ID=あなたのAPIキー
S3_BUCKET=estat-data-lake  # オプション
AWS_REGION=ap-northeast-1   # オプション
```

### Kiroでの設定

`~/.kiro/settings/mcp.json`を編集：

```json
{
  "mcpServers": {
    "estat-enhanced": {
      "command": "python",
      "args": ["-m", "estat_mcp_server.server"],
      "env": {
        "ESTAT_APP_ID": "あなたのAPIキー",
        "S3_BUCKET": "estat-data-lake",
        "AWS_REGION": "ap-northeast-1",
        "FASTMCP_LOG_LEVEL": "ERROR"
      },
      "disabled": false
    }
  }
}
```

### Clineでの設定

`.cline/mcp.json`を編集：

```json
{
  "mcpServers": {
    "estat-enhanced": {
      "command": "python",
      "args": ["-m", "estat_mcp_server.server"],
      "env": {
        "ESTAT_APP_ID": "あなたのAPIキー"
      }
    }
  }
}
```

## 🚀 使い方

### 基本的な使用例

1. **データセット検索**
```
世田谷区の人口データを検索してください
```

2. **データ取得**
```
データセット0000020101を取得してください
```

3. **CSV出力**
```
取得したデータをCSVで保存してください
```

### 利用可能なツール

| ツール名 | 説明 |
|---------|------|
| `search_estat_data` | キーワードでデータセット検索 |
| `apply_keyword_suggestions` | キーワード変換を適用 |
| `fetch_dataset_auto` | データセット自動取得 |
| `fetch_large_dataset_complete` | 大規模データ完全取得 |
| `fetch_dataset_filtered` | フィルタ付きデータ取得 |
| `save_dataset_as_csv` | CSV形式で保存 |
| `download_csv_from_s3` | S3からダウンロード |
| `transform_to_parquet` | Parquet形式に変換 |
| `load_to_iceberg` | Icebergテーブルに投入 |
| `analyze_with_athena` | Athenaで分析 |

## 🧪 動作確認

### 手動テスト

```bash
# サーバーを直接起動
python -m estat_mcp_server.server

# 別のターミナルでテスト
curl -X POST http://localhost:3000/tools
```

### Kiro/Clineでテスト

1. Kiroを再起動
2. チャットで以下を試す：
```
e-Statで東京都の人口データを検索してください
```

## 🔧 トラブルシューティング

### エラー: "ESTAT_APP_ID not set"

**解決方法:**
```bash
# 環境変数を確認
echo $ESTAT_APP_ID

# 設定されていない場合
export ESTAT_APP_ID="あなたのAPIキー"
```

### エラー: "Module not found"

**解決方法:**
```bash
# 再インストール
pip uninstall estat-mcp-server
pip install estat-mcp-server

# または開発モード
pip install -e .
```

### MCPサーバーが起動しない

**解決方法:**
```bash
# ログレベルを上げて詳細確認
export FASTMCP_LOG_LEVEL=DEBUG
python -m estat_mcp_server.server
```

### AWS S3エラー

**解決方法:**
```bash
# AWS認証情報を確認
aws configure list

# または環境変数で設定
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
```

## 📚 詳細ドキュメント

- [完全なデプロイメントガイド](MCP_DEPLOYMENT_GUIDE.md)
- [MCPツールの詳細](README_MCP_TOOLS.md)
- [GitHub Issues](https://github.com/yourusername/estat-mcp-server/issues)

## 💡 使用例

### 例1: 特定地域の人口データ取得

```
世田谷区の最新人口データを取得してCSVでダウンロードしてください
```

### 例2: 大規模データセットの取得

```
データセット0002070001を完全に取得してください
```

### 例3: フィルタリング取得

```
東京都のデータのみをフィルタして取得してください
```

## 🤝 サポート

問題が発生した場合：
1. [GitHub Issues](https://github.com/yourusername/estat-mcp-server/issues)で検索
2. 新しいIssueを作成
3. 以下の情報を含める：
   - エラーメッセージ
   - 実行環境（OS、Pythonバージョン）
   - 実行したコマンド

## 📝 ライセンス

MIT License - 詳細は[LICENSE](LICENSE)を参照
