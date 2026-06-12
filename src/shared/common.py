"""common.py – shared initializations for custom MCP servers (Python port).

Provides:
- AgentResult type and helpers (agent_success, agent_error)
- safe_execute decorator for wrapping MCP tool functions
- retry_with_backoff for rate-limit resilience
- get_scoped_auth for Google ADC
- Google API service client factories
"""

from __future__ import annotations

import asyncio
import json
import logging
import functools
import sys
from typing import Any, Callable, Coroutine, Optional, TypedDict

import google.auth
from google.auth.credentials import Credentials
from googleapiclient.discovery import build, Resource

logger = logging.getLogger(__name__)


# ==========================================
# TYPES (AgentResult Standard)
# ==========================================


class AgentResult(TypedDict, total=False):
    """Structured result returned by every MCP tool."""

    success: bool
    message: str
    data: Any
    error_code: str


def agent_success(message: str, data: Any = None) -> AgentResult:
    """Create a successful AgentResult."""
    return AgentResult(success=True, message=message, data=data)


def agent_error(message: str, error_code: Optional[str] = None) -> AgentResult:
    """Create a failed AgentResult."""
    result = AgentResult(success=False, message=message, data=None)
    if error_code is not None:
        result["error_code"] = error_code
    return result


# ==========================================
# SAFE EXECUTE DECORATOR
# ==========================================


def safe_execute(tool_name: str) -> Callable:
    """Decorator that wraps an async MCP tool function with error handling.

    Catches all exceptions and returns a JSON-serialized AgentResult string.
    This ensures tools never raise unhandled exceptions to the MCP transport.

    Usage::

        @safe_execute("my_tool")
        async def my_tool(param1: str) -> dict:
            ...
    """

    def decorator(
        fn: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Callable[..., Coroutine[Any, Any, str]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> str:
            try:
                result = await fn(*args, **kwargs)
                return json.dumps(
                    agent_success(f"{tool_name} completed successfully", result),
                    indent=2,
                    default=str,
                )
            except Exception as err:
                message = str(err)
                # Extract API error code if available
                error_code: str
                code = getattr(err, "status_code", None) or getattr(err, "code", None)
                if code is not None:
                    error_code = f"API_{code}"
                else:
                    error_code = "EXECUTION_ERROR"
                return json.dumps(
                    agent_error(f"{tool_name} failed: {message}", error_code),
                    indent=2,
                    default=str,
                )

        return wrapper

    return decorator


# ==========================================
# RESILIENCE & IDEMPOTENCY
# ==========================================


async def retry_with_backoff(
    fn: Callable[..., Coroutine[Any, Any, Any]],
    max_retries: int = 5,
    initial_delay: float = 1.0,
) -> Any:
    """Execute an async function with exponential backoff retries on rate-limit (429) errors.

    Args:
        fn: Async callable to execute.
        max_retries: Maximum number of attempts (default 5).
        initial_delay: Initial delay in seconds before first retry (default 1.0).

    Returns:
        The result of the successful function call.

    Raises:
        The last exception if all retries are exhausted or a non-rate-limit error occurs.
    """
    last_error: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            return await fn()
        except Exception as err:
            last_error = err
            message = str(err).lower()
            is_rate_limit = (
                "429" in str(err)
                or "too many requests" in message
                or "rate limit" in message
                or "exhausted" in message
            )

            if not is_rate_limit or attempt == max_retries - 1:
                raise

            delay = initial_delay * (2 ** attempt)
            logger.warning(
                "[BACKOFF] Rate limit hit. Retrying in %.1fs... (Attempt %d/%d)",
                delay,
                attempt + 1,
                max_retries,
            )
            await asyncio.sleep(delay)

    # Should not reach here, but satisfy type checker
    if last_error is not None:
        raise last_error


async def is_resource_exists(check_fn: Callable[..., Coroutine[Any, Any, bool]]) -> bool:
    """Standardizes the 'Check-Before-Create' idempotency pattern.

    Returns True if the resource exists, False on any error (safer for creation).
    """
    try:
        return await check_fn()
    except Exception:
        return False


# ==========================================
# SCOPED AUTH FACTORY (ADC — PoLP)
# ==========================================


def get_scoped_auth(scopes: list[str]) -> Credentials:
    """Get Google credentials scoped to the specified OAuth scopes using ADC.

    Uses Application Default Credentials (ADC). Works with both service accounts
    (GOOGLE_APPLICATION_CREDENTIALS env var) and user credentials (gcloud auth).

    Args:
        scopes: List of OAuth scope URLs.

    Returns:
        Scoped Google credentials.

    Raises:
        RuntimeError: If ADC is not configured.
    """
    try:
        credentials, _project = google.auth.default(scopes=scopes)
        return credentials
    except google.auth.exceptions.DefaultCredentialsError as err:
        raise RuntimeError(
            f"⚠️ ADC NOT CONFIGURED: {err}\n\n"
            "To fix this, run:\n"
            "  gcloud auth application-default login\n\n"
            "For service account auth, set GOOGLE_APPLICATION_CREDENTIALS:\n"
            '  export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"\n'
        ) from err


# ==========================================
# API CLIENT FACTORIES
# ==========================================


def create_drive_service(creds: Credentials) -> Resource:
    """Create a Google Drive API v3 service client."""
    return build("drive", "v3", credentials=creds)


def create_docs_service(creds: Credentials) -> Resource:
    """Create a Google Docs API v1 service client."""
    return build("docs", "v1", credentials=creds)


def create_slides_service(creds: Credentials) -> Resource:
    """Create a Google Slides API v1 service client."""
    return build("slides", "v1", credentials=creds)


def create_sheets_service(creds: Credentials) -> Resource:
    """Create a Google Sheets API v4 service client."""
    return build("sheets", "v4", credentials=creds)
