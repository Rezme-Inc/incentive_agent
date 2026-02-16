"""
Retry Handler - Exponential backoff for API calls

Provides retry logic with exponential backoff for handling:
- Rate limits
- Temporary API failures
- Network issues
"""

import time
import random
from functools import wraps
from typing import Callable, Any, Type, Tuple, Optional


class RetryError(Exception):
    """Raised when all retries are exhausted"""
    def __init__(self, message: str, last_exception: Exception = None):
        super().__init__(message)
        self.last_exception = last_exception


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int, float], None]] = None
):
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exponential_base: Base for exponential increase
        jitter: Add random jitter to prevent thundering herd
        retryable_exceptions: Tuple of exceptions to retry on
        on_retry: Optional callback called before each retry
                  Receives (exception, attempt_number, delay)

    Usage:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def api_call():
            # Make API call that might fail
            pass
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

                    # Check if this is a non-retryable error
                    if not _is_retryable_error(e):
                        raise

                    # If we've exhausted retries, raise
                    if attempt >= max_retries:
                        raise RetryError(
                            f"Failed after {max_retries + 1} attempts: {str(e)}",
                            last_exception=e
                        )

                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )

                    # Add jitter (0-25% of delay)
                    if jitter:
                        delay = delay * (1 + random.uniform(0, 0.25))

                    # Call retry callback if provided
                    if on_retry:
                        on_retry(e, attempt + 1, delay)
                    else:
                        print(f"    Retry {attempt + 1}/{max_retries}: {str(e)[:50]}... (waiting {delay:.1f}s)")

                    time.sleep(delay)

            # Should never reach here, but just in case
            raise RetryError(
                f"Failed after {max_retries + 1} attempts",
                last_exception=last_exception
            )

        return wrapper
    return decorator


def _is_retryable_error(e: Exception) -> bool:
    """
    Check if an error is retryable.

    Retryable errors:
    - Rate limit errors (429)
    - Server errors (500, 502, 503, 504)
    - Connection errors
    - Timeout errors

    Non-retryable errors:
    - Authentication errors (401, 403)
    - Bad request (400)
    - Not found (404)
    """
    error_str = str(e).lower()

    # Check for rate limit indicators
    if "rate" in error_str and "limit" in error_str:
        return True
    if "429" in error_str:
        return True
    if "overloaded" in error_str:
        return True

    # Check for server errors
    if any(code in error_str for code in ["500", "502", "503", "504"]):
        return True

    # Check for connection errors
    if any(term in error_str for term in ["connection", "timeout", "timed out", "network"]):
        return True

    # Check for authentication errors (not retryable)
    if any(code in error_str for code in ["401", "403", "authentication", "unauthorized"]):
        return False

    # Check for bad request (not retryable)
    if "400" in error_str or "bad request" in error_str:
        return False

    # Default to retryable for unknown errors
    return True


def safe_api_call(
    func: Callable,
    *args,
    max_retries: int = 3,
    default_return: Any = None,
    **kwargs
) -> Any:
    """
    Make a safe API call with retry logic and default return.

    Args:
        func: Function to call
        *args: Positional arguments for func
        max_retries: Maximum retries
        default_return: Value to return if all retries fail
        **kwargs: Keyword arguments for func

    Returns:
        Result of func, or default_return if all retries fail

    Usage:
        result = safe_api_call(tavily_search, query="test", max_retries=3, default_return=[])
    """
    @retry_with_backoff(max_retries=max_retries)
    def wrapped_call():
        return func(*args, **kwargs)

    try:
        return wrapped_call()
    except RetryError as e:
        print(f"    Warning: API call failed after {max_retries + 1} attempts: {str(e.last_exception)[:100]}")
        return default_return
    except Exception as e:
        print(f"    Warning: API call failed: {str(e)[:100]}")
        return default_return
