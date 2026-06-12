"""Tests for GCP CLI wrapper tools (gcp_read, gcp_write, gcp_destructive).

Validates verb-based permission gating:
- gcp_read rejects write and destructive verbs
- gcp_write rejects read-only and destructive verbs
- gcp_destructive rejects non-destructive verbs
- Reason validation on write and destructive tools
- gcp_destructive description contains ⚠️ DESTRUCTIVE
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from fastmcp import FastMCP

from src.tools.gcp_cli import register_tools


# ==========================================
# FIXTURES
# ==========================================


@pytest.fixture
def mcp_server() -> FastMCP:
    """Create a fresh FastMCP server with GCP CLI tools registered."""
    mcp = FastMCP("test-gcp-cli")
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
# gcp_read — REJECTION TESTS
# ==========================================


class TestGcpReadRejectsWriteVerbs:
    """gcp_read must reject commands containing write verbs."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "command",
        [
            "gcloud run deploy my-service --image=gcr.io/proj/img",
            "gcloud iam service-accounts create my-sa",
            "gcloud services enable compute.googleapis.com",
            "gcloud compute instances start my-vm",
        ],
    )
    async def test_rejects_write_verbs(self, mcp_server: FastMCP, command: str):
        fn = await _get_tool_fn(mcp_server, "gcp_read")
        result = await fn(command=command)
        parsed = _parse_result(result)

        assert parsed["success"] is False
        assert "POLICY GATE" in parsed["message"]
        assert "gcp_write" in parsed["message"]


class TestGcpReadRejectsDestructiveVerbs:
    """gcp_read must reject commands containing destructive verbs."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "command",
        [
            "gcloud projects delete my-project",
            "bq rm dataset.table",
            "gsutil rm gs://bucket/file.txt",
            "gcloud iam service-accounts delete my-sa@proj.iam.gserviceaccount.com",
        ],
    )
    async def test_rejects_destructive_verbs(self, mcp_server: FastMCP, command: str):
        fn = await _get_tool_fn(mcp_server, "gcp_read")
        result = await fn(command=command)
        parsed = _parse_result(result)

        assert parsed["success"] is False
        assert "HITL SAFETY GATE" in parsed["message"]
        assert "gcp_destructive" in parsed["message"]


# ==========================================
# gcp_read — HAPPY PATH (mocked)
# ==========================================


class TestGcpReadHappyPath:
    """gcp_read should call run_gcp_command for valid read-only commands."""

    @pytest.mark.asyncio
    @patch("src.tools.gcp_cli.run_gcp_command", new_callable=AsyncMock)
    @pytest.mark.parametrize(
        "command",
        [
            "gcloud run services list --project=my-project",
            "gcloud compute instances describe my-vm --zone=us-central1-a",
            "bq ls --project_id=my-project",
            "gsutil ls gs://my-bucket",
        ],
    )
    async def test_accepts_read_verbs(
        self, mock_run: AsyncMock, mcp_server: FastMCP, command: str
    ):
        mock_run.return_value = {
            "stdout": '{"items": []}',
            "stderr": "",
            "parsed": {"items": []},
        }

        fn = await _get_tool_fn(mcp_server, "gcp_read")
        result = await fn(command=command)
        parsed = _parse_result(result)

        assert parsed["success"] is True
        mock_run.assert_awaited_once()


# ==========================================
# gcp_write — REJECTION TESTS
# ==========================================


class TestGcpWriteRejectsReadVerbs:
    """gcp_write must reject commands containing read-only verbs."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "command",
        [
            "gcloud run services list",
            "gcloud compute instances describe my-vm",
            "bq ls",
            "bq show dataset.table",
        ],
    )
    async def test_rejects_read_verbs(self, mcp_server: FastMCP, command: str):
        fn = await _get_tool_fn(mcp_server, "gcp_write")
        result = await fn(
            command=command,
            reason="Testing read-only rejection in gcp_write",
        )
        parsed = _parse_result(result)

        assert parsed["success"] is False
        assert "POLICY GATE" in parsed["message"]
        assert "gcp_read" in parsed["message"]


class TestGcpWriteRejectsDestructiveVerbs:
    """gcp_write must reject commands containing destructive verbs."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "command",
        [
            "gcloud projects delete my-project",
            "bq rm dataset.table",
            "gsutil rm gs://bucket/file.txt",
        ],
    )
    async def test_rejects_destructive_verbs(self, mcp_server: FastMCP, command: str):
        fn = await _get_tool_fn(mcp_server, "gcp_write")
        result = await fn(
            command=command,
            reason="Testing destructive rejection in gcp_write",
        )
        parsed = _parse_result(result)

        assert parsed["success"] is False
        assert "HITL SAFETY GATE" in parsed["message"]
        assert "gcp_destructive" in parsed["message"]


# ==========================================
# gcp_write — HAPPY PATH (mocked)
# ==========================================


class TestGcpWriteHappyPath:
    """gcp_write should execute valid write commands with reason."""

    @pytest.mark.asyncio
    @patch("src.tools.gcp_cli.run_gcp_command", new_callable=AsyncMock)
    async def test_accepts_write_verbs(self, mock_run: AsyncMock, mcp_server: FastMCP):
        mock_run.return_value = {
            "stdout": '{"name": "my-sa"}',
            "stderr": "",
            "parsed": {"name": "my-sa"},
        }

        fn = await _get_tool_fn(mcp_server, "gcp_write")
        result = await fn(
            command="gcloud iam service-accounts create my-sa --display-name=My SA",
            reason="Creating service account for CI/CD pipeline",
        )
        parsed = _parse_result(result)

        assert parsed["success"] is True
        assert parsed["data"]["reason"] == "Creating service account for CI/CD pipeline"
        mock_run.assert_awaited_once()


# ==========================================
# gcp_destructive — REJECTION TESTS
# ==========================================


class TestGcpDestructiveRejectsNonDestructiveVerbs:
    """gcp_destructive must reject commands that are NOT destructive."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "command",
        [
            "gcloud run services list",
            "gcloud compute instances describe my-vm",
            "gcloud run deploy my-service --image=gcr.io/proj/img",
            "gcloud iam service-accounts create my-sa",
            "bq ls",
        ],
    )
    async def test_rejects_non_destructive_verbs(self, mcp_server: FastMCP, command: str):
        fn = await _get_tool_fn(mcp_server, "gcp_destructive")
        result = await fn(
            command=command,
            reason="Testing non-destructive rejection in gcp_destructive",
        )
        parsed = _parse_result(result)

        assert parsed["success"] is False
        assert "POLICY GATE" in parsed["message"]
        assert "gcp_write or gcp_read" in parsed["message"]


# ==========================================
# gcp_destructive — HAPPY PATH (mocked)
# ==========================================


class TestGcpDestructiveHappyPath:
    """gcp_destructive should execute valid destructive commands."""

    @pytest.mark.asyncio
    @patch("src.tools.gcp_cli.run_gcp_command", new_callable=AsyncMock)
    async def test_executes_delete_command(
        self, mock_run: AsyncMock, mcp_server: FastMCP
    ):
        mock_run.return_value = {
            "stdout": "{}",
            "stderr": "",
            "parsed": {},
        }

        fn = await _get_tool_fn(mcp_server, "gcp_destructive")
        result = await fn(
            command="gcloud projects delete my-test-project",
            reason="Cleaning up test project after integration run",
        )
        parsed = _parse_result(result)

        assert parsed["success"] is True
        assert parsed["data"]["reason"] == "Cleaning up test project after integration run"
        mock_run.assert_awaited_once()


# ==========================================
# gcp_destructive — DESCRIPTION TEST
# ==========================================


class TestGcpDestructiveDescription:
    """gcp_destructive description must contain ⚠️ DESTRUCTIVE."""

    @pytest.mark.asyncio
    async def test_has_destructive_marker(self, mcp_server: FastMCP):
        tool = await _get_tool(mcp_server, "gcp_destructive")
        assert "DESTRUCTIVE" in tool.description


# ==========================================
# REASON VALIDATION
# ==========================================


class TestReasonValidation:
    """gcp_write and gcp_destructive must reject short reasons."""

    @pytest.mark.asyncio
    async def test_gcp_write_rejects_short_reason(self, mcp_server: FastMCP):
        fn = await _get_tool_fn(mcp_server, "gcp_write")
        result = await fn(
            command="gcloud iam service-accounts create my-sa",
            reason="short",
        )
        parsed = _parse_result(result)

        assert parsed["success"] is False
        assert "AUDIT GATE" in parsed["message"]

    @pytest.mark.asyncio
    async def test_gcp_destructive_rejects_short_reason(self, mcp_server: FastMCP):
        fn = await _get_tool_fn(mcp_server, "gcp_destructive")
        result = await fn(
            command="gcloud projects delete my-project",
            reason="short",
        )
        parsed = _parse_result(result)

        assert parsed["success"] is False
        assert "AUDIT GATE" in parsed["message"]

    @pytest.mark.asyncio
    async def test_gcp_write_accepts_long_reason(self, mcp_server: FastMCP):
        fn = await _get_tool_fn(mcp_server, "gcp_write")
        # This will fail at sanitize_command/run_gcp_command level,
        # but the reason check should pass
        result = await fn(
            command="gcloud iam service-accounts create my-sa",
            reason="Creating service account for the new CI/CD pipeline",
        )
        parsed = _parse_result(result)
        # It may fail at execution, but NOT at reason validation
        assert "AUDIT GATE" not in parsed.get("message", "")
