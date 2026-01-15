"""
ロギング設定ユーティリティ
"""

import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict


def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    ロガーをセットアップ
    
    Args:
        name: ロガー名
        level: ログレベル
    
    Returns:
        設定されたロガー
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # ハンドラーが既に存在する場合は追加しない
    if logger.handlers:
        return logger
    
    # コンソールハンドラー
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))
    
    # フォーマッター（構造化ログ）
    formatter = StructuredFormatter()
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    
    return logger


class StructuredFormatter(logging.Formatter):
    """構造化ログフォーマッター"""
    
    def format(self, record: logging.LogRecord) -> str:
        """
        ログレコードをJSON形式にフォーマット
        
        Args:
            record: ログレコード
        
        Returns:
            JSON形式のログ
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # 追加のフィールドを含める
        if hasattr(record, 'extra'):
            log_data.update(record.extra)
        
        # エラー情報を含める
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


def log_tool_call(logger: logging.Logger, tool_name: str, arguments: Dict[str, Any]):
    """
    ツール呼び出しをログに記録
    
    Args:
        logger: ロガー
        tool_name: ツール名
        arguments: 引数
    """
    logger.info(
        f"Tool called: {tool_name}",
        extra={
            "tool": tool_name,
            "arguments": _sanitize_for_log(arguments)
        }
    )


def log_tool_result(logger: logging.Logger, tool_name: str, success: bool, execution_time: float):
    """
    ツール実行結果をログに記録
    
    Args:
        logger: ロガー
        tool_name: ツール名
        success: 成功したかどうか
        execution_time: 実行時間（秒）
    """
    logger.info(
        f"Tool completed: {tool_name}",
        extra={
            "tool": tool_name,
            "success": success,
            "execution_time": execution_time
        }
    )


def _sanitize_for_log(data: Any) -> Any:
    """
    ログ用にデータをサニタイズ（機密情報を除去）
    
    Args:
        data: データ
    
    Returns:
        サニタイズされたデータ
    """
    if isinstance(data, dict):
        sanitized = {}
        sensitive_keys = ['api_key', 'app_id', 'access_key', 'secret_key', 'password', 'token']
        
        for key, value in data.items():
            if key.lower() in sensitive_keys:
                sanitized[key] = '[REDACTED]'
            else:
                sanitized[key] = _sanitize_for_log(value)
        
        return sanitized
    elif isinstance(data, list):
        return [_sanitize_for_log(item) for item in data]
    else:
        return data
