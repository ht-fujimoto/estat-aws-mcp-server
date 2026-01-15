# estat-aws セットアップガイド - 他の環境での使用方法

このガイドでは、estat-awsを他の環境（別のプロジェクト、別のマシン、チームメンバーなど）で使用する方法を説明します。

---

## 📋 前提条件

### 必須
- Python 3.11以上
- Kiro IDE（MCPクライアント）
- e-Stat APIキー（[こちら](https://www.e-stat.go.jp/api/)から取得）

### オプション（AWS機能を使用する場合）
- AWSアカウント
- AWS CLI設定済み
- S3バケット
- Athena/Glueへのアクセス権限

---

## 🚀 セットアップ方法

### 方法1: 既存のECS Fargateサービスを使用（推奨）

この方法は、既にデプロイされているECS Fargateサービスを使用します。最も簡単で、AWS設定が不要です。

#### ステップ1: 必要なファイルをコピー

以下のファイルを新しい環境にコピーします：

```bash
your-new-project/
├── mcp_aws_wrapper.py          # MCPブリッジ（必須）
└── .kiro/
    └── settings/
        └── mcp.json            # Kiro設定ファイル
```

#### ステップ2: mcp_aws_wrapper.pyの確認

`mcp_aws_wrapper.py`を開き、API URLを確認します：

```python
# 現在のALB URL
API_URL = "http://estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com"
```

このURLは現在稼働中のECS Fargateサービスを指しています。

#### ステップ3: Kiro設定ファイルの作成

`.kiro/settings/mcp.json`を作成または編集します：

```json
{
  "mcpServers": {
    "estat-aws": {
      "command": "python3",
      "args": ["mcp_aws_wrapper.py"],
      "env": {
        "ESTAT_APP_ID": "your-estat-api-key-here",
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

**重要**: `your-estat-api-key-here`を実際のe-Stat APIキーに置き換えてください。

#### ステップ4: 動作確認

Kiro IDEを再起動し、以下のコマンドで動作確認します：

```bash
# ローカルでテスト
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 mcp_aws_wrapper.py
```

10個のツールが表示されれば成功です！

---

### 方法2: 独自のECS Fargateサービスをデプロイ

この方法は、独自のAWS環境にestat-awsをデプロイします。

#### 前提条件
- AWSアカウント
- AWS CLI設定済み
- Docker Desktop（またはDocker）
- 以下のAWSリソースへのアクセス権限：
  - ECS
  - ECR
  - ALB
  - IAM
  - S3
  - Athena
  - Glue

#### ステップ1: 必要なファイルをコピー

```bash
your-new-project/
├── mcp_servers/
│   └── estat_aws/
│       ├── __init__.py
│       ├── server.py
│       ├── keyword_dictionary.py
│       └── utils/
│           ├── __init__.py
│           ├── error_handler.py
│           ├── retry.py
│           ├── logger.py
│           └── response_formatter.py
├── server_http.py
├── mcp_aws_wrapper.py
├── Dockerfile
├── requirements.txt
├── task-definition.json
└── deploy_ecs_fargate.sh
```

#### ステップ2: AWS環境変数の設定

```bash
export AWS_ACCOUNT_ID="your-aws-account-id"
export AWS_REGION="ap-northeast-1"  # または任意のリージョン
export ESTAT_APP_ID="your-estat-api-key"
export S3_BUCKET="your-s3-bucket-name"
```

#### ステップ3: S3バケットの作成

```bash
aws s3 mb s3://${S3_BUCKET} --region ${AWS_REGION}

# バケットポリシーの設定（後で実施）
```

#### ステップ4: ECRリポジトリの作成

```bash
aws ecr create-repository \
  --repository-name estat-mcp-server \
  --region ${AWS_REGION}
```

#### ステップ5: IAMロールの作成

**A. タスク実行ロール（ecsTaskExecutionRole）**

既に存在する場合はスキップ。存在しない場合：

```bash
# 信頼ポリシー
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# ロール作成
aws iam create-role \
  --role-name ecsTaskExecutionRole \
  --assume-role-policy-document file://trust-policy.json

# 管理ポリシーをアタッチ
aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

**B. タスクロール（estatMcpTaskRole）**

```bash
# ロール作成
aws iam create-role \
  --role-name estatMcpTaskRole \
  --assume-role-policy-document file://trust-policy.json

# タスクポリシー
cat > task-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::${S3_BUCKET}",
        "arn:aws:s3:::${S3_BUCKET}/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:StopQueryExecution",
        "athena:GetWorkGroup"
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
        "glue:GetPartitions",
        "glue:CreateDatabase"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# ポリシーをアタッチ
aws iam put-role-policy \
  --role-name estatMcpTaskRole \
  --policy-name estatMcpTaskPolicy \
  --policy-document file://task-policy.json
```

#### ステップ6: S3バケットポリシーの設定

```bash
cat > bucket-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowECSTaskRole",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/estatMcpTaskRole"
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::${S3_BUCKET}",
        "arn:aws:s3:::${S3_BUCKET}/*"
      ]
    }
  ]
}
EOF

aws s3api put-bucket-policy \
  --bucket ${S3_BUCKET} \
  --policy file://bucket-policy.json
```

#### ステップ7: Athenaワークグループの作成

```bash
aws athena create-work-group \
  --name estat-mcp-workgroup \
  --description "e-Stat MCP Server workgroup" \
  --configuration "{
    \"ResultConfiguration\": {
      \"OutputLocation\": \"s3://${S3_BUCKET}/athena-results/\"
    },
    \"EnforceWorkGroupConfiguration\": false
  }" \
  --region ${AWS_REGION}
```

#### ステップ8: Glueデータベースの作成

```bash
aws glue create-database \
  --database-input "{
    \"Name\": \"estat_db\",
    \"Description\": \"e-Stat統計データ用データベース\",
    \"LocationUri\": \"s3://${S3_BUCKET}/iceberg/\"
  }" \
  --region ${AWS_REGION}
```

#### ステップ9: task-definition.jsonの編集

`task-definition.json`を開き、以下を更新します：

```json
{
  "family": "estat-mcp-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/estatMcpTaskRole",
  "containerDefinitions": [
    {
      "name": "estat-mcp-container",
      "image": "YOUR_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/estat-mcp-server:latest",
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ESTAT_APP_ID",
          "value": "YOUR_ESTAT_API_KEY"
        },
        {
          "name": "S3_BUCKET",
          "value": "YOUR_S3_BUCKET"
        },
        {
          "name": "AWS_REGION",
          "value": "YOUR_REGION"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/estat-mcp",
          "awslogs-region": "YOUR_REGION",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### ステップ10: CloudWatch Logsグループの作成

```bash
aws logs create-log-group \
  --log-group-name /ecs/estat-mcp \
  --region ${AWS_REGION}
```

#### ステップ11: デプロイスクリプトの実行

`deploy_ecs_fargate.sh`を編集して、変数を更新します：

```bash
#!/bin/bash

# 変数設定
AWS_ACCOUNT_ID="your-account-id"
AWS_REGION="ap-northeast-1"
ECR_REPOSITORY="estat-mcp-server"
CLUSTER_NAME="estat-mcp-cluster"
SERVICE_NAME="estat-mcp-service"
TASK_FAMILY="estat-mcp-task"

# ... 以下スクリプト内容 ...
```

実行：

```bash
chmod +x deploy_ecs_fargate.sh
./deploy_ecs_fargate.sh
```

#### ステップ12: ALB URLの取得

デプロイが完了したら、ALB URLを取得します：

```bash
aws elbv2 describe-load-balancers \
  --names estat-mcp-alb \
  --region ${AWS_REGION} \
  --query 'LoadBalancers[0].DNSName' \
  --output text
```

#### ステップ13: mcp_aws_wrapper.pyの更新

取得したALB URLで`mcp_aws_wrapper.py`を更新します：

```python
# ALB URLを更新
API_URL = "http://your-alb-url-here.elb.amazonaws.com"
```

#### ステップ14: Kiro設定

方法1のステップ3と同じ手順でKiro設定を行います。

---

### 方法3: ローカル開発環境で使用

この方法は、ローカルでserver_http.pyを直接実行します。開発・テスト用です。

#### ステップ1: 依存関係のインストール

```bash
pip install -r requirements.txt
```

#### ステップ2: 環境変数の設定

```bash
export ESTAT_APP_ID="your-estat-api-key"
export S3_BUCKET="your-s3-bucket"  # オプション
export AWS_REGION="ap-northeast-1"  # オプション
export PORT=8080
```

#### ステップ3: サーバーの起動

```bash
python3 server_http.py
```

別のターミナルで動作確認：

```bash
curl http://localhost:8080/health
curl http://localhost:8080/tools
```

#### ステップ4: mcp_aws_wrapper.pyの更新

```python
# ローカルサーバーを使用
API_URL = "http://localhost:8080"
```

#### ステップ5: Kiro設定

方法1のステップ3と同じ手順でKiro設定を行います。

---

## 🔧 トラブルシューティング

### 問題1: ツールが表示されない

**原因**: mcp_aws_wrapper.pyのパスが正しくない

**解決策**:
```json
{
  "mcpServers": {
    "estat-aws": {
      "command": "python3",
      "args": ["/absolute/path/to/mcp_aws_wrapper.py"],  // 絶対パスを使用
      ...
    }
  }
}
```

### 問題2: API接続エラー

**原因**: ALB URLが間違っている、またはサービスが停止している

**解決策**:
```bash
# サービスの状態確認
curl http://your-alb-url/health

# ECSサービスの確認
aws ecs describe-services \
  --cluster estat-mcp-cluster \
  --services estat-mcp-service \
  --region ap-northeast-1
```

### 問題3: S3アクセスエラー

**原因**: IAMロールまたはバケットポリシーの権限不足

**解決策**:
1. IAMロールの権限を確認
2. S3バケットポリシーを確認
3. バケットが存在することを確認

```bash
aws s3 ls s3://your-bucket-name/
```

### 問題4: Athenaクエリエラー

**原因**: ワークグループが設定されていない

**解決策**:
```bash
# ワークグループの確認
aws athena get-work-group \
  --work-group estat-mcp-workgroup \
  --region ap-northeast-1

# 存在しない場合は作成
aws athena create-work-group \
  --name estat-mcp-workgroup \
  --configuration "{
    \"ResultConfiguration\": {
      \"OutputLocation\": \"s3://your-bucket/athena-results/\"
    }
  }"
```

---

## 📝 チェックリスト

### 方法1（既存サービス使用）の場合
- [ ] mcp_aws_wrapper.pyをコピー
- [ ] .kiro/settings/mcp.jsonを作成
- [ ] e-Stat APIキーを設定
- [ ] Kiro IDEを再起動
- [ ] 動作確認（tools/list）

### 方法2（独自デプロイ）の場合
- [ ] 全ファイルをコピー
- [ ] AWS環境変数を設定
- [ ] S3バケットを作成
- [ ] ECRリポジトリを作成
- [ ] IAMロールを作成（2つ）
- [ ] S3バケットポリシーを設定
- [ ] Athenaワークグループを作成
- [ ] Glueデータベースを作成
- [ ] task-definition.jsonを編集
- [ ] CloudWatch Logsグループを作成
- [ ] デプロイスクリプトを実行
- [ ] ALB URLを取得
- [ ] mcp_aws_wrapper.pyを更新
- [ ] Kiro設定を作成
- [ ] 動作確認

### 方法3（ローカル開発）の場合
- [ ] 依存関係をインストール
- [ ] 環境変数を設定
- [ ] server_http.pyを起動
- [ ] mcp_aws_wrapper.pyを更新
- [ ] Kiro設定を作成
- [ ] 動作確認

---

## 🎯 推奨される使用方法

| 用途 | 推奨方法 | 理由 |
|------|---------|------|
| 個人利用 | 方法1 | 最も簡単、設定不要 |
| チーム共有 | 方法1 | 全員が同じサービスを使用 |
| 本番環境 | 方法2 | 独自のAWS環境で管理 |
| 開発・テスト | 方法3 | ローカルで素早く試せる |
| セキュリティ重視 | 方法2 | 独自の権限管理 |

---

## 📚 参考資料

- [e-Stat API仕様書](https://www.e-stat.go.jp/api/api-info/api-spec)
- [AWS ECS Fargate ドキュメント](https://docs.aws.amazon.com/ecs/latest/developerguide/AWS_Fargate.html)
- [MCP (Model Context Protocol)](https://modelcontextprotocol.io/)

---

## 💡 ヒント

### 環境変数の管理

`.env`ファイルを使用すると便利です：

```bash
# .env
ESTAT_APP_ID=your-api-key
S3_BUCKET=your-bucket
AWS_REGION=ap-northeast-1
```

```bash
# 読み込み
source .env
```

### 複数環境の管理

環境ごとに異なる設定を使用する場合：

```json
{
  "mcpServers": {
    "estat-aws-prod": {
      "command": "python3",
      "args": ["mcp_aws_wrapper.py"],
      "env": {
        "ESTAT_APP_ID": "prod-api-key",
        ...
      }
    },
    "estat-aws-dev": {
      "command": "python3",
      "args": ["mcp_aws_wrapper_dev.py"],
      "env": {
        "ESTAT_APP_ID": "dev-api-key",
        ...
      }
    }
  }
}
```

---

**作成日**: 2026年1月9日  
**バージョン**: 1.0.0  
**対象**: estat-aws v1.1.0
