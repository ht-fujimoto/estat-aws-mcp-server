"""
レスポンス形式統一ユーティリティ
"""

from typing import Any, Dict, Optional
from datetime import datetime


def format_success_response(
    result: Any,
    execution_time: Optional[float] = None,
    **metadata
) -> Dict[str, Any]:
    """
    成功レスポンスをフォーマット
    
    Args:
        result: 結果データ
        execution_time: 実行時間（秒）
        **metadata: 追加のメタデータ
    
    Returns:
        フォーマットされたレスポンス
    """
    response = {
        "success": True,
        "result": result,
        "metadata": {
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    }
    
    if execution_time is not None:
        response["metadata"]["execution_time"] = round(execution_time, 3)
    
    # 追加のメタデータを含める
    response["metadata"].update(metadata)
    
    return response


def format_error_response(
    error_code: str,
    error_message: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    エラーレスポンスをフォーマット
    
    Args:
        error_code: エラーコード
        error_message: エラーメッセージ
        details: エラーの詳細
    
    Returns:
        フォーマットされたエラーレスポンス
    """
    response = {
        "success": False,
        "error": {
            "code": error_code,
            "message": error_message
        },
        "metadata": {
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    }
    
    if details:
        response["error"]["details"] = details
    
    return response


def format_dataset_info(dataset: Dict[str, Any], rank: Optional[int] = None, score: Optional[float] = None) -> Dict[str, Any]:
    """
    データセット情報をフォーマット
    
    Args:
        dataset: データセット情報
        rank: ランク
        score: スコア
    
    Returns:
        フォーマットされたデータセット情報
    """
    formatted = {
        "dataset_id": dataset.get('@id') or dataset.get('id'),
        "title": _extract_value(dataset.get('TITLE') or dataset.get('title')),
        "gov_org": _extract_value(dataset.get('GOV_ORG') or dataset.get('gov_org')),
        "survey_date": dataset.get('SURVEY_DATE') or dataset.get('survey_date'),
        "open_date": dataset.get('OPEN_DATE') or dataset.get('open_date')
    }
    
    if rank is not None:
        formatted["rank"] = rank
    
    if score is not None:
        formatted["score"] = round(score, 3)
    
    return formatted


def _extract_value(field: Any) -> str:
    """
    フィールドから値を抽出（辞書または文字列）
    
    Args:
        field: フィールド
    
    Returns:
        抽出された値
    """
    if isinstance(field, dict):
        return field.get('$', 'N/A')
    elif isinstance(field, str):
        return field
    else:
        return 'N/A'
