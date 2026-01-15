# HTTPS対応オプションガイド

## 現状

Kiroは**HTTPS接続を要求**し、自己署名証明書を受け入れません。
現在はHTTPで動作していますが、Kiroのセキュリティポリシーに準拠するため、HTTPS対応が必要です。

## 選択肢の比較

| 方法 | コスト | 難易度 | 所要時間 | 推奨度 |
|------|--------|--------|----------|--------|
| **ACM証明書** | ドメイン代のみ（年1,000円〜） | 中 | 30分〜1時間 | ⭐⭐⭐⭐⭐ |
| **CloudFlare Tunnel** | 完全無料 | 中 | 30分 | ⭐⭐⭐⭐ |
| **Let's Encrypt** | ドメイン代のみ | 高 | 1時間〜 | ⭐⭐⭐ |
| **ローカルwrapper** | 無料 | 低 | 5分 | ⭐⭐ |

## オプション1: AWS Certificate Manager (ACM) 【推奨】

### メリット
- ✅ AWS公式の証明書サービス
- ✅ 証明書は無料
- ✅ 自動更新
- ✅ ALBと完全統合
- ✅ Kiroが信頼する正式な証明書

### デメリット
- ❌ ドメイン名が必要（年間約1,000円〜）

### 手順

```bash
chmod +x setup_acm_certificate.sh
./setup_acm_certificate.sh
```

スクリプトが以下を自動実行:
1. ACM証明書をリクエスト
2. DNS検証レコードを取得
3. Route 53にレコードを追加（オプション）
4. 証明書の検証を待機
5. ALBにHTTPSリスナーを追加
6. Kiro設定を更新

### コスト
- **ドメイン名**: 年間約1,000円〜（Route 53）
  - .com: 約1,200円/年
  - .net: 約1,200円/年
  - .jp: 約3,000円/年
- **証明書**: 無料
- **合計**: 約1,000円/年

## オプション2: CloudFlare Tunnel 【無料】

### メリット
- ✅ 完全無料
- ✅ ドメイン名不要（CloudFlareが提供）
- ✅ HTTPS自動対応
- ✅ DDoS保護付き

### デメリット
- ❌ CloudFlareアカウントが必要
- ❌ トンネルプロセスを常時起動

### 手順

1. **CloudFlareアカウント作成**
   ```
   https://dash.cloudflare.com/sign-up
   ```

2. **cloudflaredインストール**
   ```bash
   brew install cloudflare/cloudflare/cloudflared
   ```

3. **ログイン**
   ```bash
   cloudflared tunnel login
   ```

4. **トンネル作成**
   ```bash
   cloudflared tunnel create estat-mcp
   ```

5. **設定ファイル作成**
   ```yaml
   # ~/.cloudflared/config.yml
   tunnel: <TUNNEL_ID>
   credentials-file: ~/.cloudflared/<TUNNEL_ID>.json
   
   ingress:
     - hostname: estat-mcp-<random>.trycloudflare.com
       service: http://estat-mcp-alb-633149734.ap-northeast-1.elb.amazonaws.com
     - service: http_status:404
   ```

6. **トンネル起動**
   ```bash
   cloudflared tunnel run estat-mcp
   ```

7. **Kiro設定更新**
   ```json
   {
     "url": "https://estat-mcp-<random>.trycloudflare.com"
   }
   ```

### コスト
- **すべて無料**

## オプション3: Let's Encrypt

### メリット
- ✅ 証明書は無料
- ✅ 広く信頼されている

### デメリット
- ❌ ドメイン名が必要
- ❌ 90日ごとに更新が必要
- ❌ 設定が複雑

### 手順

1. **ドメイン取得**
2. **Certbotインストール**
3. **証明書取得**
4. **ACMにインポート**
5. **自動更新設定**

詳細は省略（複雑なため非推奨）

## オプション4: ローカルwrapper（現在の方式）

### メリット
- ✅ 完全無料
- ✅ 設定が簡単
- ✅ すぐに使える

### デメリット
- ❌ ローカルプロセスが必要
- ❌ 完全なHTTPトランスポートではない

### 手順

```bash
chmod +x switch_to_local.sh
./switch_to_local.sh
```

Kiroを再起動

### アーキテクチャ
```
Kiro → python3 mcp_aws_wrapper.py (ローカル) → HTTP → ECS Fargate
```

## 推奨フロー

### 個人利用・開発環境
1. **まず**: ローカルwrapperで動作確認（現在の状態）
2. **次に**: CloudFlare Tunnelで無料HTTPS対応
3. **将来**: ACMで本格運用

### 本番環境・チーム利用
1. **Route 53でドメイン取得**（年間1,000円〜）
2. **ACM証明書を取得**（無料）
3. **ALBにHTTPS設定**
4. **Kiro設定を更新**

## 実行コマンド

### ACM証明書（推奨）
```bash
chmod +x setup_acm_certificate.sh
./setup_acm_certificate.sh
```

### CloudFlare Tunnel（無料）
```bash
chmod +x setup_cloudflare_tunnel.sh
./setup_cloudflare_tunnel.sh
```

### ローカルwrapper（一時的）
```bash
chmod +x switch_to_local.sh
./switch_to_local.sh
```

## よくある質問

### Q1: どの方法が一番おすすめですか？

**A**: 用途によります:
- **個人利用**: CloudFlare Tunnel（無料）
- **本番環境**: ACM証明書（年1,000円〜）
- **一時的**: ローカルwrapper（無料）

### Q2: ドメイン名は必須ですか？

**A**: 
- ACM: 必須
- CloudFlare Tunnel: 不要（CloudFlareが提供）
- Let's Encrypt: 必須
- ローカルwrapper: 不要

### Q3: 証明書の更新は必要ですか？

**A**:
- ACM: 自動更新（不要）
- CloudFlare: 自動更新（不要）
- Let's Encrypt: 90日ごとに手動更新（必要）

### Q4: 今すぐHTTPS対応したいです

**A**: CloudFlare Tunnelが最速です（30分程度）

### Q5: コストを最小限にしたいです

**A**: 
1. CloudFlare Tunnel（完全無料）
2. ローカルwrapper（完全無料、ただしHTTPSではない）

## まとめ

| 要件 | 推奨方法 |
|------|----------|
| **無料でHTTPS** | CloudFlare Tunnel |
| **本格運用** | ACM証明書 |
| **最速セットアップ** | ローカルwrapper |
| **AWS完結** | ACM証明書 |

---

**次のアクション:**

1. 上記の選択肢から1つ選ぶ
2. 対応するスクリプトを実行
3. Kiroを再起動
4. 動作確認

どの方法を選びますか？
