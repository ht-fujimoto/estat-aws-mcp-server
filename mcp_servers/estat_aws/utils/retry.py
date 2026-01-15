"""
リトライロジックユーティリティ
"""

import time
import logging
from typing import Callable, Any, Type, Tuple
from functools import wraps

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    指数バックオフでリトライするデコレータ
    
    Args:
        max_retries: 最大リトライ回数
        base_delay: 基本遅延時間（秒）
        max_delay: 最大遅延時間（秒）
        exponential_base: 指数の基数
        retryable_exceptions: リトライ可能な例外のタプル
    
    Returns:
        デコレータ関数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}",
                            extra={"error": str(e)}
                        )
                        raise
                    
                    # 遅延時間を計算
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} after {delay:.1f}s",
                        extra={"error": str(e)}
                    )
                    
                    time.sleep(delay)
            
            # 最後の例外を再送出
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


def is_retryable_error(error: Exception) -> bool:
    """
    エラーがリトライ可能かどうかを判定
    
    Args:
        error: エラー
    
    Returns:
        リトライ可能な場合True
    """
    error_message = str(error).lower()
    
    # リトライ可能なエラーパターン
    retryable_patterns = [
        'timeout',
        'connection',
        'network',
        'temporary',
        'rate limit',
        'throttl',
        'service unavailable',
        '503',
        '504',
        '429'
    ]
    
    return any(pattern in error_message for pattern in retryable_patterns)


class RetryableError(Exception):
    """リトライ可能なエラー"""
    pass
