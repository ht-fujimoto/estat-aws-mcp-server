# estat-aws クイックスタートガイド

他の環境でestat-awsを**5分で**セットアップする方法

---

## 🚀 最速セットアップ（既存サービス使用）

### 必要なもの
- ✅ e-Stat APIキー（[こちら](https://www.e-stat.go.jp/api/)から取得）
- ✅ Kiro IDE
- ✅ Python 3.11以上

### ステップ1: ファイルをコピー（1分）

以下の2ファイルをコピーします：

```bash
# 現在のプロジェクトから
cp mcp_aws_wrapper.py /path/to/new/project/

# Kiro設定ディレクトリを作成
mkdir -p /path/to/new/project/.kiro/settings/
```

### ステップ2: Kiro設定を作成（2分）

`/path/to/new/project/.kiro/settings/mcp.json`を作成：

```json
{
  "mcpServers": {
    "estat-aws": {
      "command": "python3",
      "args": ["mcp_aws_wrapper.py"],
      "env": {
        "ESTAT_APP_ID": "あなたのe-Stat APIキー",
        "S3_BUCKET": "estat-data-lake",
        "AWS_REGION": "ap-northeast-1"
      },
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

**重要**: `あなたのe-Stat APIキー`を実際のAPIキーに置き換えてください！

### ステップ3: 動作確認（1分）

```bash
cd /path/to/new/project/

# テスト実行
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 mcp_aws_wrapper.py
```

以下のように10個のツールが表示されれば成功です：

```
✅ 10 tools available

Tool Details:

1. search_estat_data
   Description: 自然言語でe-Statデータを検索し、キーワードサジェスト機能付きで最適なデータセットを提案
   Required params: ['query']

2. apply_keyword_suggestions
   ...
```

### ステップ4: Kiro IDEで使用（1分）

1. Kiro IDEを開く
2. 新しいプロジェクトを開く（`/path/to/new/project/`）
3. Kiro IDEを再起動（設定を読み込むため）
4. チャットで試す：

```
京都府の労働者データを検索してください
```

---

## 🎯 これだけ！

たった4ステップで、他の環境でもestat-awsが使えるようになりました。

---

## 📝 よくある質問

### Q1: mcp_aws_wrapper.pyの中身を変更する必要はありますか？

**A**: いいえ、必要ありません。既存のECS Fargateサービスを使用するため、そのまま使えます。

### Q2: AWS設定は必要ですか？

**A**: いいえ、この方法では不要です。既にデプロイされているサービスを使用します。

### Q3: e-Stat APIキーはどこで取得できますか？

**A**: [e-Stat API利用登録ページ](https://www.e-stat.go.jp/api/)から無料で取得できます。

### Q4: 複数のプロジェクトで使えますか？

**A**: はい、各プロジェクトに`mcp_aws_wrapper.py`と`.kiro/settings/mcp.json`をコピーするだけです。

### Q5: チームメンバーと共有できますか？

**A**: はい、同じ手順で各メンバーがセットアップできます。全員が同じECS Fargateサービスを使用します。

---

## 🔧 トラブルシューティング

### エラー: "Connection refused"

**原因**: サービスが停止している可能性があります。

**確認方法**:
```bash
curl http://estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com/health
```

正常な場合:
```json
{"status": "healthy", "timestamp": "2026-01-09T..."}
```

### エラー: "tools not found"

**原因**: mcp.jsonのパスが間違っている可能性があります。

**確認方法**:
```bash
# 現在のディレクトリを確認
pwd

# mcp_aws_wrapper.pyが存在するか確認
ls -la mcp_aws_wrapper.py

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

### エラー: "Invalid API key"

**原因**: e-Stat APIキーが間違っているか、期限切れです。

**解決方法**:
1. [e-Stat API管理ページ](https://www.e-stat.go.jp/api/)でAPIキーを確認
2. mcp.jsonの`ESTAT_APP_ID`を更新
3. Kiro IDEを再起動

---

## 📚 次のステップ

セットアップが完了したら、以下を試してみてください：

### 1. データ検索
```
東京都の人口データを検索してください
```

### 2. データ取得
```
データセットID 0000010209 を取得してください
```

### 3. データ分析
```
取得したデータをParquet形式に変換してください
```

### 4. 詳細な使い方
詳細なセットアップ方法や高度な使い方は、`ESTAT_AWS_SETUP_GUIDE.md`を参照してください。

---

## 💡 ヒント

### 環境変数ファイルを使う

`.env`ファイルを作成すると便利です：

```bash
# .env
ESTAT_APP_ID=your-api-key-here
S3_BUCKET=estat-data-lake
AWS_REGION=ap-northeast-1
```

### 複数のAPIキーを管理

開発用と本番用で異なるAPIキーを使用する場合：

```json
{
  "mcpServers": {
    "estat-aws-dev": {
      "command": "python3",
      "args": ["mcp_aws_wrapper.py"],
      "env": {
        "ESTAT_APP_ID": "dev-api-key",
        ...
      }
    },
    "estat-aws-prod": {
      "command": "python3",
      "args": ["mcp_aws_wrapper.py"],
      "env": {
        "ESTAT_APP_ID": "prod-api-key",
        ...
      },
      "disabled": true  // 通常は無効化
    }
  }
}
```

---

## ✅ チェックリスト

セットアップが完了したか確認しましょう：

- [ ] mcp_aws_wrapper.pyをコピーした
- [ ] .kiro/settings/mcp.jsonを作成した
- [ ] e-Stat APIキーを設定した
- [ ] ローカルでtools/listをテストした（10個のツールが表示）
- [ ] Kiro IDEを再起動した
- [ ] Kiro IDEでデータ検索を試した

全てチェックできたら、estat-awsを使う準備完了です！🎉

---

**所要時間**: 約5分  
**難易度**: ⭐☆☆☆☆（とても簡単）  
**作成日**: 2026年1月9日
