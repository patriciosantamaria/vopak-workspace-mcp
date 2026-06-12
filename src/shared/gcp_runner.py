"""gcp_runner.py – Async subprocess executor for GCP CLI commands.

Provides:
- run_gcp_command() for executing gcloud, bq, or gsutil via asyncio subprocess
- Auto-detects the binary from the first token of the command
- JSON-parses stdout when possible, falls back to raw string
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


# ==========================================
# CONSTANTS
# ==========================================

GCLOUD_BINARY: str = "gcloud"
BQ_BINARY: str = "bq"
GSUTIL_BINARY: str = "gsutil"
GCP_TIMEOUT_S: int = 60

# Map of recognized first tokens to their binary
_BINARY_MAP: dict[str, str] = {
    "gcloud": GCLOUD_BINARY,
    "bq": BQ_BINARY,
    "gsutil": GSUTIL_BINARY,
}


# ==========================================
# TYPES
# ==========================================


class GcpCommandResult(TypedDict):
    """Structured result from a GCP CLI invocation."""

    stdout: str
    stderr: str
    parsed: Any


# ==========================================
# CLI RUNNER
# ==========================================


async def run_gcp_command(
    command: str,
    timeout: int = GCP_TIMEOUT_S,
) -> GcpCommandResult:
    """Run a GCP CLI command and return structured results.

    Auto-detects the binary (gcloud, bq, gsutil) from the first token of
    the command string. If the agent included the binary name, it is stripped
    and the correct binary is used. If the first token is not a recognized
    binary, it defaults to gcloud.

    Args:
        command: The GCP command string. May or may not include the binary
                 prefix (e.g. 'gcloud run services list' or
                 'run services list').
        timeout: Maximum seconds to wait for command completion.

    Returns:
        GcpCommandResult with stdout, stderr, and parsed (JSON or raw string).

    Raises:
        RuntimeError: If the binary is not found or the command times out.
    """
    tokens = shlex.split(command)
    if not tokens:
        raise ValueError("Empty command provided")

    # Detect and resolve binary from first token
    first = tokens[0].lower()
    if first in _BINARY_MAP:
        binary = _BINARY_MAP[first]
        args = tokens[1:]  # Strip binary prefix from args
    else:
        # Default to gcloud if no recognized binary prefix
        binary = GCLOUD_BINARY
        args = tokens

    logger.info(
        "[GCP] Executing: %s %s",
        binary,
        " ".join(args[:4]) + ("..." if len(args) > 4 else ""),
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ},
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
        stdout = (stdout_bytes or b"").decode("utf-8").strip()
        stderr = (stderr_bytes or b"").decode("utf-8").strip()

    except FileNotFoundError:
        raise RuntimeError(
            f"GCP_NOT_FOUND: The `{binary}` CLI is not installed or not in PATH. "
            "Install the Google Cloud SDK: https://cloud.google.com/sdk/docs/install"
        )
    except asyncio.TimeoutError:
        raise RuntimeError(
            f"GCP_TIMEOUT: Command timed out after {timeout}s: {binary} {' '.join(args)}"
        )

    # Attempt JSON parse of stdout
    parsed: Any = None
    if stdout and (stdout.startswith("{") or stdout.startswith("[")):
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = stdout
    elif stdout:
        parsed = stdout

    # If only stderr and no stdout, treat as error
    if stderr and not stdout:
        raise RuntimeError(f"GCP CLI error: {stderr}")

    logger.info("[GCP] Command completed (stdout: %d bytes)", len(stdout))

    return GcpCommandResult(stdout=stdout, stderr=stderr, parsed=parsed)
