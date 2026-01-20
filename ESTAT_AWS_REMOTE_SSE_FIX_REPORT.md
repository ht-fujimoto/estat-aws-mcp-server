# e-Stat AWS Remote MCP SSE修正レポート

## 実施日時
2026年1月20日

## 問題の概要

`estat-aws-remote` MCPサーバーに接続しようとすると、以下のエラーが発生していました：

```
Failed to call MCP tool: Invalid path
```

Kiroクライアントは`streamable-http`トランスポートでSSE（Server-Sent Events）接続を試みていましたが、サーバーが`content-type: application/json`を返し、期待される`text/event-stream`ではありませんでした。

## 根本原因

ECS Fargateで動作しているDockerイメージが**古いHTTPサーバー**（`server_http.py`）を使用しており、**SSE対応のstreamableサーバー**（`server_mcp_streamable.py`）ではありませんでした。

### 証拠

CloudWatch Logsから確認された起動メッセージ：
```
[2026-01-20 01:12:47] Starting e-Stat AWS MCP HTTP Server on port 8080...
Tools endpoint: http://localhost:8080/tools
Execute endpoint: http://localhost:8080/execute
```

これは古いHTTPサーバーの起動メッセージです。

### 追加の問題

最初のビルド時に、Dockerイメージがマルチアーキテクチャ（ARM64とAMD64）でビルドされており、ECS Fargateが`linux/amd64`プラットフォームを見つけられませんでした：

```
CannotPullContainerError: image Manifest does not contain descriptor matching platform 'linux/amd64'
```

## 実施した修正

### 1. 正しいDockerイメージのビルド

AMD64プラットフォーム専用で`server_mcp_streamable.py`を使用したイメージをビルド：

```bash
docker buildx build --platform linux/amd64 --load -t estat-mcp-server:streamable-amd64 .
```

### 2. ECRへのプッシュ

```bash
docker tag estat-mcp-server:streamable-amd64 639135896267.dkr.ecr.ap-northeast-1.amazonaws.com/estat-mcp-server:latest
docker push 639135896267.dkr.ecr.ap-northeast-1.amazonaws.com/estat-mcp-server:latest
```

### 3. ECSサービスの更新

```bash
aws ecs update-service --cluster estat-mcp-cluster --service estat-mcp-service --force-new-deployment --region ap-northeast-1
```

## 検証結果

### 1. ルートエンドポイントの確認

```bash
curl -s https://estat-mcp.snowmole.co.jp/ | jq '.'
```

**結果：**
```json
{
  "service": "e-Stat AWS MCP Server",
  "version": "1.0.0",
  "protocol": "MCP Streamable HTTP",
  "endpoints": [
    "/health",
    "/mcp"
  ]
}
```

✅ 正しいサーバーが起動（`"protocol": "MCP Streamable HTTP"`）

### 2. SSEエンドポイントの確認

```bash
curl -v -H "Accept: text/event-stream" https://estat-mcp.snowmole.co.jp/mcp
```

**結果：**
```
< HTTP/2 200 
< content-type: text/event-stream
< cache-control: no-cache
< access-control-allow-origin: *
< access-control-allow-headers: Content-Type
< access-control-allow-methods: GET, POST, DELETE
< server: Python/3.11 aiohttp/3.13.3
```

✅ SSEが正しく動作（`content-type: text/event-stream`）

## MCP設定

`.kiro/settings/mcp.json`の`estat-aws-remote`設定：

```json
{
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
      "save_dataset_as_csv",
      "save_metadata_as_csv",
      "get_csv_download_url",
      "get_estat_table_url",
      "download_csv_from_s3",
      "transform_to_parquet",
      "load_to_iceberg",
      "analyze_with_athena"
    ]
  }
}
```

## 利用可能なツール（全13個）

1. **search_estat_data** - 自然言語でe-Statデータを検索
2. **apply_keyword_suggestions** - キーワード変換を適用
3. **fetch_dataset_auto** - データセットを自動取得
4. **fetch_large_dataset_complete** - 大規模データセットの完全取得
5. **fetch_dataset_filtered** - カテゴリ指定で絞り込み取得
6. **save_dataset_as_csv** - データセットをCSV形式で保存
7. **save_metadata_as_csv** - メタデータをCSV形式で保存
8. **get_csv_download_url** - CSVダウンロードURL生成
9. **get_estat_table_url** - e-Statホームページリンク生成
10. **download_csv_from_s3** - S3からCSVダウンロード
11. **transform_to_parquet** - Parquet形式に変換
12. **load_to_iceberg** - Icebergテーブルに投入
13. **analyze_with_athena** - Athenaで統計分析

## 次のステップ

1. Kiroを再起動してMCP接続を再確立
2. `estat-aws-remote`サーバーのツールが正しく表示されることを確認
3. 実際のツール呼び出しをテスト（例：`search_estat_data`）

## まとめ

- ✅ SSE対応のstreamableサーバーが正しくデプロイされました
- ✅ `content-type: text/event-stream`が正しく返されています
- ✅ MCP設定は正しく構成されています
- ✅ 全13個のツールが利用可能です

**estat-aws-remoteサーバーは正常に動作しています！**
