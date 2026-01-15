# e-Stat AWS MCP システムアーキテクチャ詳細

## 目次
1. [通信層 (Transport Layer)](#1-通信層-transport-layer)
2. [インフラ層 (Infrastructure Layer)](#2-インフラ層-infrastructure-layer)
3. [アプリケーション層 (Application Layer)](#3-アプリケーション層-application-layer)
4. [セキュリティ設定](#4-セキュリティ設定)
5. [監視・ログ設定](#5-監視ログ設定)
6. [コスト最適化](#6-コスト最適化)

---

## 1. 通信層 (Transport Layer)

### 1.1 プロトコル設定

#### MCP Streamable-HTTP
```json
{
  "transport": "streamable-http",
  "url": "https://estat-mcp.snowmole.co.jp/mcp"
}
```

**特徴:**
- **双方向通信**: SSE (Server-Sent Events) + JSON-RPC 2.0
- **ステートレス**: セッション管理不要
- **タイムアウト**: 制限なし（長時間実行可能）

**エンドポイント構成:**
```
GET  /mcp  → SSE接続確立（イベントストリーム）
POST /mcp  → JSON-RPCメッセージ送信
DELETE /mcp → セッション終了
GET  /health → ヘルスチェック
```

### 1.2 HTTPS/TLS設定

#### SSL/TLS証明書
- **発行元**: AWS Certificate Manager (ACM)
- **ドメイン**: estat-mcp.snowmole.co.jp
- **検証方法**: DNS検証（Route 53）
- **TLSバージョン**: TLS 1.2以上
- **暗号化スイート**: AWS推奨の強力な暗号化

**証明書設定:**
```bash
# ACM証明書リクエスト
aws acm request-certificate \
  --domain-name estat-mcp.snowmole.co.jp \
  --validation-method DNS \
  --region ap-northeast-1
```

**DNS検証レコード:**
```
Type: CNAME
Name: _xxxxx.estat-mcp.snowmole.co.jp
Value: _xxxxx.acm-validations.aws.
```

### 1.3 接続安定性の実装

#### SSE初期化メッセージ
```python
# 接続確立時に即座に送信
initialization_message = """
event: connection
data: {"status": "ready", "timestamp": "2026-01-13T13:00:00"}

"""
```

**ポイント:**
- 接続確立後、即座に初期化メッセージを送信
- Kiroが「サーバー準備完了」を認識
- タイムアウトエラーを防止

#### ノンブロッキング接続維持
```python
# 1秒間隔でチェック（60秒sleepを避ける）
while connection_active:
    await asyncio.sleep(1)  # 短い間隔
    if response.transport.is_closing():
        break
```

---

## 2. インフラ層 (Infrastructure Layer)

### 2.1 Application Load Balancer (ALB)

#### 基本設定
```bash
名前: estat-mcp-alb
スキーム: internet-facing
タイプ: application
リージョン: ap-northeast-1
```

#### リスナー設定
```
プロトコル: HTTPS
ポート: 443
SSL証明書: ACM証明書
デフォルトアクション: ターゲットグループへ転送
```

#### ターゲットグループ設定
```bash
名前: estat-mcp-tg
プロトコル: HTTP
ポート: 8080
ターゲットタイプ: IP（Fargate用）
VPC: デフォルトVPC

# ヘルスチェック
パス: /health
間隔: 30秒
タイムアウト: 10秒
正常しきい値: 2
異常しきい値: 3

# タイムアウト設定
登録解除遅延: 30秒
```

#### セキュリティグループ
```bash
名前: estat-mcp-sg
インバウンドルール:
  - プロトコル: TCP
  - ポート: 443 (HTTPS)
  - ソース: 0.0.0.0/0
  - 説明: HTTPS from anywhere

  - プロトコル: TCP
  - ポート: 8080 (コンテナ)
  - ソース: ALBセキュリティグループ
  - 説明: Container port from ALB

アウトバウンドルール:
  - すべてのトラフィック許可
```

### 2.2 ECS Fargate

#### クラスター設定
```bash
名前: estat-mcp-cluster
タイプ: Fargate
リージョン: ap-northeast-1
```

#### タスク定義 (Revision 10)
```json
{
  "family": "estat-mcp-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",          // 0.25 vCPU
  "memory": "512",       // 0.5 GB
  
  "executionRoleArn": "arn:aws:iam::639135896267:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::639135896267:role/ecsTaskRole",
  
  "containerDefinitions": [{
    "name": "estat-mcp-container",
    "image": "639135896267.dkr.ecr.ap-northeast-1.amazonaws.com/estat-mcp:latest",
    
    "portMappings": [{
      "containerPort": 8080,
      "protocol": "tcp"
    }],
    
    "environment": [
      {"name": "ESTAT_APP_ID", "value": "320dd2fbff6974743e3f95505c9f346650ab635e"},
      {"name": "S3_BUCKET", "value": "estat-data-lake"},
      {"name": "AWS_REGION", "value": "ap-northeast-1"}
    ],
    
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/estat-mcp",
        "awslogs-region": "ap-northeast-1",
        "awslogs-stream-prefix": "ecs"
      }
    }
  }]
}
```

#### サービス設定
```bash
名前: estat-mcp-service
クラスター: estat-mcp-cluster
タスク定義: estat-mcp-task:10
起動タイプ: FARGATE
希望タスク数: 1

# ネットワーク設定
サブネット: デフォルトVPCの全サブネット
セキュリティグループ: estat-mcp-sg
パブリックIP: 有効

# ロードバランサー統合
ターゲットグループ: estat-mcp-tg
コンテナ名: estat-mcp-container
コンテナポート: 8080
```

### 2.3 DNS設定 (Route 53)

#### ホストゾーン
```
ドメイン: snowmole.co.jp
タイプ: パブリックホストゾーン
```

#### Aレコード設定
```
名前: estat-mcp.snowmole.co.jp
タイプ: A (エイリアス)
エイリアスターゲット: estat-mcp-alb
ルーティングポリシー: シンプル
```

### 2.4 コンテナレジストリ (ECR)

#### リポジトリ設定
```bash
名前: estat-mcp
リージョン: ap-northeast-1
URI: 639135896267.dkr.ecr.ap-northeast-1.amazonaws.com/estat-mcp

# イメージタグ
latest: 最新版（自動更新）
```

#### イメージビルド設定
```dockerfile
# プラットフォーム指定
docker build --platform linux/amd64 -t estat-mcp:latest .

# ECRプッシュ
docker tag estat-mcp:latest 639135896267.dkr.ecr.ap-northeast-1.amazonaws.com/estat-mcp:latest
docker push 639135896267.dkr.ecr.ap-northeast-1.amazonaws.com/estat-mcp:latest
```

---

## 3. アプリケーション層 (Application Layer)

### 3.1 MCPサーバー (server_mcp_streamable.py)

#### サーバー設定
```python
# 環境変数
PORT = 8080
HOST = "0.0.0.0"
TRANSPORT_MODE = "streamable-http"
MCP_SESSION_MODE = "stateless"
```

#### エンドポイントハンドラー
```python
# ルーティング
app.router.add_get('/mcp', handle_mcp_endpoint)    # SSE
app.router.add_post('/mcp', handle_mcp_endpoint)   # JSON-RPC
app.router.add_delete('/mcp', handle_mcp_endpoint) # セッション終了
app.router.add_get('/health', handle_health)       # ヘルスチェック
```

#### JSON-RPC 2.0メソッド
```python
# サポートメソッド
- initialize          # サーバー初期化
- tools/list          # ツール一覧取得
- tools/call          # ツール実行
- notifications/*     # 通知（応答なし）
```

### 3.2 データ処理層 (e-Stat AWS Core)

#### コアモジュール構成
```
mcp_servers/estat_aws/
├── server.py              # メインサーバー
├── utils/
│   ├── logger.py         # ロギング
│   └── error_handler.py  # エラーハンドリング
└── __init__.py
```

#### 提供ツール (10個)
```python
1. search_estat_data           # データ検索
2. apply_keyword_suggestions   # キーワード提案適用
3. fetch_dataset_auto          # 自動データ取得
4. fetch_large_dataset_complete # 大規模データ完全取得
5. fetch_dataset_filtered      # フィルタ付き取得
6. transform_to_parquet        # Parquet変換
7. load_to_iceberg            # Iceberg投入
8. analyze_with_athena        # Athena分析
9. save_dataset_as_csv        # CSV保存
10. download_csv_from_s3      # CSVダウンロード
```

### 3.3 ストレージ層

#### S3バケット設定
```bash
バケット名: estat-data-lake
リージョン: ap-northeast-1

# フォルダ構造
estat-data-lake/
├── raw/              # 生データ（JSON）
├── parquet/          # Parquet形式
├── csv/              # CSV形式
└── iceberg/          # Icebergテーブル
```

#### S3アクセス権限
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket"
    ],
    "Resource": [
      "arn:aws:s3:::estat-data-lake",
      "arn:aws:s3:::estat-data-lake/*"
    ]
  }]
}
```

#### Athena設定
```bash
ワークグループ: primary
クエリ結果の場所: s3://estat-data-lake/athena-results/
データカタログ: AWS Glue Data Catalog
```

#### Iceberg設定
```python
# テーブル形式
format: Apache Iceberg
catalog: AWS Glue
location: s3://estat-data-lake/iceberg/
```

---

## 4. セキュリティ設定

### 4.1 IAMロール

#### タスク実行ロール (ecsTaskExecutionRole)
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Service": "ecs-tasks.amazonaws.com"
    },
    "Action": "sts:AssumeRole"
  }]
}
```

**アタッチポリシー:**
- AmazonECSTaskExecutionRolePolicy (AWS管理)

**権限:**
- ECRからイメージをプル
- CloudWatch Logsへログ送信

#### タスクロール (ecsTaskRole)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::estat-data-lake",
        "arn:aws:s3:::estat-data-lake/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:StopQueryExecution"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase",
        "glue:GetTable",
        "glue:CreateTable",
        "glue:UpdateTable",
        "glue:DeleteTable",
        "glue:GetPartitions"
      ],
      "Resource": "*"
    }
  ]
}
```

### 4.2 ネットワークセキュリティ

#### VPC設定
```bash
VPC: デフォルトVPC
CIDR: 172.31.0.0/16
サブネット: 3つ（マルチAZ）
  - ap-northeast-1a
  - ap-northeast-1c
  - ap-northeast-1d
```

#### セキュリティグループルール
```
インバウンド:
  443 (HTTPS) ← 0.0.0.0/0
  8080 (Container) ← ALB SG

アウトバウンド:
  すべて → 0.0.0.0/0
```

---

## 5. 監視・ログ設定

### 5.1 CloudWatch Logs

#### ロググループ設定
```bash
名前: /ecs/estat-mcp
リージョン: ap-northeast-1
保持期間: 7日間（デフォルト）
```

#### ログストリーム
```
形式: ecs/{container-name}/{task-id}
例: ecs/estat-mcp-container/abc123def456
```

#### ログ確認コマンド
```bash
# リアルタイムログ
aws logs tail /ecs/estat-mcp --follow --region ap-northeast-1

# 特定期間のログ
aws logs filter-log-events \
  --log-group-name /ecs/estat-mcp \
  --start-time 1673568000000 \
  --region ap-northeast-1
```

### 5.2 ヘルスチェック

#### ALBヘルスチェック
```
パス: /health
間隔: 30秒
タイムアウト: 10秒
正常しきい値: 2回連続成功
異常しきい値: 3回連続失敗
```

#### コンテナヘルスチェック
```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"
```

### 5.3 メトリクス監視

#### ECSメトリクス
- CPUUtilization
- MemoryUtilization
- TaskCount
- RunningTaskCount

#### ALBメトリクス
- TargetResponseTime
- RequestCount
- HTTPCode_Target_2XX_Count
- HTTPCode_Target_5XX_Count
- HealthyHostCount
- UnHealthyHostCount

---

## 6. コスト最適化

### 6.1 月額コスト見積もり

#### Fargate
```
vCPU: 0.25 × $0.04656/時間 × 730時間 = $8.50
メモリ: 0.5GB × $0.00511/GB/時間 × 730時間 = $1.87
合計: 約$10.37/月
```

#### ALB
```
時間料金: $0.0225/時間 × 730時間 = $16.43
LCU料金: 約$5/月（低トラフィック想定）
合計: 約$21.43/月
```

#### その他
```
ECR: $0.10/GB/月（イメージサイズ約500MB） = $0.05/月
CloudWatch Logs: $0.50/GB（約1GB/月） = $0.50/月
Route 53: $0.50/月（ホストゾーン）
ACM証明書: 無料
```

#### 総コスト
```
合計: 約$33/月
```

### 6.2 コスト削減策

1. **Fargateスポット**: 最大70%削減（本番環境では非推奨）
2. **ログ保持期間短縮**: 7日→3日で約50%削減
3. **ALB削除**: CloudFront + Lambda@Edge使用で約$16/月削減
4. **リザーブドキャパシティ**: 1年契約で約30%削減

---

## 7. デプロイメントフロー

### 7.1 初回デプロイ
```bash
1. ECRリポジトリ作成
2. Dockerイメージビルド
3. ECRにプッシュ
4. ECSクラスター作成
5. IAMロール作成
6. CloudWatch Logsグループ作成
7. タスク定義登録
8. VPC/サブネット取得
9. セキュリティグループ作成
10. ALB作成
11. ターゲットグループ作成
12. リスナー作成
13. ECSサービス作成
14. ACM証明書リクエスト
15. DNS検証
16. ALBリスナーHTTPS追加
17. Route 53レコード作成
```

### 7.2 更新デプロイ
```bash
1. コード修正
2. Dockerイメージ再ビルド
3. ECRにプッシュ
4. 新しいタスク定義登録
5. ECSサービス更新
6. ローリングアップデート自動実行
```

### 7.3 ロールバック
```bash
# 前のタスク定義に戻す
aws ecs update-service \
  --cluster estat-mcp-cluster \
  --service estat-mcp-service \
  --task-definition estat-mcp-task:9
```

---

## 8. トラブルシューティング

### 8.1 よくある問題

#### 問題1: タスクが起動しない
```bash
# 原因確認
aws ecs describe-tasks \
  --cluster estat-mcp-cluster \
  --tasks <task-id> \
  --query 'tasks[0].stoppedReason'

# 対処:
- ECRイメージが正しいか確認
- IAMロールの権限確認
- セキュリティグループ確認
```

#### 問題2: ヘルスチェック失敗
```bash
# ログ確認
aws logs tail /ecs/estat-mcp --follow

# 対処:
- /healthエンドポイントが応答するか確認
- コンテナポート8080が開いているか確認
- セキュリティグループでALBからの通信許可確認
```

#### 問題3: SSL証明書エラー
```bash
# 証明書ステータス確認
aws acm describe-certificate \
  --certificate-arn <cert-arn>

# 対処:
- DNS検証レコードが正しいか確認
- Route 53のレコード確認
- 証明書の有効期限確認（自動更新）
```

---

## 9. Kiro設定

### 9.1 MCP設定ファイル
```json
{
  "mcpServers": {
    "estat-aws-remote": {
      "transport": "streamable-http",
      "url": "https://estat-mcp.snowmole.co.jp/mcp",
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

### 9.2 接続テスト
```bash
# ヘルスチェック
curl https://estat-mcp.snowmole.co.jp/health

# SSE接続テスト
curl -N -H "Accept: text/event-stream" \
  https://estat-mcp.snowmole.co.jp/mcp
```

---

## まとめ

このシステムは以下の特徴を持つ、本番環境対応のMCPサーバーです：

✅ **高可用性**: マルチAZ構成、ALBによる負荷分散
✅ **セキュア**: HTTPS/TLS暗号化、IAMロールベース認証
✅ **スケーラブル**: Fargateによる自動スケーリング
✅ **監視可能**: CloudWatch Logs、メトリクス、ヘルスチェック
✅ **コスト効率**: 約$33/月で運用可能
✅ **メンテナンス容易**: ローリングアップデート、簡単なロールバック

