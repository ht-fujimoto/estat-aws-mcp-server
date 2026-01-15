"""
エラーハンドリングユーティリティ
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class EStatError(Exception):
    """e-Stat API関連のエラー"""
    pass


class AWSError(Exception):
    """AWSサービス関連のエラー"""
    pass


class DataTransformError(Exception):
    """データ変換関連のエラー"""
    pass


def format_error_response(
    error: Exception,
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    hide_sensitive: bool = True
) -> Dict[str, Any]:
    """
    エラーレスポンスをフォーマット
    
    Args:
        error: 発生したエラー
        tool_name: ツール名
        arguments: ツールの引数（機密情報を除外）
        hide_sensitive: 機密情報を隠すか
    
    Returns:
        フォーマットされたエラーレスポンス
    """
    error_message = str(error)
    
    # 機密情報を除外
    if hide_sensitive:
        error_message = _remove_sensitive_info(error_message)
        if arguments:
            arguments = _sanitize_arguments(arguments)
    
    # エラーコードを決定
    error_code = _get_error_code(error)
    
    return {
        "success": False,
        "error": {
            "code": error_code,
            "message": error_message,
            "tool": tool_name,
            "arguments": arguments
        }
    }


def _remove_sensitive_info(message: str) -> str:
    """
    エラーメッセージから機密情報を除去
    
    Args:
        message: エラーメッセージ
    
    Returns:
        サニタイズされたメッセージ
    """
    # APIキーのパターンを除去
    import re
    
    # APIキー（32文字の英数字）
    message = re.sub(r'[a-f0-9]{32}', '[API_KEY_REDACTED]', message)
    
    # AWSアクセスキー
    message = re.sub(r'AKIA[0-9A-Z]{16}', '[AWS_ACCESS_KEY_REDACTED]', message)
    
    # AWSシークレットキー
    message = re.sub(r'[A-Za-z0-9/+=]{40}', '[AWS_SECRET_REDACTED]', message)
    
    return message


def _sanitize_arguments(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    引数から機密情報を除去
    
    Args:
        arguments: ツールの引数
    
    Returns:
        サニタイズされた引数
    """
    sanitized = arguments.copy()
    
    # 機密情報のキーをマスク
    sensitive_keys = ['api_key', 'app_id', 'access_key', 'secret_key', 'password', 'token']
    
    for key in sensitive_keys:
        if key in sanitized:
            sanitized[key] = '[REDACTED]'
    
    return sanitized


def _get_error_code(error: Exception) -> str:
    """
    エラーからエラーコードを取得
    
    Args:
        error: エラー
    
    Returns:
        エラーコード
    """
    if isinstance(error, EStatError):
        return "ESTAT_API_ERROR"
    elif isinstance(error, AWSError):
        return "AWS_SERVICE_ERROR"
    elif isinstance(error, DataTransformError):
        return "DATA_TRANSFORM_ERROR"
    elif isinstance(error, ValueError):
        return "INVALID_PARAMETER"
    elif isinstance(error, TimeoutError):
        return "TIMEOUT_ERROR"
    else:
        return "INTERNAL_ERROR"
