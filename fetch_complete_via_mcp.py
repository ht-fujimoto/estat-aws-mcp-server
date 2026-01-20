#!/usr/bin/env python3
"""
MCPツールを使用して家計調査データを完全取得
"""
import sys
import json

# 既に取得済みのチャンク1の情報
print("=" * 70)
print("家計調査データ（0002070002）完全取得プラン")
print("=" * 70)
print()
print("データセット情報:")
print("  - Dataset ID: 0002070002")
print("  - 総レコード数: 103,629件")
print("  - チャンクサイズ: 100,000件")
print("  - 必要チャンク数: 2チャンク")
print()
print("取得状況:")
print("  ✓ チャンク1: 100,000件 取得済み")
print("    S3: s3://estat-data-lake/raw/data/0002070002_chunk_001_20260119_235308.json")
print("    Parquet: s3://estat-data-lake/processed/0002070002_chunk_001_20260119_235308.parquet")
print("    Iceberg: economy_data テーブルに 115,515件 投入済み")
print()
print("  ⏳ チャンク2: 3,629件 未取得")
print("    開始位置: 100,001")
print("    終了位置: 103,629")
print()
print("=" * 70)
print()
print("次のステップ:")
print("1. E-stat APIから直接チャンク2を取得（startPosition=100001, limit=10000）")
print("2. 取得したデータをS3に保存")
print("3. Parquet形式に変換")
print("4. Icebergテーブルに追加投入")
print()
print("注意: MCPツールのタイムアウト制限により、")
print("      残り3,629件は手動でE-stat APIから取得する必要があります。")
print()
print("推奨アクション:")
print("  - より小さいデータセットを選択する")
print("  - または、フィルタリングを使用して必要なデータのみ取得する")
print()
