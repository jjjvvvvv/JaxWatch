#!/usr/bin/env python3
"""
Retry utilities and enhanced error handling for JaxWatch
"""

import time
import logging
import functools
from typing import Callable, Any, Union, Tuple, List, Type
from enum import Enum
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError, HTTPError

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Different retry strategies"""
    EXPONENTIAL_BACKOFF = "exponential"
    LINEAR_BACKOFF = "linear"
    FIXED_DELAY = "fixed"


class RetryableException(Exception):
    """Custom exception for retryable operations"""
    pass


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        RequestException,
        ConnectionError,
        Timeout,
        RetryableException
    ),
    non_retryable_exceptions: Tuple[Type[Exception], ...] = (
        HTTPError,  # 4xx client errors shouldn't be retried
    )
):
    """
    Decorator for retrying functions with configurable backoff strategies

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        backoff_factor: Multiplier for exponential backoff
        strategy: Retry strategy to use
        retryable_exceptions: Exceptions that should trigger retries
        non_retryable_exceptions: Exceptions that should NOT be retried
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(f"✅ {func.__name__} succeeded on attempt {attempt + 1}")
                    return result

                except non_retryable_exceptions as e:
                    logger.error(f"❌ {func.__name__} failed with non-retryable error: {e}")
                    raise e

                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = calculate_delay(attempt, initial_delay, max_delay, backoff_factor, strategy)
                        logger.warning(
                            f"⚠️ {func.__name__} failed on attempt {attempt + 1}/{max_retries + 1}: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"❌ {func.__name__} failed after {max_retries + 1} attempts: {e}")

                except Exception as e:
                    logger.error(f"❌ {func.__name__} failed with unexpected error: {e}")
                    raise e

            # If we get here, all retries failed
            raise last_exception

        return wrapper
    return decorator


def calculate_delay(
    attempt: int,
    initial_delay: float,
    max_delay: float,
    backoff_factor: float,
    strategy: RetryStrategy
) -> float:
    """Calculate delay for the given attempt"""
    if strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
        delay = initial_delay * (backoff_factor ** attempt)
    elif strategy == RetryStrategy.LINEAR_BACKOFF:
        delay = initial_delay + (attempt * backoff_factor)
    else:  # FIXED_DELAY
        delay = initial_delay

    return min(delay, max_delay)


class HttpRetrySession:
    """HTTP session with built-in retry logic and circuit breaker"""

    def __init__(
        self,
        max_retries: int = 3,
        timeout: float = 30.0,
        user_agent: str = None
    ):
        self.max_retries = max_retries
        self.timeout = timeout
        self.user_agent = user_agent or 'Mozilla/5.0 (compatible; JaxWatch/1.0; +https://github.com/jjjvvvvv/JaxWatch)'
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})

        # Circuit breaker state
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0

    @retry_with_backoff(
        max_retries=3,
        retryable_exceptions=(ConnectionError, Timeout, requests.exceptions.RequestException),
        non_retryable_exceptions=(HTTPError,)
    )
    def get(self, url: str, **kwargs) -> requests.Response:
        """GET request with retry logic"""
        try:
            response = self.session.get(url, timeout=self.timeout, **kwargs)

            # Check for HTTP errors
            if response.status_code == 429:  # Rate limited
                logger.warning(f"Rate limited for {url}, treating as retryable")
                raise RetryableException(f"Rate limited: {response.status_code}")
            elif 500 <= response.status_code < 600:  # Server errors are retryable
                raise RetryableException(f"Server error: {response.status_code}")
            elif 400 <= response.status_code < 500:  # Client errors are not retryable
                raise HTTPError(f"Client error: {response.status_code}")

            response.raise_for_status()
            self._record_success()
            return response

        except Exception as e:
            self._record_failure()
            raise

    def _record_success(self):
        """Record successful request"""
        self.success_count += 1
        if self.success_count >= 5:  # Reset failure count after consecutive successes
            self.failure_count = 0

    def _record_failure(self):
        """Record failed request"""
        self.failure_count += 1
        self.last_failure_time = time.time()

    @property
    def health_status(self) -> dict:
        """Get health status of the session"""
        return {
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'last_failure_time': self.last_failure_time,
            'is_healthy': self.failure_count < 10
        }


def safe_execute(func: Callable, *args, fallback_value=None, log_errors=True, **kwargs) -> Any:
    """
    Safely execute a function with fallback

    Args:
        func: Function to execute
        *args: Arguments for function
        fallback_value: Value to return if function fails
        log_errors: Whether to log errors
        **kwargs: Keyword arguments for function

    Returns:
        Function result or fallback_value
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            logger.error(f"Safe execution failed for {func.__name__}: {e}")
        return fallback_value


def validate_url(url: str) -> bool:
    """Validate if URL is properly formatted"""
    if not url or not isinstance(url, str):
        return False
    return url.startswith(('http://', 'https://'))


def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks for batch processing"""
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


class ErrorContext:
    """Context manager for enhanced error reporting"""

    def __init__(self, operation: str, source: str = None):
        self.operation = operation
        self.source = source
        self.start_time = time.time()

    def __enter__(self):
        logger.info(f"🔄 Starting {self.operation}" + (f" for {self.source}" if self.source else ""))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time

        if exc_type is None:
            logger.info(f"✅ Completed {self.operation} in {duration:.2f}s")
        else:
            logger.error(f"❌ Failed {self.operation} after {duration:.2f}s: {exc_val}")

            # Add context to exception
            if hasattr(exc_val, 'add_note'):  # Python 3.11+
                exc_val.add_note(f"Operation: {self.operation}, Duration: {duration:.2f}s")

        return False  # Don't suppress exceptions


# Common retry configurations
WEB_SCRAPING_RETRY = retry_with_backoff(
    max_retries=3,
    initial_delay=2.0,
    retryable_exceptions=(ConnectionError, Timeout, RetryableException),
    non_retryable_exceptions=(HTTPError,)
)

API_CALL_RETRY = retry_with_backoff(
    max_retries=2,
    initial_delay=1.0,
    max_delay=10.0,
    retryable_exceptions=(ConnectionError, Timeout, RetryableException)
)

GEOCODING_RETRY = retry_with_backoff(
    max_retries=2,
    initial_delay=3.0,  # Longer delay for rate-limited APIs
    retryable_exceptions=(ConnectionError, Timeout, RetryableException)
)