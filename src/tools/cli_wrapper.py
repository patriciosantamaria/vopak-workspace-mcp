"""cli_wrapper.py — GWS CLI wrapper tools (read / write / destructive).

Port of the 3 CLI wrapper tools from gws_bridge.ts (lines 150-263).
Each tool classifies the verb in the command and gates execution based on
the verb's permission level. This enforces the HITL safety protocol at the
tool boundary.

Legacy tools retained for backward compatibility — disabled in hybrid MCP config.
"""

from __future__ import annotations

import re

from fastmcp import FastMCP

from src.shared.common import safe_execute, is_resource_exists
from src.shared.gws_helpers import (
    READ_ONLY_VERBS,
    WRITE_VERBS,
    DESTRUCTIVE_VERBS,
    extract_verb,
)
from src.shared.gws_runner import (
    run_gws_command,
    handle_drive_export,
    handle_docs_get,
)


def register_tools(mcp: FastMCP) -> None:
    """Register the 3 GWS CLI wrapper tools on the given FastMCP server."""

    # ------------------------------------------------------------------
    # Tool 1: gws_read — Read-only operations
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("gws_read")
    async def gws_read(command: str) -> dict:
        """Read-only Google Workspace CLI tool. Supports 'list', 'get', 'query', '+agenda', '+triage'.
        Example: 'drive files list --params '{"pageSize": 5}'', 'gmail +triage'.
        NEVER used for +send, delete, update, etc."""
        verb = extract_verb(command)

        if verb in WRITE_VERBS or verb in DESTRUCTIVE_VERBS:
            raise ValueError(
                f"HITL SAFETY GATE: '{verb}' is a mutating/destructive operation. "
                "Use gws_write or gws_destructive for this."
            )

        # === API FAST-PATH: Route specific commands through Google APIs ===

        # 1. Drive export → Drive API (streams content in memory, no disk write)
        if verb == "export":
            return await handle_drive_export(command)

        # 2. Docs get → Docs API (supports field filtering for efficient reads)
        if re.search(r"docs\s+documents\s+get", command, re.IGNORECASE):
            return await handle_docs_get(command)

        return await run_gws_command(command)

    # ------------------------------------------------------------------
    # Tool 2: gws_write — Write operations (requires HITL confirmation)
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("gws_write")
    async def gws_write(command: str, reason: str) -> dict:
        """Write-capable Google Workspace CLI tool.
        Supports '+send', 'update', 'insert', '+append', 'create'.
        Used for editing and creating content. Requires HITL confirmation."""
        if len(reason) < 10:
            raise ValueError(
                "AUDIT GATE: 'reason' must be at least 10 characters for audit trail."
            )

        verb = extract_verb(command)

        if verb in READ_ONLY_VERBS:
            raise ValueError(
                f"POLICY GATE: '{verb}' is read-only. "
                "Use gws_read to save human confirmation cycles."
            )

        if verb in DESTRUCTIVE_VERBS:
            raise ValueError(
                f"HITL SAFETY GATE: '{verb}' is a destructive operation. "
                "Use gws_destructive for this."
            )

        # Idempotency check for Drive creation
        if "drive" in command and ("create" in command or "insert" in command):
            name_match = re.search(r"""--name\s+["']?([^"']+)["']?""", command, re.IGNORECASE)
            folder_match = re.search(
                r"""--(?:folder|parent)\s+["']?([^"']+)["']?""", command, re.IGNORECASE
            )

            if name_match:
                resource_name = name_match.group(1)
                parent_id = folder_match.group(1) if folder_match else "root"

                async def _check_exists() -> bool:
                    list_cmd = (
                        f"drive files list --query "
                        f"\"name = '{resource_name}' and '{parent_id}' in parents\""
                    )
                    result = await run_gws_command(list_cmd)
                    files = result.get("parsed") or []
                    return isinstance(files, list) and len(files) > 0

                exists = await is_resource_exists(_check_exists)
                if exists:
                    return {
                        "stdout": (
                            f"gws_write: Resource '{resource_name}' already exists "
                            f"in '{parent_id}'. Skipping creation."
                        ),
                        "stderr": "",
                        "parsed": {"skipped": True, "name": resource_name},
                    }

        result = await run_gws_command(command)
        return {**result, "reason": reason}

    # ------------------------------------------------------------------
    # Tool 3: gws_destructive — Destructive operations (strict HITL)
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("gws_destructive")
    async def gws_destructive(command: str, reason: str) -> dict:
        """⚠️ DESTRUCTIVE — Delete-capable Google Workspace CLI tool.
        Supports 'delete', 'trash'. Use with EXTREME CAUTION.
        Requires explicit human confirmation as per Vopak Security Protocol."""
        if len(reason) < 10:
            raise ValueError(
                "AUDIT GATE: 'reason' must be at least 10 characters for audit trail."
            )

        verb = extract_verb(command)

        if verb not in DESTRUCTIVE_VERBS:
            raise ValueError(
                f"POLICY GATE: '{verb}' is not a destructive verb. "
                "Use gws_write or gws_read instead."
            )

        result = await run_gws_command(command)
        return {"result": result, "reason": reason}
