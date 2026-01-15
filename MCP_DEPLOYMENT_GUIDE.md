# MCPサーバー配布・デプロイメントガイド

このガイドでは、作成したe-Stat Enhanced Analysis MCPサーバーを他の環境でも使えるようにする手順を説明します。

## 目次
1. [パッケージ化の準備](#1-パッケージ化の準備)
2. [PyPIへの公開](#2-pypiへの公開)
3. [Gitリポジトリでの配布](#3-gitリポジトリでの配布)
4. [ローカルインストール](#4-ローカルインストール)
5. [設定方法](#5-設定方法)

---

## 1. パッケージ化の準備

### 1.1 必要なファイル構造

```
estat-mcp-server/
├── pyproject.toml          # パッケージメタデータ（推奨）
├── setup.py                # 従来の設定ファイル（オプション）
├── README.md               # 使い方の説明
├── LICENSE                 # ライセンスファイル
├── requirements.txt        # 依存パッケージ
├── .env.example           # 環境変数のサンプル
└── estat_mcp_server/      # パッケージディレクトリ
    ├── __init__.py
    ├── server.py          # メインサーバー
    ├── hitl.py            # HITLロジック
    ├── dictionary.py      # キーワード辞書
    └── keyword_dict.py    # 辞書データ
```

### 1.2 pyproject.toml の作成

最新のPythonパッケージング標準に従った設定ファイル：

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "estat-mcp-server"
version = "1.0.0"
description = "e-Stat Enhanced Analysis MCP Server with keyword suggestions"
readme = "README.md"
requires-python = ">=3.8"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
keywords = ["mcp", "estat", "statistics", "data-analysis"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
]

dependencies = [
    "requests>=2.28.0",
    "boto3>=1.26.0",
    "pandas>=1.5.0",
    "pyarrow>=10.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "black>=22.0.0",
    "flake8>=4.0.0",
]

[project.urls]
Homepage = "https://github.com/yourusername/estat-mcp-server"
Documentation = "https://github.com/yourusername/estat-mcp-server#readme"
Repository = "https://github.com/yourusername/estat-mcp-server"
Issues = "https://github.com/yourusername/estat-mcp-server/issues"

[project.scripts]
estat-mcp-server = "estat_mcp_server.server:main"
```

### 1.3 setup.py の作成（後方互換性のため）

```python
from setuptools import setup, find_packages

setup(
    name="estat-mcp-server",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
        "boto3>=1.26.0",
        "pandas>=1.5.0",
        "pyarrow>=10.0.0",
    ],
    entry_points={
        'console_scripts': [
            'estat-mcp-server=estat_mcp_server.server:main',
        ],
    },
)
```

### 1.4 __init__.py の作成

```python
"""e-Stat Enhanced Analysis MCP Server"""

__version__ = "1.0.0"
__author__ = "Your Name"

from .server import MCPServer, main

__all__ = ["MCPServer", "main"]
```

### 1.5 .env.example の作成

```bash
# e-Stat API設定
ESTAT_APP_ID=your_estat_app_id_here

# AWS S3設定（オプション）
S3_BUCKET=estat-data-lake
AWS_REGION=ap-northeast-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# ログレベル
FASTMCP_LOG_LEVEL=ERROR
```

---

## 2. PyPIへの公開

### 2.1 アカウント作成
1. [PyPI](https://pypi.org/)でアカウントを作成
2. [TestPyPI](https://test.pypi.org/)でテスト用アカウントを作成（推奨）

### 2.2 ビルドツールのインストール

```bash
pip install build twine
```

### 2.3 パッケージのビルド

```bash
# プロジェクトルートで実行
python -m build
```

これにより `dist/` ディレクトリに以下が生成されます：
- `estat-mcp-server-1.0.0.tar.gz` (ソース配布)
- `estat_mcp_server-1.0.0-py3-none-any.whl` (ホイール配布)

### 2.4 TestPyPIへのアップロード（テスト）

```bash
python -m twine upload --repository testpypi dist/*
```

### 2.5 PyPIへのアップロード（本番）

```bash
python -m twine upload dist/*
```

### 2.6 インストール確認

```bash
# TestPyPIから
pip install -i https://test.pypi.org/simple/ estat-mcp-server

# PyPIから
pip install estat-mcp-server
```

---

## 3. Gitリポジトリでの配布

### 3.1 リポジトリの準備

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/estat-mcp-server.git
git push -u origin main
```

### 3.2 .gitignore の作成

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# 環境変数
.env
.venv
env/
venv/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# データファイル
*.json
*.csv
*.parquet
!example_*.json
```

### 3.3 README.md の充実

```markdown
# e-Stat Enhanced Analysis MCP Server

キーワードサジェスト機能と強化されたスコアリングを持つe-Stat分析MCPサーバー

## Features
- 134用語の統計用語辞書によるキーワードサジェスト
- 8項目の強化されたスコアリングアルゴリズム
- AWS S3連携によるデータ保存
- CSV出力・ダウンロード機能

## Installation

### From PyPI
\`\`\`bash
pip install estat-mcp-server
\`\`\`

### From GitHub
\`\`\`bash
pip install git+https://github.com/yourusername/estat-mcp-server.git
\`\`\`

### From Source
\`\`\`bash
git clone https://github.com/yourusername/estat-mcp-server.git
cd estat-mcp-server
pip install -e .
\`\`\`

## Configuration

1. 環境変数の設定：
\`\`\`bash
cp .env.example .env
# .envファイルを編集してe-Stat APIキーを設定
\`\`\`

2. Kiro/Clineでの設定：
\`\`\`json
{
  "mcpServers": {
    "estat-enhanced": {
      "command": "python",
      "args": ["-m", "estat_mcp_server.server"],
      "env": {
        "ESTAT_APP_ID": "your_app_id_here",
        "S3_BUCKET": "your-bucket-name",
        "AWS_REGION": "ap-northeast-1"
      }
    }
  }
}
\`\`\`

## Usage

利用可能なツール：
- `search_estat_data` - データセット検索
- `apply_keyword_suggestions` - キーワード変換適用
- `fetch_dataset_auto` - データセット自動取得
- `fetch_large_dataset_complete` - 大規模データ完全取得
- `fetch_dataset_filtered` - フィルタ付き取得
- `save_dataset_as_csv` - CSV保存
- `download_csv_from_s3` - S3からダウンロード

## License
MIT
```

### 3.4 GitHubからのインストール

ユーザーは以下のコマンドでインストール可能：

```bash
# 最新版
pip install git+https://github.com/yourusername/estat-mcp-server.git

# 特定のバージョン
pip install git+https://github.com/yourusername/estat-mcp-server.git@v1.0.0

# 開発モード
git clone https://github.com/yourusername/estat-mcp-server.git
cd estat-mcp-server
pip install -e .
```

---

## 4. ローカルインストール

### 4.1 開発モードでのインストール

```bash
# プロジェクトルートで
pip install -e .
```

これにより、コードの変更が即座に反映されます。

### 4.2 通常インストール

```bash
pip install .
```

### 4.3 依存関係のみインストール

```bash
pip install -r requirements.txt
```

---

## 5. 設定方法

### 5.1 Kiroでの設定

`~/.kiro/settings/mcp.json` または `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "estat-enhanced": {
      "command": "python",
      "args": ["-m", "estat_mcp_server.server"],
      "env": {
        "ESTAT_APP_ID": "your_estat_app_id_here",
        "S3_BUCKET": "estat-data-lake",
        "AWS_REGION": "ap-northeast-1",
        "FASTMCP_LOG_LEVEL": "ERROR"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

### 5.2 Clineでの設定

`.cline/mcp.json`:

```json
{
  "mcpServers": {
    "estat-enhanced": {
      "command": "python",
      "args": ["-m", "estat_mcp_server.server"],
      "env": {
        "ESTAT_APP_ID": "your_estat_app_id_here"
      }
    }
  }
}
```

### 5.3 uvxでの実行（PyPI公開後）

```json
{
  "mcpServers": {
    "estat-enhanced": {
      "command": "uvx",
      "args": ["estat-mcp-server"],
      "env": {
        "ESTAT_APP_ID": "your_estat_app_id_here"
      }
    }
  }
}
```

---

## 配布方法の比較

| 方法 | メリット | デメリット | 推奨用途 |
|------|---------|-----------|----------|
| **PyPI** | - 簡単インストール<br>- バージョン管理<br>- 広く利用可能 | - 審査が必要<br>- 名前の競合 | 一般公開 |
| **GitHub** | - 無料<br>- バージョン管理<br>- Issue管理 | - Gitが必要<br>- ビルドが必要 | オープンソース |
| **ローカル** | - 即座に利用可能<br>- カスタマイズ容易 | - 配布が困難<br>- 更新管理が手動 | 開発・テスト |

---

## トラブルシューティング

### インストールエラー

```bash
# 依存関係の問題
pip install --upgrade pip setuptools wheel

# キャッシュクリア
pip cache purge
pip install --no-cache-dir estat-mcp-server
```

### 環境変数が読み込まれない

```bash
# .envファイルの確認
cat .env

# 環境変数の確認
echo $ESTAT_APP_ID

# 直接設定
export ESTAT_APP_ID="your_app_id"
```

### MCPサーバーが起動しない

```bash
# 手動実行でエラー確認
python -m estat_mcp_server.server

# ログレベルを上げる
export FASTMCP_LOG_LEVEL=DEBUG
```

---

## 次のステップ

1. **テストの追加**: `pytest`でユニットテストを作成
2. **CI/CDの設定**: GitHub Actionsで自動テスト・デプロイ
3. **ドキュメントの充実**: Sphinx等でAPIドキュメント生成
4. **バージョン管理**: セマンティックバージョニングの採用

---

## 参考リンク

- [Python Packaging User Guide](https://packaging.python.org/)
- [PyPI](https://pypi.org/)
- [MCP Protocol](https://modelcontextprotocol.io/)
- [Kiro Documentation](https://kiro.dev/)
