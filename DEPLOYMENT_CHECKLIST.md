# MCPサーバー配布チェックリスト

このチェックリストに従って、MCPサーバーを配布可能な状態にします。

## ✅ 事前準備

- [ ] Python 3.8以上がインストールされている
- [ ] pipが最新版に更新されている (`pip install --upgrade pip`)
- [ ] Gitがインストールされている
- [ ] GitHubアカウントを持っている
- [ ] PyPIアカウントを作成した（オプション）
- [ ] TestPyPIアカウントを作成した（推奨）

## 📁 ステップ1: パッケージ構造の整理

- [ ] `reorganize_package.sh`を実行
  ```bash
  ./reorganize_package.sh
  ```

- [ ] `estat_mcp_server/`ディレクトリが作成されたことを確認
- [ ] 以下のファイルが存在することを確認：
  - [ ] `estat_mcp_server/__init__.py`
  - [ ] `estat_mcp_server/server.py`
  - [ ] `estat_mcp_server/hitl.py`
  - [ ] `estat_mcp_server/dictionary.py`
  - [ ] `estat_mcp_server/keyword_dict.py`

## 📝 ステップ2: メタデータの更新

- [ ] `pyproject.toml`を編集：
  - [ ] `name`を確認
  - [ ] `version`を設定
  - [ ] `authors`に自分の情報を記入
  - [ ] `urls`のGitHubリンクを更新

- [ ] `setup.py`を編集：
  - [ ] `author`と`author_email`を更新
  - [ ] `url`を更新

- [ ] `README.md`を充実させる：
  - [ ] プロジェクトの説明
  - [ ] インストール方法
  - [ ] 使用例
  - [ ] ライセンス情報

- [ ] `LICENSE`ファイルを確認
  - [ ] 年と著作者名を更新

## 🔧 ステップ3: 環境設定

- [ ] `.env.example`を確認
- [ ] `.gitignore`を確認
- [ ] 機密情報が含まれていないことを確認

## 🧪 ステップ4: ローカルテスト

- [ ] 開発モードでインストール
  ```bash
  pip install -e .
  ```

- [ ] サーバーが起動することを確認
  ```bash
  python -m estat_mcp_server.server
  ```

- [ ] Kiro/Clineで動作確認
  - [ ] MCPサーバーが認識される
  - [ ] ツールが正常に動作する

## 📦 ステップ5: パッケージのビルド

- [ ] ビルドツールをインストール
  ```bash
  pip install build twine
  ```

- [ ] パッケージをビルド
  ```bash
  python -m build
  ```

- [ ] `dist/`ディレクトリに以下が生成されたことを確認：
  - [ ] `.tar.gz`ファイル（ソース配布）
  - [ ] `.whl`ファイル（ホイール配布）

- [ ] パッケージを検証
  ```bash
  twine check dist/*
  ```

## 🌐 ステップ6: GitHubへの公開

- [ ] GitHubでリポジトリを作成
- [ ] ローカルリポジトリを初期化
  ```bash
  git init
  git add .
  git commit -m "Initial commit"
  ```

- [ ] リモートリポジトリを追加
  ```bash
  git remote add origin https://github.com/yourusername/estat-mcp-server.git
  git branch -M main
  git push -u origin main
  ```

- [ ] README.mdがGitHubで正しく表示されることを確認

## 🚀 ステップ7: TestPyPIへの公開（推奨）

- [ ] TestPyPIのAPIトークンを取得
  - [ ] https://test.pypi.org/manage/account/token/ にアクセス
  - [ ] 新しいトークンを作成

- [ ] TestPyPIにアップロード
  ```bash
  twine upload --repository testpypi dist/*
  ```

- [ ] TestPyPIからインストールして動作確認
  ```bash
  pip install -i https://test.pypi.org/simple/ estat-mcp-server
  ```

## 🎉 ステップ8: PyPIへの公開（本番）

- [ ] PyPIのAPIトークンを取得
  - [ ] https://pypi.org/manage/account/token/ にアクセス
  - [ ] 新しいトークンを作成

- [ ] PyPIにアップロード
  ```bash
  twine upload dist/*
  ```

- [ ] PyPIからインストールして動作確認
  ```bash
  pip install estat-mcp-server
  ```

- [ ] PyPIのプロジェクトページを確認
  - [ ] https://pypi.org/project/estat-mcp-server/

## 🤖 ステップ9: GitHub Actionsの設定（オプション）

- [ ] GitHubリポジトリのSecretsを設定
  - [ ] `Settings` > `Secrets and variables` > `Actions`
  - [ ] `TEST_PYPI_API_TOKEN`を追加
  - [ ] `PYPI_API_TOKEN`を追加

- [ ] GitHub Actionsが動作することを確認
  - [ ] `.github/workflows/test.yml`
  - [ ] `.github/workflows/publish.yml`

## 📢 ステップ10: ドキュメントの整備

- [ ] `QUICK_START.md`を確認
- [ ] `MCP_DEPLOYMENT_GUIDE.md`を確認
- [ ] GitHubのREADMEにバッジを追加（オプション）
  ```markdown
  ![PyPI](https://img.shields.io/pypi/v/estat-mcp-server)
  ![Python](https://img.shields.io/pypi/pyversions/estat-mcp-server)
  ![License](https://img.shields.io/github/license/yourusername/estat-mcp-server)
  ```

## 🔄 ステップ11: バージョン管理

- [ ] セマンティックバージョニングを採用
  - MAJOR.MINOR.PATCH (例: 1.0.0)
  - MAJOR: 互換性のない変更
  - MINOR: 後方互換性のある機能追加
  - PATCH: 後方互換性のあるバグ修正

- [ ] バージョン更新時の手順：
  1. [ ] `pyproject.toml`のversionを更新
  2. [ ] `setup.py`のversionを更新
  3. [ ] `estat_mcp_server/__init__.py`の__version__を更新
  4. [ ] CHANGELOGを更新（推奨）
  5. [ ] Gitタグを作成
     ```bash
     git tag -a v1.0.0 -m "Release version 1.0.0"
     git push origin v1.0.0
     ```
  6. [ ] 再ビルド・再公開

## 📊 ステップ12: 使用状況の追跡（オプション）

- [ ] PyPIのダウンロード統計を確認
  - https://pypistats.org/packages/estat-mcp-server

- [ ] GitHubのInsightsを確認
  - Stars、Forks、Issues

## 🆘 トラブルシューティング

### パッケージ名が既に使用されている

- [ ] PyPIで名前を検索して確認
- [ ] 別の名前を選択（例: `estat-mcp-server-enhanced`）

### ビルドエラー

- [ ] `pyproject.toml`の構文を確認
- [ ] 依存関係が正しいか確認
- [ ] Pythonバージョンの互換性を確認

### アップロードエラー

- [ ] APIトークンが正しいか確認
- [ ] ネットワーク接続を確認
- [ ] パッケージ名の重複を確認

## 📚 参考リソース

- [ ] [Python Packaging User Guide](https://packaging.python.org/)
- [ ] [PyPI Help](https://pypi.org/help/)
- [ ] [Semantic Versioning](https://semver.org/)
- [ ] [GitHub Actions Documentation](https://docs.github.com/en/actions)

## ✨ 完了！

すべてのチェックが完了したら、MCPサーバーは配布可能な状態です！

次のステップ：
1. コミュニティに共有
2. フィードバックを収集
3. 継続的な改善
4. ドキュメントの充実
