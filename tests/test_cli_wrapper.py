"""Tests for GWS CLI wrapper tools (gws_read, gws_write, gws_destructive).

Validates verb-based permission gating:
- gws_read rejects write and destructive verbs
- gws_write rejects read-only and destructive verbs
- gws_destructive rejects non-destructive verbs
- gws_destructive description contains ⚠️ DESTRUCTIVE
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from fastmcp import FastMCP

from src.tools.cli_wrapper import register_tools


# ==========================================
# FIXTURES
# ==========================================


@pytest.fixture
def mcp_server() -> FastMCP:
    """Create a fresh FastMCP server with CLI wrapper tools registered."""
    mcp = FastMCP("test-workspace-cli")
    register_tools(mcp)
    return mcp


async def _get_tool_fn(mcp: FastMCP, name: str):
    """Retrieve a registered tool function by name from the FastMCP server."""
    tool = await mcp.get_tool(name)
    if tool is None:
        raise KeyError(f"Tool '{name}' not found in server")
    return tool.fn


async def _get_tool(mcp: FastMCP, name: str):
    """Retrieve a registered tool object by name from the FastMCP server."""
    tool = await mcp.get_tool(name)
    if tool is None:
        raise KeyError(f"Tool '{name}' not found in server")
    return tool


def _parse_result(raw: str) -> dict:
    """Parse a JSON AgentResult string returned by safe_execute-wrapped tools."""
    return json.loads(raw)


# ==========================================
# gws_read — REJECTION TESTS
# ==========================================


class TestGwsReadRejectsWriteVerbs:
    """gws_read must reject commands containing write verbs."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "command",
        [
            "gmail +send --to someone@example.com",
            "drive files create --name test",
            "docs documents update --documentId abc123",
            "sheets spreadsheets values update Sheet1!A1",
            "calendar events insert --calendarId primary",
        ],
    )
    async def test_rejects_write_verbs(self, mcp_server: FastMCP, command: str):
        fn = await _get_tool_fn(mcp_server, "gws_read")
        result = await fn(command=command)
        parsed = _parse_result(result)

        assert parsed["success"] is False
        assert "HITL SAFETY GATE" in parsed["message"]
        assert "gws_write or gws_destructive" in parsed["message"]


class TestGwsReadRejectsDestructiveVerbs:
    """gws_read must reject commands containing destructive verbs."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "command",
        [
            "drive files delete --fileId abc123",
            "drive files trash --fileId abc123",
        ],
    )
    async def test_rejects_destructive_verbs(self, mcp_server: FastMCP, command: str):
        fn = await _get_tool_fn(mcp_server, "gws_read")
        result = await fn(command=command)
        parsed = _parse_result(result)

        assert parsed["success"] is False
        assert "HITL SAFETY GATE" in parsed["message"]


# ==========================================
# gws_write — REJECTION TESTS
# ==========================================


class TestGwsWriteRejectsReadOnlyVerbs:
    """gws_write must reject commands containing read-only verbs."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "command",
        [
            "drive files list",
            "gmail messages get --id abc123",
            "docs documents get --documentId abc123",
            "calendar events list --calendarId primary",
        ],
    )
    async def test_rejects_read_only_verbs(self, mcp_server: FastMCP, command: str):
        fn = await _get_tool_fn(mcp_server, "gws_write")
        result = await fn(command=command, reason="Testing read-only rejection in gws_write")
        parsed = _parse_result(result)

        assert parsed["success"] is False
        assert "POLICY GATE" in parsed["message"]
        assert "gws_read" in parsed["message"]


class TestGwsWriteRejectsDestructiveVerbs:
    """gws_write must reject commands containing destructive verbs."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "command",
        [
            "drive files delete --fileId abc123",
            "drive files trash --fileId abc123",
        ],
    )
    async def test_rejects_destructive_verbs(self, mcp_server: FastMCP, command: str):
        fn = await _get_tool_fn(mcp_server, "gws_write")
        result = await fn(
            command=command,
            reason="Testing destructive rejection in gws_write",
        )
        parsed = _parse_result(result)

        assert parsed["success"] is False
        assert "HITL SAFETY GATE" in parsed["message"]
        assert "gws_destructive" in parsed["message"]


# ==========================================
# gws_destructive — REJECTION TESTS
# ==========================================


class TestGwsDestructiveRejectsNonDestructiveVerbs:
    """gws_destructive must reject commands that are NOT destructive."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "command",
        [
            "drive files list",
            "drive files get --fileId abc123",
            "drive files create --name test",
            "gmail +send --to someone@example.com",
            "docs documents update --documentId abc123",
        ],
    )
    async def test_rejects_non_destructive_verbs(self, mcp_server: FastMCP, command: str):
        fn = await _get_tool_fn(mcp_server, "gws_destructive")
        result = await fn(
            command=command,
            reason="Testing non-destructive rejection in gws_destructive",
        )
        parsed = _parse_result(result)

        assert parsed["success"] is False
        assert "POLICY GATE" in parsed["message"]
        assert "gws_write or gws_read" in parsed["message"]


# ==========================================
# gws_destructive — DESCRIPTION TEST
# ==========================================


class TestGwsDestructiveDescription:
    """gws_destructive description must contain ⚠️ DESTRUCTIVE."""

    @pytest.mark.asyncio
    async def test_has_destructive_marker(self, mcp_server: FastMCP):
        tool = await _get_tool(mcp_server, "gws_destructive")
        assert "⚠️ DESTRUCTIVE" in tool.description


# ==========================================
# gws_read — HAPPY PATH (mocked)
# ==========================================


class TestGwsReadHappyPath:
    """gws_read should call run_gws_command for valid read-only commands."""

    @pytest.mark.asyncio
    @patch("src.tools.cli_wrapper.run_gws_command", new_callable=AsyncMock)
    async def test_calls_run_gws_command(
        self, mock_run: AsyncMock, mcp_server: FastMCP
    ):
        mock_run.return_value = {
            "stdout": '{"files": []}',
            "stderr": "",
            "parsed": {"files": []},
        }

        fn = await _get_tool_fn(mcp_server, "gws_read")
        result = await fn(command="drive files list")
        parsed = _parse_result(result)

        assert parsed["success"] is True
        mock_run.assert_awaited_once_with("drive files list")


class TestGwsReadExportFastPath:
    """gws_read should route 'export' verb to handle_drive_export."""

    @pytest.mark.asyncio
    @patch("src.tools.cli_wrapper.handle_drive_export", new_callable=AsyncMock)
    async def test_routes_export_to_api(
        self, mock_export: AsyncMock, mcp_server: FastMCP
    ):
        mock_export.return_value = {
            "stdout": "exported content",
            "stderr": "",
            "parsed": "exported content",
        }

        fn = await _get_tool_fn(mcp_server, "gws_read")
        result = await fn(
            command="drive files export --params '{\"fileId\": \"abc\", \"mimeType\": \"text/plain\"}'"
        )
        parsed = _parse_result(result)

        assert parsed["success"] is True
        mock_export.assert_awaited_once()


class TestGwsReadDocsGetFastPath:
    """gws_read should route 'docs documents get' to handle_docs_get."""

    @pytest.mark.asyncio
    @patch("src.tools.cli_wrapper.handle_docs_get", new_callable=AsyncMock)
    async def test_routes_docs_get_to_api(
        self, mock_docs: AsyncMock, mcp_server: FastMCP
    ):
        mock_docs.return_value = {
            "stdout": '{"title": "Test Doc"}',
            "stderr": "",
            "parsed": {"title": "Test Doc"},
        }

        fn = await _get_tool_fn(mcp_server, "gws_read")
        result = await fn(
            command="docs documents get --params '{\"documentId\": \"abc123\"}'"
        )
        parsed = _parse_result(result)

        assert parsed["success"] is True
        mock_docs.assert_awaited_once()


# ==========================================
# gws_destructive — HAPPY PATH (mocked)
# ==========================================


class TestGwsDestructiveHappyPath:
    """gws_destructive should execute valid destructive commands."""

    @pytest.mark.asyncio
    @patch("src.tools.cli_wrapper.run_gws_command", new_callable=AsyncMock)
    async def test_executes_delete_command(
        self, mock_run: AsyncMock, mcp_server: FastMCP
    ):
        mock_run.return_value = {
            "stdout": "{}",
            "stderr": "",
            "parsed": {},
        }

        fn = await _get_tool_fn(mcp_server, "gws_destructive")
        result = await fn(
            command="drive files delete --fileId abc123",
            reason="Cleaning up test files from integration run",
        )
        parsed = _parse_result(result)

        assert parsed["success"] is True
        mock_run.assert_awaited_once_with("drive files delete --fileId abc123")


# ==========================================
# gws_write / gws_destructive — REASON VALIDATION
# ==========================================


class TestReasonValidation:
    """gws_write and gws_destructive must reject short reasons."""

    @pytest.mark.asyncio
    async def test_gws_write_rejects_short_reason(self, mcp_server: FastMCP):
        fn = await _get_tool_fn(mcp_server, "gws_write")
        result = await fn(command="drive files create --name test", reason="short")
        parsed = _parse_result(result)

        assert parsed["success"] is False
        assert "AUDIT GATE" in parsed["message"]

    @pytest.mark.asyncio
    async def test_gws_destructive_rejects_short_reason(self, mcp_server: FastMCP):
        fn = await _get_tool_fn(mcp_server, "gws_destructive")
        result = await fn(command="drive files delete --fileId abc", reason="short")
        parsed = _parse_result(result)

        assert parsed["success"] is False
        assert "AUDIT GATE" in parsed["message"]
