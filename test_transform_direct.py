#!/usr/bin/env python3
"""
transform_data関数を直接テストするスクリプト
"""

import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 環境変数を設定
os.environ['AWS_REGION'] = 'ap-northeast-1'
os.environ['DATALAKE_S3_BUCKET'] = 'estat-iceberg-datalake'

# transform_data関数をインポート
from mcp_servers.estat_datalake.server import transform_data

# テストデータ
test_args = {
    "s3_input_path": "s3://estat-iceberg-datalake/raw/0003001380/0003001380_20260119_161123.json",
    "domain": "population",
    "dataset_id": "0003001380"
}

print("=" * 60)
print("transform_data関数のテスト")
print("=" * 60)
print(f"引数: {test_args}")
print()

try:
    result = transform_data(test_args)
    print("結果:")
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"エラー発生: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
