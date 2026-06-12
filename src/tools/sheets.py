"""sheets.py – Sheets API tools for the vopak-workspace-mcp server.

Ported from gws_bridge.ts (lines 557–925). Provides:
- sheets_read_range: Read cell values from a range
- sheets_get_structure: Get spreadsheet metadata (sheets, dimensions, named ranges)
- sheets_write_from_file: Bulk-write from a JSON file on disk
- sheets_verify_range: Atomic write + readback + cell-by-cell comparison
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from fastmcp import FastMCP

from ..shared.common import (
    get_scoped_auth,
    create_sheets_service,
    retry_with_backoff,
    safe_execute,
)
from ..shared.gws_helpers import compare_sheet_values, CellValue

logger = logging.getLogger(__name__)

# ==========================================
# OAUTH SCOPES
# ==========================================

SHEETS_READONLY_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SHEETS_READWRITE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def register_tools(mcp: FastMCP) -> None:
    """Register all Sheets tools on the given FastMCP server instance."""

    # ------------------------------------------------------------------
    # sheets_read_range — Read-only
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("sheets_read_range")
    async def sheets_read_range(
        spreadsheet_id: str,
        range: str,
        value_render_option: str = "FORMATTED_VALUE",
    ) -> dict[str, Any]:
        """Read cell values from a Google Sheets range.

        Returns the 2D array of values for the specified A1-notation range.
        Supports formatted values, raw values, or formulas via value_render_option.
        Read-only — no confirmation required.

        Args:
            spreadsheet_id: The ID of the target spreadsheet.
            range: A1 notation range to read (e.g., 'Sheet1!A1:Z100').
            value_render_option: How values should be rendered. One of
                FORMATTED_VALUE (display strings), UNFORMATTED_VALUE (raw numbers/dates),
                or FORMULA (formulas). Defaults to FORMATTED_VALUE.
        """
        if value_render_option not in ("FORMATTED_VALUE", "UNFORMATTED_VALUE", "FORMULA"):
            raise ValueError(
                f"Invalid value_render_option '{value_render_option}'. "
                "Must be one of: FORMATTED_VALUE, UNFORMATTED_VALUE, FORMULA"
            )

        logger.info(
            "[API] sheets_read_range: Reading %s from %s (render: %s)",
            range, spreadsheet_id, value_render_option,
        )

        creds = get_scoped_auth(SHEETS_READONLY_SCOPES)
        sheets = create_sheets_service(creds)

        async def _read() -> dict[str, Any]:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: sheets.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range=range,
                    valueRenderOption=value_render_option,
                ).execute(),
            )

        response = await retry_with_backoff(_read)

        values: list[list[Any]] = response.get("values", [])
        row_count = len(values)
        column_count = max((len(r) for r in values), default=0) if row_count > 0 else 0

        logger.info("[API] sheets_read_range: Got %d rows × %d columns", row_count, column_count)

        return {
            "spreadsheetId": spreadsheet_id,
            "range": response.get("range", range),
            "values": values,
            "rowCount": row_count,
            "columnCount": column_count,
            "message": f"Read {row_count} rows × {column_count} columns from '{response.get('range', range)}'.",
        }

    # ------------------------------------------------------------------
    # sheets_get_structure — Read-only
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("sheets_get_structure")
    async def sheets_get_structure(
        spreadsheet_id: str,
    ) -> dict[str, Any]:
        """Get spreadsheet metadata: title, sheet names, dimensions, and named ranges.

        Use this to discover sheet structure before reading or writing data.
        Read-only — no confirmation required.

        Args:
            spreadsheet_id: The ID of the target spreadsheet.
        """
        logger.info("[API] sheets_get_structure: Fetching metadata for %s", spreadsheet_id)

        creds = get_scoped_auth(SHEETS_READONLY_SCOPES)
        sheets = create_sheets_service(creds)

        async def _get() -> dict[str, Any]:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: sheets.spreadsheets().get(
                    spreadsheetId=spreadsheet_id,
                    fields="spreadsheetId,properties.title,sheets.properties,namedRanges",
                ).execute(),
            )

        spreadsheet = await retry_with_backoff(_get)

        sheet_list = []
        for s in spreadsheet.get("sheets", []):
            props = s.get("properties", {})
            grid = props.get("gridProperties", {})
            sheet_list.append({
                "sheetId": props.get("sheetId"),
                "title": props.get("title"),
                "index": props.get("index"),
                "rowCount": grid.get("rowCount"),
                "colCount": grid.get("columnCount"),
                "frozenRowCount": grid.get("frozenRowCount", 0),
                "frozenColCount": grid.get("frozenColumnCount", 0),
            })

        named_ranges = [
            {"name": nr.get("name"), "range": nr.get("range")}
            for nr in spreadsheet.get("namedRanges", [])
        ]

        title = spreadsheet.get("properties", {}).get("title", "")
        logger.info(
            "[API] sheets_get_structure: Found %d sheets, %d named ranges",
            len(sheet_list), len(named_ranges),
        )

        return {
            "spreadsheetId": spreadsheet.get("spreadsheetId"),
            "title": title,
            "sheetCount": len(sheet_list),
            "sheets": sheet_list,
            "namedRanges": named_ranges,
            "message": (
                f"Spreadsheet '{title}' has {len(sheet_list)} sheet(s) "
                f"and {len(named_ranges)} named range(s)."
            ),
        }

    # ------------------------------------------------------------------
    # sheets_write_from_file — Write (HITL)
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("sheets_write_from_file")
    async def sheets_write_from_file(
        spreadsheet_id: str,
        file_path: str,
        value_input_option: str = "USER_ENTERED",
    ) -> dict[str, Any]:
        """Bulk-write to Google Sheets from a JSON file on disk.

        Reads a JSON payload file and executes a single Sheets API batchUpdate.
        Replaces 16+ sequential write calls with 1 atomic API call.
        The JSON file must contain: { "data": [{ "range": "Sheet1!A1:C3", "values": [[...], ...] }] }.
        Requires HITL confirmation (mutates spreadsheet data).

        Args:
            spreadsheet_id: Target spreadsheet ID.
            file_path: Absolute path to JSON file containing write payload.
            value_input_option: How input data should be interpreted.
                USER_ENTERED parses formulas; RAW stores literally. Defaults to USER_ENTERED.
        """
        if value_input_option not in ("RAW", "USER_ENTERED"):
            raise ValueError(
                f"Invalid value_input_option '{value_input_option}'. Must be RAW or USER_ENTERED"
            )

        # 1. Read and validate the JSON payload file
        logger.info("[API] sheets_write_from_file: Reading payload from %s", file_path)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_content = f.read()
        except (FileNotFoundError, PermissionError, OSError) as err:
            raise RuntimeError(
                f"FILE_READ_ERROR: Could not read payload file '{file_path}': {err}"
            ) from err

        file_size_kb = round(len(raw_content) / 1024, 1)
        logger.info("[API] Payload file size: %.1f KB", file_size_kb)

        try:
            parsed_json = json.loads(raw_content)
        except json.JSONDecodeError as err:
            raise RuntimeError(
                f"JSON_PARSE_ERROR: File '{file_path}' contains invalid JSON: {err}"
            ) from err

        # 2. Validate structure
        if not isinstance(parsed_json, dict) or "data" not in parsed_json:
            raise RuntimeError(
                "SCHEMA_VALIDATION_ERROR: Payload must contain a 'data' array of ValueRange objects"
            )

        data = parsed_json["data"]
        if not isinstance(data, list) or len(data) == 0:
            raise RuntimeError(
                "SCHEMA_VALIDATION_ERROR: 'data' must be a non-empty array of ValueRange objects"
            )

        for i, entry in enumerate(data):
            if not isinstance(entry, dict):
                raise RuntimeError(f"SCHEMA_VALIDATION_ERROR: data[{i}] must be an object")
            if "range" not in entry or "values" not in entry:
                raise RuntimeError(
                    f"SCHEMA_VALIDATION_ERROR: data[{i}] must have 'range' and 'values' fields"
                )

        total_ranges = len(data)
        total_cells = sum(
            len(cell)
            for entry in data
            for row in entry.get("values", [])
            for cell in [row]  # count cells in each row
        )
        # Recount properly: sum of row lengths
        total_cells = sum(
            len(row)
            for entry in data
            for row in entry.get("values", [])
        )
        logger.info(
            "[API] Batch writing %d ranges (%d cells) to spreadsheet %s",
            total_ranges, total_cells, spreadsheet_id,
        )

        # 3. Execute Sheets API batchUpdate
        creds = get_scoped_auth(SHEETS_READWRITE_SCOPES)
        sheets = create_sheets_service(creds)

        async def _batch_update() -> dict[str, Any]:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: sheets.spreadsheets().values().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={
                        "valueInputOption": value_input_option,
                        "data": data,
                    },
                ).execute(),
            )

        result = await retry_with_backoff(_batch_update)

        logger.info(
            "[API] Batch write complete: %s cells updated across %s sheets",
            result.get("totalUpdatedCells"), result.get("totalUpdatedSheets"),
        )

        return {
            "spreadsheetId": spreadsheet_id,
            "totalUpdatedCells": result.get("totalUpdatedCells"),
            "totalUpdatedRows": result.get("totalUpdatedRows"),
            "totalUpdatedColumns": result.get("totalUpdatedColumns"),
            "totalUpdatedSheets": result.get("totalUpdatedSheets"),
            "rangesProcessed": total_ranges,
            "payloadSizeKB": file_size_kb,
            "message": (
                f"Successfully wrote {result.get('totalUpdatedCells')} cells across "
                f"{total_ranges} ranges from '{file_path}' ({file_size_kb} KB)."
            ),
        }

    # ------------------------------------------------------------------
    # sheets_verify_range — Write + Verify (HITL)
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("sheets_verify_range")
    async def sheets_verify_range(
        spreadsheet_id: str,
        range: str,
        expected_values: list[list[CellValue]],
        value_input_option: str = "RAW",
    ) -> dict[str, Any]:
        """Atomic write + readback + compare for Google Sheets.

        Writes values to a range, immediately reads them back, and compares cell-by-cell.
        Returns pass/fail with per-cell mismatch details.
        Use RAW value_input_option for exact verification (avoids format-induced mismatches).
        Requires HITL confirmation (mutates spreadsheet data).

        Args:
            spreadsheet_id: Target spreadsheet ID.
            range: A1 notation range to write and verify (e.g., 'Sheet1!A1:C3').
            expected_values: 2D array of values to write and then verify.
            value_input_option: How input data should be interpreted.
                RAW recommended for exact verification. Defaults to RAW.
        """
        if value_input_option not in ("RAW", "USER_ENTERED"):
            raise ValueError(
                f"Invalid value_input_option '{value_input_option}'. Must be RAW or USER_ENTERED"
            )

        creds = get_scoped_auth(SHEETS_READWRITE_SCOPES)
        sheets = create_sheets_service(creds)

        # 1. Write
        logger.info("[API] sheets_verify_range: Writing to %s...", range)

        async def _write() -> dict[str, Any]:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: sheets.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=range,
                    valueInputOption=value_input_option,
                    body={"values": expected_values},
                ).execute(),
            )

        write_response = await retry_with_backoff(_write)
        updated_cells = write_response.get("updatedCells", 0)
        logger.info("[API] Write complete: %d cells updated", updated_cells)

        # 2. Read back (use UNFORMATTED_VALUE to get raw data for comparison)
        logger.info("[API] sheets_verify_range: Reading back %s...", range)

        async def _read() -> dict[str, Any]:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: sheets.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range=range,
                    valueRenderOption="UNFORMATTED_VALUE",
                ).execute(),
            )

        read_response = await retry_with_backoff(_read)
        read_values: list[list[Any]] = read_response.get("values", [])

        # 3. Compare cell-by-cell
        result = compare_sheet_values(expected_values, read_values)
        logger.info(
            "[API] Verification: %d/%d cells match (%s)",
            result["matched_cells"], result["total_cells"],
            "PASS" if result["verified"] else "FAIL",
        )

        return {
            "verified": result["verified"],
            "totalCells": result["total_cells"],
            "matchedCells": result["matched_cells"],
            "mismatches": result["mismatches"][:50],  # Cap at 50 to avoid bloated responses
            "mismatchCount": len(result["mismatches"]),
            "range": range,
            "message": (
                f"✅ Verified: All {result['total_cells']} cells in '{range}' match expected values."
                if result["verified"]
                else (
                    f"❌ Verification failed: {len(result['mismatches'])} of "
                    f"{result['total_cells']} cells differ in '{range}'."
                )
            ),
        }
