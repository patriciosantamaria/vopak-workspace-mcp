"""gws_helpers.py – GWS CLI verb classification, Drive query builder, Sheets comparison.

Ported from gws_helpers.ts. Provides:
- Verb sets for read/write/destructive classification
- extract_verb() for parsing GWS CLI commands
- build_drive_query() for constructing Drive API query strings
- compare_sheet_values() for cell-by-cell Sheets verification
- escape_html() for safe HTML embedding
- split_args() for quote-aware argument splitting
"""

from __future__ import annotations

import re
from typing import Any, Optional, TypedDict


# ==========================================
# TYPES
# ==========================================

CellValue = str | int | float | bool | None


class CellMismatch(TypedDict):
    """Single cell mismatch detail returned by compare_sheet_values."""

    row: int
    col: int
    cell: str
    expected: str
    actual: str


class VerifyResult(TypedDict):
    """Result of a cell-by-cell comparison between expected and actual Sheets data."""

    verified: bool
    total_cells: int
    matched_cells: int
    mismatches: list[CellMismatch]


# ==========================================
# VERB CLASSIFICATION SETS
# ==========================================

READ_ONLY_VERBS: set[str] = {
    "get", "list", "watch", "export", "download", "query",
    "triage", "schema", "auth",
    "+triage", "+agenda", "+standup-report", "+weekly-digest", "+meeting-prep",
    "+read",
}

WRITE_VERBS: set[str] = {
    "create", "insert", "update", "patch",
    "move", "copy", "rename", "share", "unshare", "send",
    "push", "+send", "+reply", "+reply-all", "+forward",
    "+append", "+write", "+upload", "+insert", "+push",
    "+email-to-task", "+file-announce",
}

DESTRUCTIVE_VERBS: set[str] = {
    "delete", "trash",
}

# Combined set for fast lookup
_ALL_VERBS = READ_ONLY_VERBS | WRITE_VERBS | DESTRUCTIVE_VERBS


# ==========================================
# VERB EXTRACTION
# ==========================================


def extract_verb(command: str) -> str:
    """Extract the primary 'verb' from a GWS CLI command string.

    Priority order:
    1. First token starting with '+' (plugin verb)
    2. First recognized verb from the known sets (skipping the binary name at index 0)
    3. Last non-flag token as fallback
    4. First token if nothing else matches

    Args:
        command: The full GWS CLI command string.

    Returns:
        The extracted verb in lowercase.
    """
    tokens = command.strip().split()
    if not tokens:
        return ""

    # 1. Check for plugin verbs (tokens starting with '+')
    for token in tokens:
        if token.startswith("+"):
            return token.lower()

    # 2. Look for recognized verbs (skip index 0 = binary name)
    for token in tokens[1:]:
        lower = token.lower()
        if lower in _ALL_VERBS:
            return lower

    # 3. Fallback: last non-flag token
    for token in reversed(tokens[1:]):
        if not token.startswith("--"):
            return token.lower()

    # 4. Ultimate fallback: first token
    return tokens[0].lower()


# ==========================================
# DRIVE QUERY BUILDER
# ==========================================


def build_drive_query(
    parent_id: Optional[str] = None,
    mime_type: Optional[str] = None,
    name_contains: Optional[str] = None,
    trashed: Optional[bool] = None,
) -> Optional[str]:
    """Build a Drive API ``q`` query string from structured filter parameters.

    Args:
        parent_id: Folder ID to scope the query to.
        mime_type: MIME type filter (exact match).
        name_contains: Substring filter for file names.
        trashed: Whether to filter by trashed status.

    Returns:
        A Drive API query string, or None if no filters are provided.
    """
    query_parts: list[str] = []

    if parent_id:
        query_parts.append(f"'{parent_id}' in parents")
    if mime_type:
        query_parts.append(f"mimeType = '{mime_type}'")
    if name_contains:
        escaped_name = name_contains.replace("'", "\\'")
        query_parts.append(f"name contains '{escaped_name}'")
    if trashed is not None:
        query_parts.append(f"trashed = {str(trashed).lower()}")

    return " and ".join(query_parts) if query_parts else None


# ==========================================
# SHEETS COMPARISON
# ==========================================


def compare_sheet_values(
    expected: list[list[CellValue]],
    actual: list[list[CellValue]],
) -> VerifyResult:
    """Compare two 2D arrays of cell values cell-by-cell.

    Args:
        expected: The expected values (2D array).
        actual: The actual values read back (2D array).

    Returns:
        A VerifyResult with match counts and per-cell mismatch details.
    """
    mismatches: list[CellMismatch] = []
    total_cells = 0

    for r, row in enumerate(expected):
        for c, cell_val in enumerate(row):
            total_cells += 1
            exp = str(cell_val) if cell_val is not None else ""
            # Safely get actual value
            act_row = actual[r] if r < len(actual) else []
            act_val = act_row[c] if c < len(act_row) else None
            act = str(act_val) if act_val is not None else ""

            if exp != act:
                col_letter = chr(65 + c)
                mismatches.append(
                    CellMismatch(
                        row=r + 1,
                        col=c + 1,
                        cell=f"{col_letter}{r + 1}",
                        expected=exp,
                        actual=act,
                    )
                )

    return VerifyResult(
        verified=len(mismatches) == 0,
        total_cells=total_cells,
        matched_cells=total_cells - len(mismatches),
        mismatches=mismatches,
    )


# ==========================================
# HTML ESCAPING
# ==========================================


def escape_html(text: str) -> str:
    """Escape HTML special characters for safe embedding in templates.

    Args:
        text: Raw text to escape.

    Returns:
        HTML-safe string with &, <, >, " escaped.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ==========================================
# ARGUMENT SPLITTING
# ==========================================

# Regex for splitting arguments respecting single and double quotes
_ARG_REGEX = re.compile(r"""("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[^\s]+)""")


def split_args(command: str) -> list[str]:
    """Split a command string into arguments, respecting quoted strings.

    Handles both single and double-quoted arguments, stripping the outer quotes.

    Args:
        command: The command string to split.

    Returns:
        List of parsed argument strings.
    """
    args: list[str] = []
    for match in _ARG_REGEX.finditer(command):
        arg = match.group(0)
        # Strip surrounding quotes
        if (arg.startswith("'") and arg.endswith("'")) or (
            arg.startswith('"') and arg.endswith('"')
        ):
            arg = arg[1:-1]
        args.append(arg)
    return args
