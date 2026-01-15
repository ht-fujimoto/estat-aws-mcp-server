# estat-aws パッケージ

e-Stat統計データをKiro IDE（MCP）経由で利用するためのパッケージです。

## 📦 パッケージ内容

```
estat-aws-package/
├── README.md                          # このファイル
├── mcp_aws_wrapper.py                 # MCPブリッジ（必須）
├── test_estat_aws_setup.sh            # セットアップテストスクリプト
│
├── .kiro/
│   └── settings/
│       └── mcp.json.example           # Kiro設定サンプル
│
├── mcp_servers/                       # MCPサーバー実装（オプション）
│   └── estat_aws/
│       ├── __init__.py
│       ├── server.py                  # メインサーバー
│       ├── keyword_dictionary.py      # 統計用語辞書
│       └── utils/
│           ├── __init__.py
│           ├── error_handler.py
│           ├── retry.py
│           ├── logger.py
│           └── response_formatter.py
│
├── server_http.py                     # HTTPラッパー（オプション）
├── Dockerfile                         # Docker設定（オプション）
├── requirements.txt                   # Python依存関係（オプション）
├── task-definition.json               # ECSタスク定義（オプション）
├── deploy_ecs_fargate.sh              # デプロイスクリプト（オプション）
│
└── docs/                              # ドキュメント
    ├── ESTAT_AWS_QUICK_START.md       # クイックスタート（5分）
    ├── ESTAT_AWS_SETUP_GUIDE.md       # 完全セットアップガイド
    ├── ESTAT_AWS_DEPLOYMENT_SUMMARY.md # 全体サマリー
    ├── KYOTO_LABOR_DATA_FULL_TEST_REPORT.md
    └── FIXED_TOOLS_TEST_REPORT.md
```

## 🚀 クイックスタート（5分）

### 前提条件
- Python 3.11以上
- Kiro IDE
- e-Stat APIキー（[こちら](https://www.e-stat.go.jp/api/)から取得）

### ステップ1: Kiro設定ファイルの作成

```bash
# サンプルをコピー
cp .kiro/settings/mcp.json.example .kiro/settings/mcp.json

# エディタで開いてAPIキーを設定
# "your-estat-api-key-here" を実際のAPIキーに置き換える
```

### ステップ2: 動作確認

```bash
# テストスクリプトを実行
chmod +x test_estat_aws_setup.sh
./test_estat_aws_setup.sh
```

全てのテストに合格すれば、セットアップ完了です！

### ステップ3: Kiro IDEで使用

1. Kiro IDEを開く
2. このプロジェクトを開く
3. Kiro IDEを再起動（設定を読み込むため）
4. チャットで試す：

```
京都府の労働者データを検索してください
```

## 📚 詳細ドキュメント

### 初めての方
→ **docs/ESTAT_AWS_QUICK_START.md**（5分で始める）

### 完全なセットアップ方法
→ **docs/ESTAT_AWS_SETUP_GUIDE.md**（3つの方法を解説）

### 全体像を把握したい
→ **docs/ESTAT_AWS_DEPLOYMENT_SUMMARY.md**（ナビゲーション）

### 実際の使用例
→ **docs/KYOTO_LABOR_DATA_FULL_TEST_REPORT.md**（テスト結果）

## 🔧 3つの使用方法

### 方法1: 既存サービスを使用（推奨）⭐

**必要なファイル**:
- `mcp_aws_wrapper.py`
- `.kiro/settings/mcp.json`

**メリット**:
- 最も簡単（5分でセットアップ）
- AWS設定不要
- すぐに使える

**手順**: docs/ESTAT_AWS_QUICK_START.md 参照

---

### 方法2: 独自AWS環境にデプロイ

**必要なファイル**:
- 全ファイル

**メリット**:
- 独自の環境で管理
- セキュリティ重視
- カスタマイズ可能

**手順**: docs/ESTAT_AWS_SETUP_GUIDE.md の「方法2」参照

---

### 方法3: ローカル開発環境

**必要なファイル**:
- `mcp_servers/` 配下全て
- `server_http.py`
- `requirements.txt`
- `mcp_aws_wrapper.py`
- `.kiro/settings/mcp.json`

**メリット**:
- 開発・テストに最適
- 素早く試せる

**手順**: docs/ESTAT_AWS_SETUP_GUIDE.md の「方法3」参照

## 🎯 利用可能な10個のツール

| # | ツール名 | 機能 |
|---|---------|------|
| 1 | search_estat_data | キーワードサジェスト付き検索 |
| 2 | apply_keyword_suggestions | キーワード変換適用 |
| 3 | fetch_dataset_auto | 自動データセット取得 |
| 4 | fetch_large_dataset_complete | 大規模データ完全取得 |
| 5 | fetch_dataset_filtered | フィルタ付き取得 |
| 6 | transform_to_parquet | Parquet変換 |
| 7 | load_to_iceberg | Icebergロード |
| 8 | analyze_with_athena | Athena分析 |
| 9 | save_dataset_as_csv | CSV保存 |
| 10 | download_csv_from_s3 | S3ダウンロード |

## 🔑 重要な情報

### 現在稼働中のサービス（方法1で使用）

- **ALB URL**: http://estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com
- **リージョン**: ap-northeast-1（東京）
- **ステータス**: 稼働中

### 必要な環境変数

```bash
ESTAT_APP_ID=your-estat-api-key  # 必須
S3_BUCKET=estat-data-lake        # オプション（AWS機能使用時）
AWS_REGION=ap-northeast-1        # オプション（AWS機能使用時）
```

## 🔧 トラブルシューティング

### 問題: ツールが表示されない

```bash
# 絶対パスを使用
{
  "mcpServers": {
    "estat-aws": {
      "command": "python3",
      "args": ["/absolute/path/to/mcp_aws_wrapper.py"],
      ...
    }
  }
}
```

### 問題: API接続エラー

```bash
# サービスの状態確認
curl http://estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com/health
```

### 問題: テストが失敗する

```bash
# 詳細なエラーメッセージを確認
./test_estat_aws_setup.sh
```

詳細は **docs/ESTAT_AWS_SETUP_GUIDE.md** のトラブルシューティングセクションを参照してください。

## 📝 チェックリスト

セットアップが完了したか確認しましょう：

- [ ] mcp.json.example を mcp.json にコピーした
- [ ] e-Stat APIキーを設定した
- [ ] test_estat_aws_setup.sh を実行した（全テスト合格）
- [ ] Kiro IDEを再起動した
- [ ] データ検索を試した

## 🎓 サポート

### ドキュメント
- クイックスタート: docs/ESTAT_AWS_QUICK_START.md
- 完全ガイド: docs/ESTAT_AWS_SETUP_GUIDE.md
- 全体サマリー: docs/ESTAT_AWS_DEPLOYMENT_SUMMARY.md

### 外部リンク
- [e-Stat API仕様書](https://www.e-stat.go.jp/api/api-info/api-spec)
- [AWS ECS Fargate](https://docs.aws.amazon.com/ecs/latest/developerguide/AWS_Fargate.html)
- [MCP Protocol](https://modelcontextprotocol.io/)

## 📊 実装統計

- **総行数**: 約2,030行
- **実装ツール**: 10個
- **テスト済み**: 8/10ツール
- **成功率**: 80%
- **ステータス**: 実用レベル達成 🎉

## 📄 ライセンス

このパッケージは、e-Stat APIの利用規約に従って使用してください。

---

**バージョン**: 1.1.0  
**最終更新**: 2026年1月9日  
**作成者**: Kiro AI Assistant
