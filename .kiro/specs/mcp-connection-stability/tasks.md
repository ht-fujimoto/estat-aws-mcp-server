# Implementation Plan: MCP Connection Stability (Streamable-HTTP)

## Overview

既存のstreamable-http MCPサーバーを修正し、Kiroとの安定した接続を確立します。SSE接続の適切な初期化とJSON-RPC処理の改善に焦点を当てます。

## Tasks

- [x] 1. 現在のサーバー問題の分析と修正
  - 既存のserver_mcp_streamable.pyの問題点を特定
  - SSE接続ハングの根本原因を解決
  - _Requirements: 2.1, 2.2_

- [x] 1.1 SSE接続初期化の修正
  - 接続確立時の即座の初期化メッセージ送信
  - 適切なSSEヘッダーとフォーマットの実装
  - _Requirements: 2.1, 2.2_

- [ ]* 1.2 SSE接続のプロパティテスト
  - **Property 5: SSE Connection Establishment**
  - **Validates: Requirements 2.1, 2.2**

- [ ] 2. HTTP リクエストハンドリングの改善
  - GET（SSE）とPOST（JSON-RPC）の明確な分離
  - エラーハンドリングの強化
  - _Requirements: 2.3, 2.4_

- [ ] 2.1 リクエストルーティングの実装
  - Accept ヘッダーに基づく適切なレスポンス選択
  - Content-Type の検証と処理
  - _Requirements: 2.4_

- [ ] 2.2 JSON-RPC処理の改善
  - 厳密なJSON-RPC 2.0仕様準拠
  - エラーレスポンスの標準化
  - _Requirements: 2.3, 6.1_

- [ ]* 2.3 デュアルプロトコルのプロパティテスト
  - **Property 7: Dual Protocol Handling**
  - **Validates: Requirements 2.4**

- [ ] 3. 接続状態管理の実装
  - アクティブ接続の追跡
  - 適切なリソースクリーンアップ
  - _Requirements: 2.5_

- [ ] 3.1 接続ライフサイクル管理
  - 接続の登録と登録解除
  - タイムアウトとキープアライブ
  - _Requirements: 2.5_

- [ ] 3.2 リソースクリーンアップの実装
  - 接続終了時の適切なリソース解放
  - メモリリークの防止
  - _Requirements: 2.5_

- [ ]* 3.3 リソースクリーンアップのプロパティテスト
  - **Property 8: Resource Cleanup**
  - **Validates: Requirements 2.5**

- [ ] 4. エラーハンドリングとロギングの強化
  - 包括的な例外処理
  - 構造化ログ出力
  - _Requirements: 1.2, 4.1, 4.2_

- [ ] 4.1 エラー分類と処理
  - HTTP エラーとJSON-RPC エラーの適切な分離
  - クライアントフレンドリーなエラーメッセージ
  - _Requirements: 1.2, 4.2_

- [ ] 4.2 ログシステムの改善
  - リクエスト追跡とパフォーマンス監視
  - デバッグ情報の充実
  - _Requirements: 1.4, 4.1, 4.3_

- [ ]* 4.3 エラーハンドリングのプロパティテスト
  - **Property 2: Error Message Clarity**
  - **Validates: Requirements 1.2, 4.2**

- [ ] 5. MCP プロトコル準拠の確保
  - 全必須メソッドの実装確認
  - スキーマ定義の改善
  - _Requirements: 6.2, 6.4, 6.5_

- [ ] 5.1 MCP メソッドの検証
  - initialize、tools/list、tools/call の動作確認
  - 通知メッセージの適切な処理
  - _Requirements: 6.4, 6.5_

- [ ] 5.2 ツールスキーマの改善
  - 正確なinputSchema定義
  - パラメータ検証の強化
  - _Requirements: 6.2, 6.3_

- [ ]* 5.3 MCP準拠のプロパティテスト
  - **Property 18: MCP Method Support**
  - **Validates: Requirements 6.4**

- [ ] 6. デプロイメントと統合テスト
  - 修正版サーバーのECSデプロイ
  - Kiroとの接続テスト
  - _Requirements: 1.1_

- [ ] 6.1 Docker イメージの更新
  - 修正されたサーバーコードでイメージ再構築
  - ECS Fargate への新バージョンデプロイ
  - _Requirements: 5.4_

- [ ] 6.2 Kiro 接続テスト
  - MCP設定の更新（disabled: false）
  - 実際の接続安定性確認
  - _Requirements: 1.1_

- [ ]* 6.3 接続安定性のプロパティテスト
  - **Property 1: Connection Stability**
  - **Validates: Requirements 1.1**

- [ ] 7. 最終検証とドキュメント化
  - 全機能の動作確認
  - 問題解決の記録
  - _Requirements: 1.1, 4.1_

- [ ] 7.1 包括的機能テスト
  - 全てのe-Stat AWSツールの動作確認
  - 長時間接続の安定性テスト
  - _Requirements: 1.1, 7.1_

- [ ] 7.2 パフォーマンステスト
  - レスポンス時間の測定
  - 同時接続処理の確認
  - _Requirements: 7.1, 7.3_

- [ ] 7.3 ドキュメント更新
  - 修正内容の詳細記録
  - 運用ガイドの更新
  - _Requirements: 4.1_

## Notes

- タスクに`*`が付いているものはオプションで、コア機能の修正を優先
- 既存のECS Fargateインフラを活用し、サーバーコードのみ修正
- 各修正後にKiroでの接続テストを実施
- 問題が解決しない場合は段階的にロールバック可能な構成を維持