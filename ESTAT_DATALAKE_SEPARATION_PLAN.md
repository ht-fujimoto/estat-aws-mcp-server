# E-stat Datalake 分離計画

## 目的
estat-datalakeを独立したプロジェクトとして分離し、他のMCPサーバーとの混同を避ける

## 新しいフォルダ構造

```
estat-datalake-project/
├── README.md                          # プロジェクト概要
├── GETTING_STARTED.md                 # クイックスタートガイド
├── .env.example                       # 環境変数テンプレート
├── requirements.txt                   # Python依存関係
├── pyproject.toml                     # プロジェクト設定
│
├── mcp_server/                        # MCPサーバー
│   ├── server.py                      # メインサーバー（更新版）
│   ├── README.md                      # サーバー説明
│   └── SETUP_GUIDE.md                 # セットアップガイド
│
├── datalake/                          # データレイクコア機能
│   ├── __init__.py
│   ├── README.md
│   ├── config/
│   │   ├── datalake_config.yaml
│   │   └── dataset_config.yaml
│   ├── config_loader.py
│   ├── data_ingestion_orchestrator.py
│   ├── data_quality_validator.py      # 更新版（重複チェックオプション化）
│   ├── dataset_selection_manager.py
│   ├── error_handler.py
│   ├── iceberg_table_manager.py
│   ├── ingestion_logger.py
│   ├── metadata_manager.py
│   ├── parallel_fetcher.py
│   ├── schema_mapper.py
│   │
│   ├── scripts/                       # 実行スクリプト
│   │   ├── initialize_datalake.py
│   │   ├── ingest_datasets.py
│   │   ├── ingest_via_kiro_mcp.py
│   │   └── create_s3_bucket.sh
│   │
│   ├── examples/                      # 使用例
│   │   ├── config_usage_example.py
│   │   ├── data_ingestion_example.py
│   │   ├── dataset_manager_example.py
│   │   ├── metadata_manager_example.py
│   │   └── schema_mapper_example.py
│   │
│   └── tests/                         # テスト
│       ├── __init__.py
│       ├── test_data_ingestion_orchestrator.py
│       ├── test_data_quality_validator.py
│       ├── test_dataset_selection_manager.py
│       ├── test_error_handler.py
│       ├── test_iceberg_table_manager.py
│       ├── test_metadata_manager.py
│       ├── test_parallel_fetcher.py
│       ├── test_properties.py
│       └── test_schema_mapper.py
│
└── docs/                              # ドキュメント
    ├── ARCHITECTURE.md                # アーキテクチャ説明
    ├── API_REFERENCE.md               # API リファレンス
    ├── TOOLS_GUIDE.md                 # ツール使用ガイド
    └── TROUBLESHOOTING.md             # トラブルシューティング
```

## 必要なファイル一覧

### コアファイル
- [x] mcp_servers/estat_datalake/server.py（更新版）
- [x] mcp_servers/estat_datalake/README.md
- [x] mcp_servers/estat_datalake/SETUP_GUIDE.md

### データレイクモジュール
- [x] datalake/__init__.py
- [x] datalake/README.md
- [x] datalake/GETTING_STARTED.md
- [x] datalake/config_loader.py
- [x] datalake/data_ingestion_orchestrator.py
- [x] datalake/data_quality_validator.py（更新版）
- [x] datalake/dataset_selection_manager.py
- [x] datalake/error_handler.py
- [x] datalake/iceberg_table_manager.py
- [x] datalake/ingestion_logger.py
- [x] datalake/metadata_manager.py
- [x] datalake/parallel_fetcher.py
- [x] datalake/schema_mapper.py

### 設定ファイル
- [x] datalake/config/datalake_config.yaml
- [x] datalake/config/dataset_config.yaml

### スクリプト
- [x] datalake/scripts/initialize_datalake.py
- [x] datalake/scripts/ingest_datasets.py
- [x] datalake/scripts/ingest_via_kiro_mcp.py
- [x] datalake/scripts/create_s3_bucket.sh

### 使用例
- [x] datalake/examples/config_usage_example.py
- [x] datalake/examples/data_ingestion_example.py
- [x] datalake/examples/dataset_manager_example.py
- [x] datalake/examples/metadata_manager_example.py
- [x] datalake/examples/schema_mapper_example.py

### テスト
- [x] datalake/tests/__init__.py
- [x] datalake/tests/test_data_ingestion_orchestrator.py
- [x] datalake/tests/test_data_quality_validator.py
- [x] datalake/tests/test_dataset_selection_manager.py
- [x] datalake/tests/test_error_handler.py
- [x] datalake/tests/test_iceberg_table_manager.py
- [x] datalake/tests/test_metadata_manager.py
- [x] datalake/tests/test_parallel_fetcher.py
- [x] datalake/tests/test_properties.py
- [x] datalake/tests/test_schema_mapper.py

### ドキュメント
- [ ] ESTAT_DATALAKE_機能説明.md → docs/ARCHITECTURE.md
- [ ] ESTAT_DATALAKE_設計書.md → docs/API_REFERENCE.md
- [ ] ESTAT_DATALAKE_TOOLS_詳細設計書.md → docs/TOOLS_GUIDE.md

### プロジェクト設定
- [x] .env.example
- [x] requirements.txt
- [x] pyproject.toml

## 更新内容

### 1. データ品質検証ツール（validate_data_quality）
- 重複チェックをオプション化（check_duplicates パラメータ追加）
- デフォルトは false（重複チェックなし）
- 必須列チェックとnull値チェックは常に実行

### 2. 分割取得ツール（fetch_large_dataset_complete）
- estat-enhanced準拠の実装に更新
- MCPタイムアウト対策として最初のチャンクのみ取得
- メタデータAPIで総レコード数を事前確認
- 完全取得には fetch_large_dataset_parallel を推奨

### 3. 自動取得ツール（fetch_dataset_auto）
- 新規追加
- データサイズに応じて自動的に取得方法を切り替え
- 10万件以下: 単一リクエスト
- 10万件超: 分割取得

## 次のステップ

1. 新しいフォルダ構造を作成
2. 必要なファイルをコピー
3. README.mdとドキュメントを作成
4. Kiroで新しいプロジェクトとして開く
5. 動作確認とテスト

## 利点

- **明確な分離**: 他のMCPサーバーとの混同を回避
- **独立性**: 単独でデプロイ・配布可能
- **保守性**: 専用のドキュメントとテスト
- **拡張性**: 新機能の追加が容易
