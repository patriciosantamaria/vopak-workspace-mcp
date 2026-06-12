"""drive.py – Drive API tools for the vopak-workspace-mcp server.

Ported from gws_bridge.ts (lines 634–768). Provides:
- drive_list_files: List/search Drive files with structured filters
- drive_manage_file: Trash, rename, or move a Drive file (DESTRUCTIVE)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from fastmcp import FastMCP

from ..shared.common import (
    get_scoped_auth,
    create_drive_service,
    retry_with_backoff,
    safe_execute,
)
from ..shared.gws_helpers import build_drive_query

logger = logging.getLogger(__name__)

# ==========================================
# OAUTH SCOPES
# ==========================================

DRIVE_READONLY_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
DRIVE_READWRITE_SCOPES = ["https://www.googleapis.com/auth/drive"]


def register_tools(mcp: FastMCP) -> None:
    """Register all Drive tools on the given FastMCP server instance."""

    # ------------------------------------------------------------------
    # drive_list_files — Read-only
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("drive_list_files")
    async def drive_list_files(
        parent_id: Optional[str] = None,
        mime_type: Optional[str] = None,
        name_contains: Optional[str] = None,
        page_size: int = 25,
        page_token: Optional[str] = None,
        order_by: Optional[str] = None,
        trashed: bool = False,
    ) -> dict[str, Any]:
        """List files in Google Drive with structured filters.

        Builds Drive API queries programmatically from typed parameters — no shell quoting needed.
        Supports filtering by parent folder, MIME type, and name substring.
        Read-only — no confirmation required.

        Args:
            parent_id: Folder ID to list children of (omit for all files).
            mime_type: Filter by MIME type (e.g., 'application/vnd.google-apps.spreadsheet').
            name_contains: Filter files whose name contains this string.
            page_size: Max results per page (1–100, default 25).
            page_token: Pagination token from previous response.
            order_by: Sort order (e.g., 'modifiedTime desc', 'name'). Defaults to 'modifiedTime desc'.
            trashed: Include trashed files (default false).
        """
        if not 1 <= page_size <= 100:
            raise ValueError(f"page_size must be between 1 and 100, got {page_size}")

        q = build_drive_query(
            parent_id=parent_id,
            mime_type=mime_type,
            name_contains=name_contains,
            trashed=trashed,
        )
        effective_order = order_by or "modifiedTime desc"

        logger.info(
            '[API] drive_list_files: q="%s" pageSize=%d',
            q or "(none)", page_size,
        )

        creds = get_scoped_auth(DRIVE_READONLY_SCOPES)
        drive = create_drive_service(creds)

        request_kwargs: dict[str, Any] = {
            "pageSize": page_size,
            "orderBy": effective_order,
            "fields": "nextPageToken,files(id,name,mimeType,modifiedTime,size,parents)",
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
        }
        if q:
            request_kwargs["q"] = q
        if page_token:
            request_kwargs["pageToken"] = page_token

        async def _list() -> dict[str, Any]:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: drive.files().list(**request_kwargs).execute(),
            )

        response = await retry_with_backoff(_list)

        files = response.get("files", [])
        logger.info("[API] drive_list_files: Found %d files", len(files))

        return {
            "files": [
                {
                    "id": f.get("id"),
                    "name": f.get("name"),
                    "mimeType": f.get("mimeType"),
                    "modifiedTime": f.get("modifiedTime"),
                    "size": f.get("size"),
                    "parents": f.get("parents"),
                }
                for f in files
            ],
            "nextPageToken": response.get("nextPageToken"),
            "totalReturned": len(files),
            "query": q or "(no filter)",
            "message": f"Found {len(files)} file(s){f' matching: {q}' if q else ''}.",
        }

    # ------------------------------------------------------------------
    # drive_manage_file — ⚠️ DESTRUCTIVE
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("drive_manage_file")
    async def drive_manage_file(
        file_id: str,
        action: str,
        new_name: Optional[str] = None,
        target_folder_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """⚠️ DESTRUCTIVE — Trash, rename, or move a Drive file.

        Supports three operations:
        - 'trash': Moves file to trash (recoverable for 30 days).
        - 'rename': Changes file title (requires new_name).
        - 'move': Moves to a different parent folder (requires target_folder_id).

        Args:
            file_id: The ID of the file to manage.
            action: The action to perform. One of: 'trash', 'rename', 'move'.
            new_name: New file name (required for 'rename' action).
            target_folder_id: Target folder ID (required for 'move' action).
        """
        if action not in ("trash", "rename", "move"):
            raise ValueError(
                f"Invalid action '{action}'. Must be one of: trash, rename, move"
            )

        creds = get_scoped_auth(DRIVE_READWRITE_SCOPES)
        drive = create_drive_service(creds)

        if action == "trash":
            async def _trash() -> dict[str, Any]:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    lambda: drive.files().update(
                        fileId=file_id,
                        body={"trashed": True},
                        fields="id,name,trashed",
                        supportsAllDrives=True,
                    ).execute(),
                )

            response = await retry_with_backoff(_trash)
            return {
                "fileId": file_id,
                "action": "trash",
                "name": response.get("name"),
                "trashed": response.get("trashed"),
                "message": f"File '{response.get('name')}' moved to trash. Recoverable for 30 days.",
            }

        elif action == "rename":
            if not new_name:
                raise ValueError("'new_name' is required for the 'rename' action.")

            async def _rename() -> dict[str, Any]:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    lambda: drive.files().update(
                        fileId=file_id,
                        body={"name": new_name},
                        fields="id,name",
                        supportsAllDrives=True,
                    ).execute(),
                )

            response = await retry_with_backoff(_rename)
            return {
                "fileId": file_id,
                "action": "rename",
                "newName": response.get("name"),
                "message": f"File renamed to '{response.get('name')}'.",
            }

        else:  # action == "move"
            if not target_folder_id:
                raise ValueError("'target_folder_id' is required for the 'move' action.")

            # Get current parents to remove
            async def _get_parents() -> dict[str, Any]:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    lambda: drive.files().get(
                        fileId=file_id,
                        fields="parents",
                        supportsAllDrives=True,
                    ).execute(),
                )

            current_file = await retry_with_backoff(_get_parents)
            previous_parents = ",".join(current_file.get("parents", []))

            async def _move() -> dict[str, Any]:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    lambda: drive.files().update(
                        fileId=file_id,
                        addParents=target_folder_id,
                        removeParents=previous_parents,
                        fields="id,name,parents",
                        supportsAllDrives=True,
                    ).execute(),
                )

            response = await retry_with_backoff(_move)
            return {
                "fileId": file_id,
                "action": "move",
                "name": response.get("name"),
                "previousParents": previous_parents.split(",") if previous_parents else [],
                "newParents": response.get("parents"),
                "message": f"File '{response.get('name')}' moved to folder {target_folder_id}.",
            }
