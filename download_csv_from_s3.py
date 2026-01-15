#!/usr/bin/env python3
"""
S3からCSVファイルを直接ダウンロードするスクリプト
MCPツールで署名付きURLを取得→ローカルにダウンロード
"""

import requests
import sys
from pathlib import Path


def download_csv_from_url(download_url: str, local_path: str) -> bool:
    """
    署名付きURLからCSVファイルをダウンロード
    
    Args:
        download_url: S3署名付きURL
        local_path: ローカル保存先パス
    
    Returns:
        成功したらTrue
    """
    try:
        print(f"📥 ダウンロード開始: {local_path}")
        
        # URLからダウンロード
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        
        # ファイルに保存
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # 検証
        file_size = Path(local_path).stat().st_size
        print(f"✅ ダウンロード完了: {file_size:,} bytes ({file_size / (1024*1024):.2f} MB)")
        
        # 行数カウント
        with open(local_path, 'r', encoding='utf-8') as f:
            line_count = sum(1 for _ in f)
        print(f"📊 行数: {line_count:,} 行")
        
        return True
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("使い方: python download_csv_from_s3.py <download_url> <local_path>")
        sys.exit(1)
    
    download_url = sys.argv[1]
    local_path = sys.argv[2]
    
    success = download_csv_from_url(download_url, local_path)
    sys.exit(0 if success else 1)
