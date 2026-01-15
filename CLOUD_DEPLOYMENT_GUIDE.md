# クラウドMCPサーバー デプロイメントガイド

MCPサーバーをクラウドにデプロイして、どの環境からもアクセスできるようにする方法を説明します。

## 目次
1. [アーキテクチャ概要](#1-アーキテクチャ概要)
2. [AWS Lambda + API Gateway](#2-aws-lambda--api-gateway)
3. [AWS ECS/Fargate](#3-aws-ecsfargate)
4. [Google Cloud Run](#4-google-cloud-run)
5. [Heroku](#5-heroku)
6. [Docker + EC2/VPS](#6-docker--ec2vps)
7. [セキュリティ設定](#7-セキュリティ設定)

---

## 1. アーキテクチャ概要

### MCPサーバーのクラウド化の選択肢

| 方法 | コスト | 難易度 | スケーラビリティ | 推奨用途 |
|------|--------|--------|------------------|----------|
| **AWS Lambda** | 低 | 中 | 自動 | サーバーレス、従量課金 |
| **AWS ECS/Fargate** | 中 | 高 | 自動 | コンテナベース、本格運用 |
| **Google Cloud Run** | 低 | 低 | 自動 | 最も簡単、従量課金 |
| **Heroku** | 中 | 低 | 手動 | 最速デプロイ |
| **EC2/VPS** | 中〜高 | 中 | 手動 | フルコントロール |

### 基本的なアーキテクチャ

```
クライアント（Kiro/Cline）
    ↓ HTTPS
API Gateway / Load Balancer
    ↓
MCPサーバー（クラウド）
    ↓
e-Stat API / AWS S3
```

---

## 2. AWS Lambda + API Gateway

### メリット
- サーバーレスで管理不要
- 従量課金（使った分だけ）
- 自動スケーリング
- 無料枠あり（月100万リクエスト）

### デメリット
- コールドスタート（初回起動が遅い）
- 実行時間制限（最大15分）
- メモリ制限

### 2.1 Lambda関数の作成

#### handler.py
```python
import json
import os
import sys

# MCPサーバーのインポート
sys.path.append(os.path.dirname(__file__))
from estat_mcp_server.server import MCPServer

# グローバルでインスタンス化（コールドスタート対策）
mcp_server = MCPServer()

def lambda_handler(event, context):
    """
    Lambda関数のエントリーポイント
    """
    try:
        # HTTPメソッドとパスを取得
        http_method = event.get('httpMethod', 'POST')
        path = event.get('path', '/')
        
        # リクエストボディを取得
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)
        
        # MCPリクエストの処理
        if path == '/tools':
            # ツール一覧を返す
            tools = mcp_server.get_tools()
            response_body = {
                'success': True,
                'tools': tools
            }
        
        elif path == '/execute':
            # ツールを実行
            tool_name = body.get('tool_name')
            arguments = body.get('arguments', {})
            
            result = mcp_server.execute_tool(tool_name, arguments)
            response_body = {
                'success': True,
                'result': result
            }
        
        else:
            response_body = {
                'success': False,
                'error': 'Invalid path'
            }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization'
            },
            'body': json.dumps(response_body)
        }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }
```

#### requirements.txt（Lambda用）
```
requests>=2.28.0
boto3>=1.26.0
pandas>=1.5.0
pyarrow>=10.0.0
```

### 2.2 デプロイスクリプト

#### deploy_lambda.sh
```bash
#!/bin/bash

# 設定
FUNCTION_NAME="estat-mcp-server"
REGION="ap-northeast-1"
ROLE_ARN="arn:aws:iam::YOUR_ACCOUNT_ID:role/lambda-execution-role"

# パッケージング
echo "Creating deployment package..."
mkdir -p lambda_package
pip install -r requirements.txt -t lambda_package/
cp -r estat_mcp_server lambda_package/
cp handler.py lambda_package/

# ZIP作成
cd lambda_package
zip -r ../lambda_function.zip .
cd ..

# Lambda関数の作成または更新
echo "Deploying to Lambda..."
aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --zip-file fileb://lambda_function.zip \
    --region $REGION

# 環境変数の設定
aws lambda update-function-configuration \
    --function-name $FUNCTION_NAME \
    --environment "Variables={ESTAT_APP_ID=$ESTAT_APP_ID,S3_BUCKET=$S3_BUCKET}" \
    --region $REGION

echo "Deployment complete!"
```

### 2.3 API Gatewayの設定

```bash
# API Gatewayの作成
aws apigateway create-rest-api \
    --name "estat-mcp-api" \
    --description "e-Stat MCP Server API"

# リソースとメソッドの作成
# （AWS Consoleで設定するのが簡単）
```

### 2.4 クライアント設定

```json
{
  "mcpServers": {
    "estat-cloud": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "https://your-api-id.execute-api.ap-northeast-1.amazonaws.com/prod/execute",
        "-H", "Content-Type: application/json",
        "-d", "@-"
      ]
    }
  }
}
```

---

## 3. AWS ECS/Fargate

### メリット
- Dockerコンテナで実行
- 本格的な運用に適している
- 長時間実行可能
- フルコントロール

### 3.1 Dockerfileの作成

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 依存関係のインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのコピー
COPY estat_mcp_server/ ./estat_mcp_server/
COPY server_http.py .

# ポート公開
EXPOSE 8080

# 環境変数
ENV ESTAT_APP_ID=""
ENV S3_BUCKET="estat-data-lake"
ENV PORT=8080

# サーバー起動
CMD ["python", "server_http.py"]
```

### 3.2 HTTPサーバーの作成

#### server_http.py
```python
#!/usr/bin/env python3
"""
HTTP wrapper for MCP Server
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
from estat_mcp_server.server import MCPServer

PORT = int(os.environ.get('PORT', 8080))
mcp_server = MCPServer()

class MCPHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            request = json.loads(post_data.decode('utf-8'))
            
            if self.path == '/tools':
                tools = mcp_server.get_tools()
                response = {'success': True, 'tools': tools}
            
            elif self.path == '/execute':
                tool_name = request.get('tool_name')
                arguments = request.get('arguments', {})
                result = mcp_server.execute_tool(tool_name, arguments)
                response = {'success': True, 'result': result}
            
            else:
                response = {'success': False, 'error': 'Invalid path'}
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
        
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = {'success': False, 'error': str(e)}
            self.wfile.write(json.dumps(error_response).encode('utf-8'))
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), MCPHandler)
    print(f'Starting MCP HTTP Server on port {PORT}...')
    server.serve_forever()
```

### 3.3 ECSデプロイスクリプト

#### deploy_ecs.sh
```bash
#!/bin/bash

# 設定
AWS_REGION="ap-northeast-1"
ECR_REPO="estat-mcp-server"
CLUSTER_NAME="estat-mcp-cluster"
SERVICE_NAME="estat-mcp-service"

# ECRにログイン
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin \
    YOUR_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Dockerイメージのビルド
docker build -t $ECR_REPO:latest .

# ECRにプッシュ
docker tag $ECR_REPO:latest \
    YOUR_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest
docker push YOUR_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest

# ECSサービスの更新
aws ecs update-service \
    --cluster $CLUSTER_NAME \
    --service $SERVICE_NAME \
    --force-new-deployment \
    --region $AWS_REGION

echo "Deployment complete!"
```

---

## 4. Google Cloud Run

### メリット
- **最も簡単**にデプロイ可能
- サーバーレス
- 自動スケーリング
- 無料枠あり

### 4.1 デプロイ手順

```bash
# Google Cloud SDKのインストール（初回のみ）
# https://cloud.google.com/sdk/docs/install

# プロジェクトの設定
gcloud config set project YOUR_PROJECT_ID

# Dockerfileを使ってデプロイ
gcloud run deploy estat-mcp-server \
    --source . \
    --platform managed \
    --region asia-northeast1 \
    --allow-unauthenticated \
    --set-env-vars ESTAT_APP_ID=$ESTAT_APP_ID,S3_BUCKET=$S3_BUCKET

# デプロイ完了後、URLが表示される
# https://estat-mcp-server-xxxxx-an.a.run.app
```

### 4.2 クライアント設定

```json
{
  "mcpServers": {
    "estat-cloud": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "https://estat-mcp-server-xxxxx-an.a.run.app/execute",
        "-H", "Content-Type: application/json",
        "-d", "@-"
      ]
    }
  }
}
```

---

## 5. Heroku

### メリット
- 最速でデプロイ可能
- Git pushだけでデプロイ
- 無料枠あり（制限付き）

### 5.1 Procfileの作成

```
web: python server_http.py
```

### 5.2 デプロイ手順

```bash
# Heroku CLIのインストール（初回のみ）
# https://devcenter.heroku.com/articles/heroku-cli

# ログイン
heroku login

# アプリケーションの作成
heroku create estat-mcp-server

# 環境変数の設定
heroku config:set ESTAT_APP_ID=your_api_key
heroku config:set S3_BUCKET=estat-data-lake

# デプロイ
git push heroku main

# URLの確認
heroku open
```

---

## 6. Docker + EC2/VPS

### メリット
- フルコントロール
- カスタマイズ自由
- 長期運用に適している

### 6.1 docker-compose.yml

```yaml
version: '3.8'

services:
  estat-mcp-server:
    build: .
    ports:
      - "8080:8080"
    environment:
      - ESTAT_APP_ID=${ESTAT_APP_ID}
      - S3_BUCKET=${S3_BUCKET}
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
    restart: always
    volumes:
      - ./logs:/app/logs
    networks:
      - mcp-network

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - estat-mcp-server
    networks:
      - mcp-network

networks:
  mcp-network:
    driver: bridge
```

### 6.2 nginx.conf

```nginx
events {
    worker_connections 1024;
}

http {
    upstream mcp_server {
        server estat-mcp-server:8080;
    }

    server {
        listen 80;
        server_name your-domain.com;
        
        # HTTPSへリダイレクト
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl;
        server_name your-domain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        location / {
            proxy_pass http://mcp_server;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

### 6.3 デプロイスクリプト

```bash
#!/bin/bash

# EC2/VPSにSSH接続して実行

# Dockerのインストール（初回のみ）
sudo yum update -y
sudo yum install -y docker
sudo service docker start
sudo usermod -a -G docker ec2-user

# Docker Composeのインストール
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# アプリケーションのデプロイ
git clone https://github.com/yourusername/estat-mcp-server.git
cd estat-mcp-server

# 環境変数の設定
cp .env.example .env
nano .env  # APIキーなどを設定

# 起動
docker-compose up -d

# ログの確認
docker-compose logs -f
```

---

## 7. セキュリティ設定

### 7.1 API認証の追加

#### auth_middleware.py
```python
import os
import hashlib
import hmac
from functools import wraps

API_KEY = os.environ.get('MCP_API_KEY', '')

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        request = args[0]  # 最初の引数がリクエスト
        
        # ヘッダーからAPIキーを取得
        provided_key = request.headers.get('X-API-Key', '')
        
        # APIキーの検証
        if not hmac.compare_digest(provided_key, API_KEY):
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Unauthorized'})
            }
        
        return f(*args, **kwargs)
    
    return decorated_function
```

### 7.2 レート制限

```python
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests=100, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
    
    def is_allowed(self, client_id):
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)
        
        # 古いリクエストを削除
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > cutoff
        ]
        
        # レート制限チェック
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        self.requests[client_id].append(now)
        return True
```

### 7.3 HTTPS/TLS設定

```bash
# Let's Encryptで無料SSL証明書を取得
sudo certbot --nginx -d your-domain.com
```

### 7.4 環境変数の暗号化

```bash
# AWS Systems Manager Parameter Storeを使用
aws ssm put-parameter \
    --name "/estat-mcp/api-key" \
    --value "your_api_key" \
    --type "SecureString" \
    --region ap-northeast-1

# Lambda/ECSから取得
import boto3

ssm = boto3.client('ssm', region_name='ap-northeast-1')
response = ssm.get_parameter(Name='/estat-mcp/api-key', WithDecryption=True)
api_key = response['Parameter']['Value']
```

---

## 8. モニタリングとログ

### 8.1 CloudWatch Logs（AWS）

```python
import boto3
import logging

# CloudWatch Logsの設定
cloudwatch = boto3.client('logs')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def log_to_cloudwatch(message):
    cloudwatch.put_log_events(
        logGroupName='/aws/lambda/estat-mcp-server',
        logStreamName='requests',
        logEvents=[{
            'timestamp': int(time.time() * 1000),
            'message': message
        }]
    )
```

### 8.2 コスト最適化

```bash
# Lambda: メモリとタイムアウトの最適化
aws lambda update-function-configuration \
    --function-name estat-mcp-server \
    --memory-size 512 \
    --timeout 30

# ECS: オートスケーリングの設定
aws application-autoscaling register-scalable-target \
    --service-namespace ecs \
    --scalable-dimension ecs:service:DesiredCount \
    --resource-id service/estat-mcp-cluster/estat-mcp-service \
    --min-capacity 1 \
    --max-capacity 10
```

---

## 9. 推奨デプロイ方法

### 初心者向け
1. **Google Cloud Run**（最も簡単）
2. **Heroku**（Git pushだけ）

### 中級者向け
1. **AWS Lambda + API Gateway**（サーバーレス）
2. **Docker + VPS**（フルコントロール）

### 本格運用
1. **AWS ECS/Fargate**（スケーラブル）
2. **Kubernetes**（大規模）

---

## 10. トラブルシューティング

### コールドスタートが遅い
- Lambda: Provisioned Concurrencyを使用
- Cloud Run: 最小インスタンス数を設定

### メモリ不足
- Lambda: メモリサイズを増やす（最大10GB）
- ECS: タスク定義でメモリを増やす

### タイムアウト
- Lambda: タイムアウトを延長（最大15分）
- 長時間処理: ECS/Fargateを使用

---

これで、MCPサーバーをクラウドにデプロイして、どこからでもアクセスできるようになります！
