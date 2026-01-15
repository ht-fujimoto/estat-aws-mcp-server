# estat-enhanced MCP Package

このパッケージには、estat-enhanced MCPサーバーを新しいPCで使用するために必要なすべてのファイルが含まれています。

## パッケージ内容

- `mcp_servers/` - MCPサーバーファイル
- `.kiro/settings/mcp.json` - Kiro MCP設定
- `.env` - 環境変数設定
- `requirements.txt` - Python依存関係
- `setup.sh` - 自動セットアップスクリプト
- `README.md` - このファイル

## セットアップ方法

### 自動セットアップ（推奨）

```bash
chmod +x setup.sh
./setup.sh
```

### 手動セットアップ

1. Python依存関係をインストール：
   ```bash
   pip install -r requirements.txt
   ```

2. AWS認証を設定：
   ```bash
   aws configure
   ```

3. Kiro設定をコピー：
   ```bash
   cp .kiro/settings/mcp.json ~/.kiro/settings/
   ```

4. Kiroを再起動

## 動作確認

Kiroで以下のコマンドを実行：

```
現在使えるmcpを教えてください
```

estat-enhancedが表示されることを確認してください。

## パッケージ作成日時

2026年01月05日 21:32:38

## 含まれるファイル

### 正常にコピーされたファイル:
- mcp_servers/estat_enhanced_analysis.py
- mcp_servers/estat_analysis_hitl.py
- mcp_servers/estat_enhanced_dictionary.py
- mcp_servers/estat_keyword_dictionary.py

### 見つからなかったファイル:
なし

## サポート

問題が発生した場合は、ESTAT_ENHANCED_MCP_SETUP_NEW_PC_GUIDE.md を参照してください。
