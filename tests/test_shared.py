"""Tests for shared infrastructure modules.

Covers:
- safe_execute decorator (success and error paths)
- extract_verb function (various GWS commands)
- compare_sheet_values function
- build_drive_query function
"""

from __future__ import annotations

import json

import pytest

from src.shared.common import agent_error, agent_success, safe_execute
from src.shared.gws_helpers import (
    build_drive_query,
    compare_sheet_values,
    escape_html,
    extract_verb,
    split_args,
)


# ==========================================
# safe_execute tests
# ==========================================


class TestSafeExecute:
    """Tests for the safe_execute decorator."""

    @pytest.mark.asyncio
    async def test_success_path(self) -> None:
        """Wrapping a successful async function returns a JSON AgentResult with success=True."""

        @safe_execute("test_tool")
        async def my_tool(value: str) -> dict:
            return {"key": value}

        result_str = await my_tool(value="hello")
        result = json.loads(result_str)

        assert result["success"] is True
        assert "test_tool completed successfully" in result["message"]
        assert result["data"]["key"] == "hello"
        assert "error_code" not in result

    @pytest.mark.asyncio
    async def test_error_path(self) -> None:
        """Wrapping a failing async function returns a JSON AgentResult with success=False."""

        @safe_execute("broken_tool")
        async def my_tool() -> dict:
            raise ValueError("something went wrong")

        result_str = await my_tool()
        result = json.loads(result_str)

        assert result["success"] is False
        assert "broken_tool failed" in result["message"]
        assert "something went wrong" in result["message"]
        assert result["data"] is None
        assert result["error_code"] == "EXECUTION_ERROR"

    @pytest.mark.asyncio
    async def test_api_error_code(self) -> None:
        """When the exception has a status_code attribute, the error_code reflects it."""

        @safe_execute("api_tool")
        async def my_tool() -> dict:
            err = Exception("not found")
            err.status_code = 404  # type: ignore[attr-defined]
            raise err

        result_str = await my_tool()
        result = json.loads(result_str)

        assert result["success"] is False
        assert result["error_code"] == "API_404"

    @pytest.mark.asyncio
    async def test_returns_json_string(self) -> None:
        """safe_execute always returns a valid JSON string, never a dict."""

        @safe_execute("json_tool")
        async def my_tool() -> str:
            return "plain string result"

        result_str = await my_tool()
        assert isinstance(result_str, str)
        result = json.loads(result_str)
        assert result["success"] is True


# ==========================================
# extract_verb tests
# ==========================================


class TestExtractVerb:
    """Tests for the extract_verb function."""

    def test_simple_get(self) -> None:
        assert extract_verb("gws drive files get --fileId abc123") == "get"

    def test_simple_list(self) -> None:
        assert extract_verb("gws drive files list") == "list"

    def test_create_verb(self) -> None:
        assert extract_verb("gws docs documents create --title 'My Doc'") == "create"

    def test_delete_verb(self) -> None:
        assert extract_verb("gws drive files delete --fileId abc") == "delete"

    def test_plugin_verb_priority(self) -> None:
        """Plugin verbs (+prefix) take priority over positional verbs."""
        assert extract_verb("gws gmail +send --to user@example.com") == "+send"

    def test_plugin_verb_triage(self) -> None:
        assert extract_verb("gws gmail +triage") == "+triage"

    def test_fallback_to_last_non_flag(self) -> None:
        """When no recognized verb is found, falls back to last non-flag token."""
        assert extract_verb("gws custom unknown-action") == "unknown-action"

    def test_empty_command(self) -> None:
        assert extract_verb("") == ""

    def test_single_token(self) -> None:
        assert extract_verb("gws") == "gws"

    def test_export_verb(self) -> None:
        assert extract_verb("gws drive files export --fileId abc --mimeType text/plain") == "export"

    def test_trash_verb(self) -> None:
        assert extract_verb("gws drive files trash --fileId abc") == "trash"

    def test_update_verb(self) -> None:
        assert extract_verb("gws sheets spreadsheets values update --range A1:B2") == "update"


# ==========================================
# compare_sheet_values tests
# ==========================================


class TestCompareSheetValues:
    """Tests for the compare_sheet_values function."""

    def test_matching_values(self) -> None:
        expected = [["a", "b"], ["c", "d"]]
        actual = [["a", "b"], ["c", "d"]]
        result = compare_sheet_values(expected, actual)

        assert result["verified"] is True
        assert result["total_cells"] == 4
        assert result["matched_cells"] == 4
        assert result["mismatches"] == []

    def test_single_mismatch(self) -> None:
        expected = [["a", "b"], ["c", "d"]]
        actual = [["a", "b"], ["c", "X"]]
        result = compare_sheet_values(expected, actual)

        assert result["verified"] is False
        assert result["total_cells"] == 4
        assert result["matched_cells"] == 3
        assert len(result["mismatches"]) == 1
        mismatch = result["mismatches"][0]
        assert mismatch["row"] == 2
        assert mismatch["col"] == 2
        assert mismatch["cell"] == "B2"
        assert mismatch["expected"] == "d"
        assert mismatch["actual"] == "X"

    def test_missing_actual_row(self) -> None:
        """When actual has fewer rows than expected, missing cells are empty strings."""
        expected = [["a", "b"], ["c", "d"]]
        actual = [["a", "b"]]
        result = compare_sheet_values(expected, actual)

        assert result["verified"] is False
        assert result["total_cells"] == 4
        assert result["matched_cells"] == 2
        assert len(result["mismatches"]) == 2

    def test_missing_actual_column(self) -> None:
        """When actual has fewer columns, missing cells show as empty."""
        expected = [["a", "b", "c"]]
        actual = [["a"]]
        result = compare_sheet_values(expected, actual)

        assert result["verified"] is False
        assert result["total_cells"] == 3
        assert result["matched_cells"] == 1

    def test_none_values(self) -> None:
        """None values in expected are treated as empty strings."""
        expected = [[None, "b"]]
        actual = [["", "b"]]
        result = compare_sheet_values(expected, actual)

        assert result["verified"] is True
        assert result["matched_cells"] == 2

    def test_numeric_values(self) -> None:
        """Numeric values are compared as strings (matching TypeScript's String() coercion)."""
        expected = [[1, 2.5]]
        actual = [["1", "2.5"]]
        result = compare_sheet_values(expected, actual)

        assert result["verified"] is True

    def test_empty_arrays(self) -> None:
        result = compare_sheet_values([], [])
        assert result["verified"] is True
        assert result["total_cells"] == 0


# ==========================================
# build_drive_query tests
# ==========================================


class TestBuildDriveQuery:
    """Tests for the build_drive_query function."""

    def test_no_filters(self) -> None:
        assert build_drive_query() is None

    def test_parent_id_only(self) -> None:
        result = build_drive_query(parent_id="folder123")
        assert result == "'folder123' in parents"

    def test_mime_type_only(self) -> None:
        result = build_drive_query(mime_type="application/vnd.google-apps.spreadsheet")
        assert result == "mimeType = 'application/vnd.google-apps.spreadsheet'"

    def test_name_contains_only(self) -> None:
        result = build_drive_query(name_contains="report")
        assert result == "name contains 'report'"

    def test_trashed_true(self) -> None:
        result = build_drive_query(trashed=True)
        assert result == "trashed = true"

    def test_trashed_false(self) -> None:
        result = build_drive_query(trashed=False)
        assert result == "trashed = false"

    def test_combined_filters(self) -> None:
        result = build_drive_query(
            parent_id="folder123",
            mime_type="application/pdf",
            name_contains="Q1",
            trashed=False,
        )
        assert result is not None
        assert "'folder123' in parents" in result
        assert "mimeType = 'application/pdf'" in result
        assert "name contains 'Q1'" in result
        assert "trashed = false" in result
        # Parts are joined with ' and '
        assert result.count(" and ") == 3

    def test_name_with_apostrophe_escaping(self) -> None:
        result = build_drive_query(name_contains="O'Brien")
        assert result is not None
        assert "O\\'Brien" in result


# ==========================================
# escape_html tests
# ==========================================


class TestEscapeHtml:
    """Tests for the escape_html function."""

    def test_no_special_chars(self) -> None:
        assert escape_html("hello world") == "hello world"

    def test_all_special_chars(self) -> None:
        assert escape_html('<div class="test">&</div>') == '&lt;div class=&quot;test&quot;&gt;&amp;&lt;/div&gt;'

    def test_ampersand_first(self) -> None:
        """Ampersand must be escaped first to avoid double-escaping."""
        assert escape_html("&lt;") == "&amp;lt;"


# ==========================================
# split_args tests
# ==========================================


class TestSplitArgs:
    """Tests for the split_args function."""

    def test_simple_args(self) -> None:
        assert split_args("drive files list") == ["drive", "files", "list"]

    def test_double_quoted_arg(self) -> None:
        result = split_args('drive files get --fileId "abc 123"')
        assert "--fileId" in result
        assert "abc 123" in result

    def test_single_quoted_arg(self) -> None:
        result = split_args("drive files get --title 'My Doc'")
        assert "My Doc" in result

    def test_mixed_quotes(self) -> None:
        result = split_args("""drive 'file name' --desc "some text" plain""")
        assert result == ["drive", "file name", "--desc", "some text", "plain"]


# ==========================================
# agent_success / agent_error tests
# ==========================================


class TestAgentResultHelpers:
    """Tests for agent_success and agent_error helpers."""

    def test_agent_success(self) -> None:
        result = agent_success("done", {"id": "123"})
        assert result["success"] is True
        assert result["message"] == "done"
        assert result["data"] == {"id": "123"}
        assert "error_code" not in result

    def test_agent_success_no_data(self) -> None:
        result = agent_success("done")
        assert result["data"] is None

    def test_agent_error_with_code(self) -> None:
        result = agent_error("failed", "NOT_FOUND")
        assert result["success"] is False
        assert result["message"] == "failed"
        assert result["data"] is None
        assert result["error_code"] == "NOT_FOUND"

    def test_agent_error_without_code(self) -> None:
        result = agent_error("failed")
        assert result["success"] is False
        assert "error_code" not in result
