"""test_sheets.py – Unit tests for the Sheets tools.

Tests the 4 tools in src/tools/sheets.py with mocked Google API responses.
Mirrors the test patterns from gws_bridge.test.ts.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module-level patches: prevent ADC discovery at import time
# ---------------------------------------------------------------------------

_mock_creds = MagicMock()
_mock_creds.token = "fake-token"
_mock_creds.valid = True


def _fake_get_scoped_auth(scopes: list[str]) -> MagicMock:
    """Return a fake credentials object without touching ADC."""
    return _mock_creds


# ---------------------------------------------------------------------------
# Helper: build a mock Sheets service
# ---------------------------------------------------------------------------


def _make_mock_sheets() -> MagicMock:
    """Create a deeply-nested mock matching the Sheets API v4 client shape."""
    mock = MagicMock()
    # sheets.spreadsheets().values().get()
    mock.spreadsheets.return_value.values.return_value.get.return_value.execute = MagicMock()
    # sheets.spreadsheets().values().update()
    mock.spreadsheets.return_value.values.return_value.update.return_value.execute = MagicMock()
    # sheets.spreadsheets().values().batchUpdate()
    mock.spreadsheets.return_value.values.return_value.batchUpdate.return_value.execute = MagicMock()
    # sheets.spreadsheets().get()
    mock.spreadsheets.return_value.get.return_value.execute = MagicMock()
    return mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_sheets():
    """Provide a mock Sheets service and patch get_scoped_auth + create_sheets_service."""
    mock_svc = _make_mock_sheets()

    with (
        patch("src.tools.sheets.get_scoped_auth", side_effect=_fake_get_scoped_auth),
        patch("src.tools.sheets.create_sheets_service", return_value=mock_svc),
    ):
        yield mock_svc


@pytest.fixture()
def tools(mock_sheets):
    """Register Sheets tools on a fresh FastMCP and return the wrapped tool functions."""
    from fastmcp import FastMCP
    from src.tools.sheets import register_tools

    mcp = FastMCP("test-sheets")
    register_tools(mcp)

    # FastMCP v2 stores tools in _local_provider._components keyed as 'tool:{name}@'
    components = mcp._local_provider._components
    return {
        name.split(":")[1].split("@")[0]: comp.fn
        for name, comp in components.items()
        if name.startswith("tool:")
    }


# ==========================================
# TESTS: sheets_read_range
# ==========================================


class TestSheetsReadRange:
    """Tests for the sheets_read_range tool."""

    async def test_read_range_returns_values(self, tools, mock_sheets):
        """Basic read should return the values from the API response."""
        mock_sheets.spreadsheets().values().get().execute.return_value = {
            "range": "Sheet1!A1:B2",
            "values": [["a", "b"], ["c", "d"]],
        }

        result_json = await tools["sheets_read_range"](
            spreadsheet_id="spreadsheet-123",
            range="Sheet1!A1:B2",
        )
        result = json.loads(result_json)

        assert result["success"] is True
        data = result["data"]
        assert data["values"] == [["a", "b"], ["c", "d"]]
        assert data["rowCount"] == 2
        assert data["columnCount"] == 2

    async def test_read_range_empty_sheet(self, tools, mock_sheets):
        """Reading an empty range should return 0 rows × 0 columns."""
        mock_sheets.spreadsheets().values().get().execute.return_value = {
            "range": "Sheet1!A1:Z100",
            "values": [],
        }

        result_json = await tools["sheets_read_range"](
            spreadsheet_id="spreadsheet-123",
            range="Sheet1!A1:Z100",
        )
        result = json.loads(result_json)

        assert result["success"] is True
        assert result["data"]["rowCount"] == 0
        assert result["data"]["columnCount"] == 0

    async def test_read_range_no_values_key(self, tools, mock_sheets):
        """API may omit 'values' entirely for empty ranges."""
        mock_sheets.spreadsheets().values().get().execute.return_value = {
            "range": "Sheet1!A1:A1",
        }

        result_json = await tools["sheets_read_range"](
            spreadsheet_id="spreadsheet-123",
            range="Sheet1!A1:A1",
        )
        result = json.loads(result_json)

        assert result["success"] is True
        assert result["data"]["values"] == []

    async def test_read_range_invalid_render_option(self, tools, mock_sheets):
        """Invalid value_render_option should return an error."""
        result_json = await tools["sheets_read_range"](
            spreadsheet_id="spreadsheet-123",
            range="Sheet1!A1:A1",
            value_render_option="INVALID",
        )
        result = json.loads(result_json)

        assert result["success"] is False
        assert "Invalid value_render_option" in result["message"]


# ==========================================
# TESTS: sheets_get_structure
# ==========================================


class TestSheetsGetStructure:
    """Tests for the sheets_get_structure tool."""

    async def test_get_structure_basic(self, tools, mock_sheets):
        """Should return sheet metadata with title, sheets, and named ranges."""
        mock_sheets.spreadsheets().get().execute.return_value = {
            "spreadsheetId": "ss-abc",
            "properties": {"title": "My Spreadsheet"},
            "sheets": [
                {
                    "properties": {
                        "sheetId": 0,
                        "title": "Sheet1",
                        "index": 0,
                        "gridProperties": {
                            "rowCount": 1000,
                            "columnCount": 26,
                            "frozenRowCount": 1,
                            "frozenColumnCount": 0,
                        },
                    }
                },
                {
                    "properties": {
                        "sheetId": 1,
                        "title": "Data",
                        "index": 1,
                        "gridProperties": {
                            "rowCount": 500,
                            "columnCount": 10,
                        },
                    }
                },
            ],
            "namedRanges": [
                {"name": "HeaderRange", "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1}},
            ],
        }

        result_json = await tools["sheets_get_structure"](
            spreadsheet_id="ss-abc",
        )
        result = json.loads(result_json)

        assert result["success"] is True
        data = result["data"]
        assert data["title"] == "My Spreadsheet"
        assert data["sheetCount"] == 2
        assert data["sheets"][0]["title"] == "Sheet1"
        assert data["sheets"][0]["rowCount"] == 1000
        assert data["sheets"][0]["frozenRowCount"] == 1
        assert data["sheets"][1]["title"] == "Data"
        assert data["sheets"][1]["frozenRowCount"] == 0  # defaults to 0
        assert len(data["namedRanges"]) == 1
        assert data["namedRanges"][0]["name"] == "HeaderRange"

    async def test_get_structure_empty_spreadsheet(self, tools, mock_sheets):
        """Should handle a spreadsheet with no sheets or named ranges."""
        mock_sheets.spreadsheets().get().execute.return_value = {
            "spreadsheetId": "ss-empty",
            "properties": {"title": "Empty"},
        }

        result_json = await tools["sheets_get_structure"](
            spreadsheet_id="ss-empty",
        )
        result = json.loads(result_json)

        assert result["success"] is True
        assert result["data"]["sheetCount"] == 0
        assert result["data"]["namedRanges"] == []


# ==========================================
# TESTS: sheets_write_from_file
# ==========================================


class TestSheetsWriteFromFile:
    """Tests for the sheets_write_from_file tool."""

    async def test_write_from_file_success(self, tools, mock_sheets):
        """Valid JSON file should be written and return cell counts."""
        mock_sheets.spreadsheets().values().batchUpdate().execute.return_value = {
            "totalUpdatedCells": 6,
            "totalUpdatedRows": 2,
            "totalUpdatedColumns": 3,
            "totalUpdatedSheets": 1,
        }

        payload = {
            "data": [
                {"range": "Sheet1!A1:C2", "values": [["a", "b", "c"], ["d", "e", "f"]]},
            ],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp:
            json.dump(payload, tmp)
            tmp_path = tmp.name

        try:
            result_json = await tools["sheets_write_from_file"](
                spreadsheet_id="ss-write",
                file_path=tmp_path,
            )
            result = json.loads(result_json)

            assert result["success"] is True
            assert result["data"]["totalUpdatedCells"] == 6
            assert result["data"]["rangesProcessed"] == 1
        finally:
            os.unlink(tmp_path)

    async def test_write_from_file_missing_file(self, tools, mock_sheets):
        """Should return an error for a non-existent file."""
        result_json = await tools["sheets_write_from_file"](
            spreadsheet_id="ss-write",
            file_path="/nonexistent/path/data.json",
        )
        result = json.loads(result_json)

        assert result["success"] is False
        assert "FILE_READ_ERROR" in result["message"]

    async def test_write_from_file_invalid_json(self, tools, mock_sheets):
        """Should return an error for invalid JSON content."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp:
            tmp.write("not valid json {{{")
            tmp_path = tmp.name

        try:
            result_json = await tools["sheets_write_from_file"](
                spreadsheet_id="ss-write",
                file_path=tmp_path,
            )
            result = json.loads(result_json)

            assert result["success"] is False
            assert "JSON_PARSE_ERROR" in result["message"]
        finally:
            os.unlink(tmp_path)

    async def test_write_from_file_empty_data_array(self, tools, mock_sheets):
        """Should reject payload with empty data array."""
        payload = {"data": []}

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp:
            json.dump(payload, tmp)
            tmp_path = tmp.name

        try:
            result_json = await tools["sheets_write_from_file"](
                spreadsheet_id="ss-write",
                file_path=tmp_path,
            )
            result = json.loads(result_json)

            assert result["success"] is False
            assert "SCHEMA_VALIDATION_ERROR" in result["message"]
        finally:
            os.unlink(tmp_path)

    async def test_write_from_file_missing_data_field(self, tools, mock_sheets):
        """Should reject payload without 'data' field."""
        payload = {"ranges": [{"range": "A1", "values": [["x"]]}]}

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp:
            json.dump(payload, tmp)
            tmp_path = tmp.name

        try:
            result_json = await tools["sheets_write_from_file"](
                spreadsheet_id="ss-write",
                file_path=tmp_path,
            )
            result = json.loads(result_json)

            assert result["success"] is False
            assert "SCHEMA_VALIDATION_ERROR" in result["message"]
        finally:
            os.unlink(tmp_path)


# ==========================================
# TESTS: sheets_verify_range
# ==========================================


class TestSheetsVerifyRange:
    """Tests for the sheets_verify_range tool."""

    async def test_verify_range_all_match(self, tools, mock_sheets):
        """Should return verified=True when all cells match."""
        mock_sheets.spreadsheets().values().update().execute.return_value = {
            "updatedCells": 4,
        }
        mock_sheets.spreadsheets().values().get().execute.return_value = {
            "values": [["a", "b"], ["c", "d"]],
        }

        result_json = await tools["sheets_verify_range"](
            spreadsheet_id="ss-verify",
            range="Sheet1!A1:B2",
            expected_values=[["a", "b"], ["c", "d"]],
        )
        result = json.loads(result_json)

        assert result["success"] is True
        data = result["data"]
        assert data["verified"] is True
        assert data["totalCells"] == 4
        assert data["matchedCells"] == 4
        assert data["mismatchCount"] == 0
        assert "✅" in data["message"]

    async def test_verify_range_mismatch_detected(self, tools, mock_sheets):
        """Should return verified=False with mismatch details."""
        mock_sheets.spreadsheets().values().update().execute.return_value = {
            "updatedCells": 4,
        }
        mock_sheets.spreadsheets().values().get().execute.return_value = {
            "values": [["a", "b"], ["c", "X"]],  # d → X mismatch
        }

        result_json = await tools["sheets_verify_range"](
            spreadsheet_id="ss-verify",
            range="Sheet1!A1:B2",
            expected_values=[["a", "b"], ["c", "d"]],
        )
        result = json.loads(result_json)

        assert result["success"] is True  # Tool succeeded, but verification failed
        data = result["data"]
        assert data["verified"] is False
        assert data["mismatchCount"] == 1
        assert data["mismatches"][0]["cell"] == "B2"
        assert data["mismatches"][0]["expected"] == "d"
        assert data["mismatches"][0]["actual"] == "X"
        assert "❌" in data["message"]

    async def test_verify_range_missing_rows_in_readback(self, tools, mock_sheets):
        """Should detect mismatches when readback has fewer rows."""
        mock_sheets.spreadsheets().values().update().execute.return_value = {
            "updatedCells": 3,
        }
        mock_sheets.spreadsheets().values().get().execute.return_value = {
            "values": [["a"]],  # Only 1 of 3 rows returned
        }

        result_json = await tools["sheets_verify_range"](
            spreadsheet_id="ss-verify",
            range="Sheet1!A1:A3",
            expected_values=[["a"], ["b"], ["c"]],
        )
        result = json.loads(result_json)

        data = result["data"]
        assert data["verified"] is False
        assert data["mismatchCount"] == 2  # b and c are missing

    async def test_verify_range_with_null_values(self, tools, mock_sheets):
        """Should handle null values correctly in comparison."""
        mock_sheets.spreadsheets().values().update().execute.return_value = {
            "updatedCells": 4,
        }
        mock_sheets.spreadsheets().values().get().execute.return_value = {
            "values": [["a", None], [None, "d"]],
        }

        result_json = await tools["sheets_verify_range"](
            spreadsheet_id="ss-verify",
            range="Sheet1!A1:B2",
            expected_values=[["a", None], [None, "d"]],
        )
        result = json.loads(result_json)

        assert result["data"]["verified"] is True
        assert result["data"]["totalCells"] == 4

    async def test_verify_range_caps_mismatches_at_50(self, tools, mock_sheets):
        """Should cap returned mismatches at 50 even if more exist."""
        # Create 60 expected values that all mismatch
        expected = [[f"expected-{i}"] for i in range(60)]
        actual_values = [[f"actual-{i}"] for i in range(60)]

        mock_sheets.spreadsheets().values().update().execute.return_value = {
            "updatedCells": 60,
        }
        mock_sheets.spreadsheets().values().get().execute.return_value = {
            "values": actual_values,
        }

        result_json = await tools["sheets_verify_range"](
            spreadsheet_id="ss-verify",
            range="Sheet1!A1:A60",
            expected_values=expected,
        )
        result = json.loads(result_json)

        data = result["data"]
        assert data["verified"] is False
        assert len(data["mismatches"]) == 50  # Capped
        assert data["mismatchCount"] == 60  # But total count is accurate
