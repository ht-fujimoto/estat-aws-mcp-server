# DNS検証レコード追加ガイド

## 現在の状況

ACM証明書がDNS検証を待っています。

**証明書ARN**: `arn:aws:acm:ap-northeast-1:639135896267:certificate/01bd1f7b-7b80-447d-81e2-e86e79974055`

## 追加が必要なDNSレコード

### 検証レコード（必須）

```
タイプ: CNAME
名前: _6ae8112390b0998bc5656a3421841353.estat-mcp.snowmole.co.jp.
値: _bfbc9b80f0a084833416d5001ebd2218.jkddzztszm.acm-validations.aws.
TTL: 300
```

## DNS管理画面での設定方法

### パターン1: お名前.com

1. お名前.comにログイン
2. ドメイン設定 → DNS設定
3. snowmole.co.jp を選択
4. DNSレコード設定を追加

**設定値:**
```
ホスト名: _6ae8112390b0998bc5656a3421841353.estat-mcp
TYPE: CNAME
VALUE: _bfbc9b80f0a084833416d5001ebd2218.jkddzztszm.acm-validations.aws.
TTL: 300
```

⚠️ 注意: ホスト名には `.snowmole.co.jp` を含めない

### パターン2: Route 53

1. AWS Console → Route 53
2. ホストゾーン → snowmole.co.jp
3. レコードを作成

**設定値:**
```
レコード名: _6ae8112390b0998bc5656a3421841353.estat-mcp.snowmole.co.jp
レコードタイプ: CNAME
値: _bfbc9b80f0a084833416d5001ebd2218.jkddzztszm.acm-validations.aws.
TTL: 300
```

### パターン3: その他のDNSプロバイダー

**設定値:**
```
Name/Host: _6ae8112390b0998bc5656a3421841353.estat-mcp.snowmole.co.jp
Type: CNAME
Value/Target: _bfbc9b80f0a084833416d5001ebd2218.jkddzztszm.acm-validations.aws.
TTL: 300
```

## 確認方法

### 方法1: AWS CLIで確認

```bash
aws acm describe-certificate \
  --certificate-arn arn:aws:acm:ap-northeast-1:639135896267:certificate/01bd1f7b-7b80-447d-81e2-e86e79974055 \
  --region ap-northeast-1 \
  --query 'Certificate.Status' \
  --output text
```

`ISSUED` になれば成功

### 方法2: DNSクエリで確認

```bash
host -t CNAME _6ae8112390b0998bc5656a3421841353.estat-mcp.snowmole.co.jp
```

CNAMEレコードが返ってくれば伝播済み

### 方法3: 自動監視スクリプト

```bash
./check_acm_status.sh
```

30秒ごとに自動確認

## よくある問題

### 問題1: レコードを追加したのに検証されない

**原因:**
- DNS伝播に時間がかかっている（5〜30分）
- レコード名が間違っている
- TTLが長すぎる

**解決策:**
1. DNS管理画面でレコードを再確認
2. 10〜15分待つ
3. DNSキャッシュをクリア

### 問題2: ホスト名の入力方法がわからない

**お名前.comの場合:**
```
❌ 間違い: _6ae8112390b0998bc5656a3421841353.estat-mcp.snowmole.co.jp
✅ 正しい: _6ae8112390b0998bc5656a3421841353.estat-mcp
```

**Route 53の場合:**
```
✅ 正しい: _6ae8112390b0998bc5656a3421841353.estat-mcp.snowmole.co.jp
```

### 問題3: 値の末尾のドット

**重要:** 値の末尾のドット(`.`)は**含めても含めなくても**OK

```
✅ OK: _bfbc9b80f0a084833416d5001ebd2218.jkddzztszm.acm-validations.aws.
✅ OK: _bfbc9b80f0a084833416d5001ebd2218.jkddzztszm.acm-validations.aws
```

## タイムライン

| 時間 | 状態 |
|------|------|
| 0分 | DNSレコード追加 |
| 5分 | DNS伝播開始 |
| 10分 | 多くの場合、伝播完了 |
| 15分 | ほぼ確実に伝播完了 |
| 30分 | 最大待機時間 |

## 次のステップ

証明書が `ISSUED` になったら:

```bash
export CERT_ARN=arn:aws:acm:ap-northeast-1:639135896267:certificate/01bd1f7b-7b80-447d-81e2-e86e79974055
./continue_acm_setup.sh
```

## 現在のステータス確認

```bash
# ステータス確認
aws acm describe-certificate \
  --certificate-arn arn:aws:acm:ap-northeast-1:639135896267:certificate/01bd1f7b-7b80-447d-81e2-e86e79974055 \
  --region ap-northeast-1 \
  --query 'Certificate.Status' \
  --output text

# DNS伝播確認
host -t CNAME _6ae8112390b0998bc5656a3421841353.estat-mcp.snowmole.co.jp
```

---

**現在の状態**: ⏳ DNS検証待ち  
**必要なアクション**: snowmole.co.jpのDNS管理画面でCNAMEレコードを追加
