"""gws_runner.py – GWS CLI runner and API fast-path handlers.

Ported from the bottom of gws_bridge.ts. Provides:
- run_gws_command() for executing the GWS CLI binary via asyncio subprocess
- handle_drive_export() for Drive export via API (avoids CLI disk-write issues)
- handle_docs_get() for Docs retrieval via API (efficient text extraction)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, TypedDict

from .common import (
    get_scoped_auth,
    create_docs_service,
    create_drive_service,
    retry_with_backoff,
)
from .gws_helpers import split_args

logger = logging.getLogger(__name__)


# ==========================================
# CONSTANTS
# ==========================================

GWS_BINARY: str = os.environ.get("GWS_BINARY_PATH", "gws")
GWS_TIMEOUT_SECONDS: int = 30


# ==========================================
# TYPES
# ==========================================


class GwsCommandResult(TypedDict):
    """Structured result from a GWS CLI invocation."""

    stdout: str
    stderr: str
    parsed: Any


# ==========================================
# CLI RUNNER
# ==========================================


async def run_gws_command(command: str) -> GwsCommandResult:
    """Run the GWS CLI binary and return structured results.

    Parses the command string into arguments (respecting quotes), executes the
    binary via ``asyncio.create_subprocess_exec``, and attempts to JSON-parse
    the stdout.

    Note: gws outputs JSON natively — we do NOT append ``--format json``
    (not all subcommands support it, causing silent failures).

    Args:
        command: The full GWS command string (without the binary name prefix
                 if the binary is ``gws``).

    Returns:
        GwsCommandResult with stdout, stderr, and parsed (JSON or raw string).

    Raises:
        RuntimeError: If the GWS binary is not found.
        Exception: If gws returns only stderr with no stdout.
    """

    async def _execute() -> GwsCommandResult:
        args = split_args(command)

        try:
            proc = await asyncio.create_subprocess_exec(
                GWS_BINARY,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ},
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=GWS_TIMEOUT_SECONDS,
            )
            stdout = (stdout_bytes or b"").decode("utf-8").strip()
            stderr = (stderr_bytes or b"").decode("utf-8").strip()

        except FileNotFoundError:
            raise RuntimeError(
                f"GWS_NOT_FOUND: The `gws` CLI is not installed at {GWS_BINARY}. "
                "Run: npm install @googleworkspace/cli"
            )
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"GWS_TIMEOUT: Command timed out after {GWS_TIMEOUT_SECONDS}s: {command}"
            )
        except Exception as err:
            stdout = ""
            stderr = str(err)

            if "ENOENT" in stderr or "not found" in stderr:
                raise RuntimeError(
                    f"GWS_NOT_FOUND: The `gws` CLI is not installed at {GWS_BINARY}. "
                    "Run: npm install @googleworkspace/cli"
                )

        # Attempt JSON parse of stdout
        parsed: Any = stdout
        if stdout.startswith("{") or stdout.startswith("["):
            try:
                parsed = json.loads(stdout)
            except json.JSONDecodeError:
                parsed = stdout

        # If only stderr and no stdout, treat as error
        if stderr and not stdout:
            raise RuntimeError(f"gws error: {stderr}")

        return GwsCommandResult(stdout=stdout, stderr=stderr, parsed=parsed)

    return await retry_with_backoff(_execute)


# ==========================================
# API FAST-PATH HANDLERS
# ==========================================

# Regex to extract --params JSON from command strings
_PARAMS_REGEX = re.compile(r"""--params\s+['"]?(\{[^}]+\})['"]?""")


def _extract_params(command: str, operation: str) -> dict[str, Any]:
    """Extract the --params JSON object from a GWS command string.

    Args:
        command: The full command string.
        operation: Human-readable operation name for error messages.

    Returns:
        Parsed parameters dict.

    Raises:
        ValueError: If --params is missing or contains invalid JSON.
    """
    match = _PARAMS_REGEX.search(command)
    if not match:
        raise ValueError(f"{operation} requires --params with required fields")

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as err:
        raise ValueError(f"Invalid JSON in --params for {operation}: {err}") from err


async def handle_drive_export(command: str) -> GwsCommandResult:
    """Handle ``drive files export`` via Drive API instead of CLI.

    The CLI tries to write the exported file to disk, which fails in read-only
    environments. This function streams the content in-memory and returns it
    directly.

    Args:
        command: The full GWS command string containing --params with
                 ``fileId`` and ``mimeType``.

    Returns:
        GwsCommandResult with the exported content in stdout/parsed.

    Raises:
        ValueError: If required parameters are missing.
    """
    params = _extract_params(command, "drive export")

    file_id = params.get("fileId")
    mime_type = params.get("mimeType")

    if not file_id or not mime_type:
        raise ValueError("drive export --params must include 'fileId' and 'mimeType'")

    logger.info("[API] Drive export: %s → %s", file_id, mime_type)

    creds = get_scoped_auth(["https://www.googleapis.com/auth/drive.readonly"])
    drive = create_drive_service(creds)

    async def _export() -> Any:
        # google-api-python-client is synchronous, run in executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: drive.files().export(fileId=file_id, mimeType=mime_type).execute(),
        )

    response = await retry_with_backoff(_export)

    content = response if isinstance(response, str) else json.dumps(response)
    logger.info("[API] Export complete: %.1f KB", len(content) / 1024)

    return GwsCommandResult(
        stdout=content,
        stderr="",
        parsed=content,
    )


async def handle_docs_get(command: str) -> GwsCommandResult:
    """Handle ``docs documents get`` via Docs API instead of CLI.

    The CLI returns the full document structure (2MB+) with all styling metadata.
    This function extracts text content efficiently using field filtering.

    Args:
        command: The full GWS command string containing --params with
                 ``documentId`` and optionally ``fields``.

    Returns:
        GwsCommandResult with extracted text content.

    Raises:
        ValueError: If required parameters are missing.
    """
    params = _extract_params(command, "docs documents get")

    document_id = params.get("documentId")
    if not document_id:
        raise ValueError("docs documents get --params must include 'documentId'")

    logger.info("[API] Docs get: %s", document_id)

    creds = get_scoped_auth(["https://www.googleapis.com/auth/documents.readonly"])
    docs = create_docs_service(creds)

    # Use field filtering if provided, otherwise default to text-only fields
    fields = params.get(
        "fields",
        "title,body.content.paragraph.elements.textRun.content,"
        "body.content.table.tableRows.tableCells.content.paragraph.elements.textRun.content",
    )

    async def _get() -> dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: docs.documents().get(documentId=document_id, fields=fields).execute(),
        )

    doc = await retry_with_backoff(_get)

    # Extract text content for easy consumption
    text_content = _extract_doc_text(doc)

    result = {
        "title": doc.get("title", ""),
        "textContent": text_content,
        "characterCount": len(text_content),
    }

    logger.info(
        '[API] Docs get complete: "%s" (%d chars)',
        doc.get("title", ""),
        len(text_content),
    )

    return GwsCommandResult(
        stdout=json.dumps(result),
        stderr="",
        parsed=result,
    )


def _extract_doc_text(doc: dict[str, Any]) -> str:
    """Extract plain text from a Google Docs API document response.

    Handles both paragraph elements and table rows, formatting tables
    as pipe-delimited markdown.

    Args:
        doc: The Google Docs API document response dict.

    Returns:
        Extracted text content as a string.
    """
    text_parts: list[str] = []
    body = doc.get("body", {})

    for element in body.get("content", []):
        if "paragraph" in element:
            for pe in element["paragraph"].get("elements", []):
                text_run = pe.get("textRun")
                if text_run:
                    text_parts.append(text_run.get("content", ""))

        elif "table" in element:
            for row in element["table"].get("tableRows", []):
                cells: list[str] = []
                for cell in row.get("tableCells", []):
                    cell_text = ""
                    for ce in cell.get("content", []):
                        if "paragraph" in ce:
                            for pe in ce["paragraph"].get("elements", []):
                                text_run = pe.get("textRun")
                                if text_run:
                                    cell_text += (text_run.get("content", "")).strip()
                    cells.append(cell_text)
                text_parts.append("| " + " | ".join(cells) + " |\n")
            text_parts.append("\n")

    return "".join(text_parts)
