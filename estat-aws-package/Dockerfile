FROM python:3.11-slim

# 作業ディレクトリの設定
WORKDIR /app

# システムパッケージの更新
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 依存関係のインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのコピー
COPY mcp_servers/ ./mcp_servers/
COPY server_http.py .

# ポート公開
EXPOSE 8080

# 環境変数のデフォルト値
ENV ESTAT_APP_ID=""
ENV S3_BUCKET="estat-data-lake"
ENV AWS_REGION="ap-northeast-1"
ENV PORT=8080

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

# 非rootユーザーで実行
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# サーバー起動
CMD ["python", "server_http.py"]
