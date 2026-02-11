"""
Supabase utilities for KOFA.

Standalone retry logic, exception hierarchy, and client factory.
No external dependencies beyond supabase-py.
"""

from __future__ import annotations

import functools
import logging
import os
import random
import time
from collections.abc import Callable
from functools import lru_cache
from typing import Any, ParamSpec, TypeVar

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


# =============================================================================
# Supabase response type helpers
# =============================================================================


def _rows(data: Any) -> list[dict[str, Any]]:
    """Type-narrow Supabase .data (JSON union) to list[dict]."""
    return data or []


def _row(data: Any) -> dict[str, Any] | None:
    """Type-narrow first element of Supabase .data to dict | None."""
    return data[0] if data else None


# =============================================================================
# Configuration (via env vars, no external config dependency)
# =============================================================================

RETRY_MAX_ATTEMPTS = int(os.getenv("KOFA_RETRY_MAX_ATTEMPTS", "3"))
RETRY_BACKOFF_BASE = float(os.getenv("KOFA_RETRY_BACKOFF_BASE", "0.5"))
RETRY_BACKOFF_MAX = float(os.getenv("KOFA_RETRY_BACKOFF_MAX", "30.0"))
RETRY_JITTER = os.getenv("KOFA_RETRY_JITTER", "true").lower() == "true"


# =============================================================================
# Exception Hierarchy
# =============================================================================


class SupabaseError(Exception):
    """Base exception for Supabase operations."""

    def __init__(self, message: str, original: Exception | None = None):
        super().__init__(message)
        self.original = original


class TransientError(SupabaseError):
    """Retry-able error - network issues, timeouts, 5xx."""

    pass


class PermanentError(SupabaseError):
    """Non-retryable error - auth, validation, 4xx."""

    def __init__(
        self,
        message: str,
        original: Exception | None = None,
        code: str | None = None,
        details: str | None = None,
    ):
        super().__init__(message, original)
        self.code = code
        self.details = details


class RateLimitError(TransientError):
    """429 - Rate limit exceeded."""

    def __init__(
        self,
        message: str,
        retry_after: int | None = None,
        original: Exception | None = None,
    ):
        super().__init__(message, original)
        self.retry_after = retry_after


def classify_error(e: Exception) -> SupabaseError:
    """Classify an exception as TransientError or PermanentError."""
    import httpx

    if isinstance(e, (httpx.TimeoutException, httpx.ConnectError, ConnectionError)):
        return TransientError(f"Network error: {e}", original=e)

    try:
        from postgrest import APIError

        if isinstance(e, APIError):
            code = getattr(e, "code", None) or ""
            message = getattr(e, "message", str(e))
            if code.startswith("PGRST3") or "JWT" in message.upper():
                return PermanentError(message, original=e, code=code)
            if code == "23505" or "unique" in message.lower():
                return PermanentError(message, original=e, code=code)
            if code.startswith("5") or code.startswith("PGRST5"):
                return TransientError(message, original=e)
            return PermanentError(message, original=e, code=code)
    except ImportError:
        pass

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 429:
            retry_after = e.response.headers.get("Retry-After")
            return RateLimitError(
                "Rate limit exceeded",
                retry_after=int(retry_after) if retry_after else None,
                original=e,
            )
        if status in (500, 502, 503, 504):
            return TransientError(f"Server error: {status}", original=e)
        return PermanentError(f"HTTP {status}", original=e)

    return TransientError(f"Unknown error: {e}", original=e)


# =============================================================================
# Retry Decorator
# =============================================================================


def with_retry(
    max_attempts: int | None = None,
    backoff_base: float | None = None,
    backoff_max: float | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator for retry with exponential backoff."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            _max = max_attempts or RETRY_MAX_ATTEMPTS
            _base = backoff_base or RETRY_BACKOFF_BASE
            _max_backoff = backoff_max or RETRY_BACKOFF_MAX

            last_exception: Exception | None = None

            for attempt in range(_max):
                try:
                    return func(*args, **kwargs)
                except (TransientError, RateLimitError) as e:
                    last_exception = e
                    if attempt == _max - 1:
                        raise
                    if isinstance(e, RateLimitError) and e.retry_after:
                        backoff = min(e.retry_after, _max_backoff)
                    else:
                        backoff = min(_base * (2**attempt), _max_backoff)
                    if RETRY_JITTER:
                        backoff = max(0, backoff + backoff * 0.25 * (2 * random.random() - 1))
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{_max} failed: {e}. "
                        f"Retrying in {backoff:.2f}s..."
                    )
                    time.sleep(backoff)
                except PermanentError:
                    raise
                except Exception as e:
                    if isinstance(e, SupabaseError):
                        classified = e
                    else:
                        classified = classify_error(e)
                    if isinstance(classified, TransientError):
                        last_exception = classified
                        if attempt == _max - 1:
                            raise classified from e
                        backoff = min(_base * (2**attempt), _max_backoff)
                        if RETRY_JITTER:
                            backoff = max(0, backoff + backoff * 0.25 * (2 * random.random() - 1))
                        time.sleep(backoff)
                    else:
                        raise classified from e

            if last_exception:
                raise last_exception
            raise RuntimeError(f"{func.__name__} failed unexpectedly")

        return wrapper

    return decorator


def safe_execute(
    operation: Callable[[], R],
    error_message: str = "Operation failed",
    default: R | None = None,
) -> R | None:
    """Execute operation with error handling, returning default on failure."""
    try:
        return operation()
    except (PermanentError, TransientError) as e:
        logger.error(f"{error_message}: {e}")
        return default
    except Exception as e:
        logger.error(f"{error_message}: {e}")
        return default


# =============================================================================
# Client Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_shared_client():
    """Get shared Supabase client (singleton)."""
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY/SUPABASE_SECRET_KEY must be set")

    return create_client(url, key)
