"""Shared utilities for vopak-workspace-mcp servers.

Re-exports all public symbols from common, gws_helpers, and gws_runner
for convenient ``from src.shared import ...`` imports.
"""

from .common import (
    AgentResult,
    agent_error,
    agent_success,
    create_docs_service,
    create_drive_service,
    create_sheets_service,
    create_slides_service,
    get_scoped_auth,
    is_resource_exists,
    retry_with_backoff,
    safe_execute,
)
from .gws_helpers import (
    DESTRUCTIVE_VERBS,
    READ_ONLY_VERBS,
    WRITE_VERBS,
    CellMismatch,
    CellValue,
    VerifyResult,
    build_drive_query,
    compare_sheet_values,
    escape_html,
    extract_verb,
    split_args,
)
from .gws_runner import (
    GWS_BINARY,
    GwsCommandResult,
    handle_docs_get,
    handle_drive_export,
    run_gws_command,
)

__all__ = [
    # common.py
    "AgentResult",
    "agent_success",
    "agent_error",
    "safe_execute",
    "retry_with_backoff",
    "is_resource_exists",
    "get_scoped_auth",
    "create_drive_service",
    "create_docs_service",
    "create_slides_service",
    "create_sheets_service",
    # gws_helpers.py
    "CellValue",
    "CellMismatch",
    "VerifyResult",
    "READ_ONLY_VERBS",
    "WRITE_VERBS",
    "DESTRUCTIVE_VERBS",
    "extract_verb",
    "build_drive_query",
    "compare_sheet_values",
    "escape_html",
    "split_args",
    # gws_runner.py
    "GWS_BINARY",
    "GwsCommandResult",
    "run_gws_command",
    "handle_drive_export",
    "handle_docs_get",
]
