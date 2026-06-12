"""gcp_cli.py — GCP CLI wrapper tools (read / write / destructive).

Three verb-gated wrapper tools for gcloud, bq, and gsutil commands.
Each tool classifies the verb in the command and gates execution based on
the verb's permission level. This enforces the HITL safety protocol at the
tool boundary.
"""

from __future__ import annotations

from fastmcp import FastMCP

from src.shared.common import safe_execute
from src.shared.gcp_helpers import (
    READ_VERBS,
    WRITE_VERBS,
    DESTRUCTIVE_VERBS,
    extract_gcp_verb,
    sanitize_command,
    ensure_json_format,
)
from src.shared.gcp_runner import run_gcp_command


def register_tools(mcp: FastMCP) -> None:
    """Register the 3 GCP CLI wrapper tools on the given FastMCP server."""

    # ------------------------------------------------------------------
    # Tool 1: gcp_read — Read-only operations
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("gcp_read")
    async def gcp_read(command: str) -> dict:
        """Read-only GCP CLI tool. Runs gcloud, bq, or gsutil read commands.
        Supports list, describe, get, show, ls, cat.
        Output is always JSON.
        Example: "run services list --project=my-project", "bq ls", "storage buckets list".
        NEVER used for create, delete, deploy, etc."""
        verb = extract_gcp_verb(command)

        if verb in WRITE_VERBS:
            raise ValueError(
                f"POLICY GATE: '{verb}' is a write operation. "
                "Use gcp_write for create/update/deploy commands."
            )

        if verb in DESTRUCTIVE_VERBS:
            raise ValueError(
                f"HITL SAFETY GATE: '{verb}' is a destructive operation. "
                "Use gcp_destructive for delete/remove/destroy commands."
            )

        command = sanitize_command(command)
        command = ensure_json_format(command)
        return await run_gcp_command(command)

    # ------------------------------------------------------------------
    # Tool 2: gcp_write — Write operations (requires reason for audit)
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("gcp_write")
    async def gcp_write(command: str, reason: str) -> dict:
        """Write-capable GCP CLI tool. Runs gcloud, bq, or gsutil create/update commands.
        Requires a reason for audit trail.
        Supports create, deploy, update, grant, enable, cp, mv.
        Example: "iam service-accounts create my-sa --display-name=My SA"."""
        if len(reason) < 10:
            raise ValueError(
                "AUDIT GATE: 'reason' must be at least 10 characters for audit trail."
            )

        verb = extract_gcp_verb(command)

        if verb in READ_VERBS:
            raise ValueError(
                f"POLICY GATE: '{verb}' is read-only. "
                "Use gcp_read to avoid unnecessary human confirmation."
            )

        if verb in DESTRUCTIVE_VERBS:
            raise ValueError(
                f"HITL SAFETY GATE: '{verb}' is a destructive operation. "
                "Use gcp_destructive for delete/remove/destroy commands."
            )

        command = sanitize_command(command)
        command = ensure_json_format(command)
        result = await run_gcp_command(command)
        return {**result, "reason": reason}

    # ------------------------------------------------------------------
    # Tool 3: gcp_destructive — Destructive operations (strict HITL)
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("gcp_destructive")
    async def gcp_destructive(command: str, reason: str) -> dict:
        """⚠️ DESTRUCTIVE -- Delete-capable GCP CLI tool.
        Runs gcloud, bq, or gsutil delete/remove commands.
        Use with EXTREME CAUTION. Requires explicit human confirmation.
        Supports delete, remove, destroy, rm, drop."""
        if len(reason) < 10:
            raise ValueError(
                "AUDIT GATE: 'reason' must be at least 10 characters for audit trail."
            )

        verb = extract_gcp_verb(command)

        if verb not in DESTRUCTIVE_VERBS:
            raise ValueError(
                f"POLICY GATE: '{verb}' is not a destructive verb. "
                "Use gcp_write or gcp_read instead."
            )

        command = sanitize_command(command)
        result = await run_gcp_command(command)
        return {"result": result, "reason": reason}
