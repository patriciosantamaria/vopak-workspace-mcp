"""branded.py — Branded content creation + health check tools.

Stubs for:
  1. create_vopak_presentation — branded Vopak Google Slides
  2. create_vopak_document     — branded Google Doc from Markdown
  3. docker_health_check       — environment / credential health report

Full template engines will be ported in a follow-up phase.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any, Optional

from fastmcp import FastMCP

from src.shared.common import (
    get_scoped_auth,
    create_docs_service,
    create_drive_service,
    create_slides_service,
    retry_with_backoff,
    safe_execute,
)

logger = logging.getLogger(__name__)

# ==========================================
# SCOPES
# ==========================================

SLIDES_SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
]
DOCS_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]
DRIVE_SCOPES_RO = [
    "https://www.googleapis.com/auth/drive.readonly",
]


# ==========================================
# INTERNAL HELPERS
# ==========================================


async def _run_subprocess(cmd: list[str]) -> tuple[int, str, str]:
    """Run a subprocess command, returning (returncode, stdout, stderr)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=15.0
        )
        return (
            proc.returncode or 0,
            (stdout_bytes or b"").decode("utf-8", errors="replace").strip(),
            (stderr_bytes or b"").decode("utf-8", errors="replace").strip(),
        )
    except FileNotFoundError:
        return (127, "", f"Command not found: {cmd[0]}")
    except asyncio.TimeoutError:
        return (1, "", f"Command timed out after 15s: {' '.join(cmd)}")


# ==========================================
# TOOL REGISTRATION
# ==========================================


def register_tools(mcp: FastMCP) -> None:
    """Register the 3 branded content + health check tools."""

    # ------------------------------------------------------------------
    # Tool 1: create_vopak_presentation (STUB)
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("create_vopak_presentation")
    async def create_vopak_presentation(
        title: str,
        slides_spec: list[dict],
    ) -> dict:
        """Create a branded Vopak presentation.

        Currently a stub that creates a blank presentation with the given title.
        The full branded template engine (layout mapping, placeholder inheritance,
        Safe Zone validation) will be ported in a follow-up phase.
        """
        # TODO: Port the full VopakSlideGenerator (v6.0.0) from TypeScript.
        #   - Clone the Vopak 2025 template (VOPAK_2025_CONFIG.template_id)
        #   - Resolve master layout mapping
        #   - Pass 1: Create slides with layout assignment
        #   - Pass 2: Inject content into native placeholders
        #   - Cleanup original template slides
        #   Currently creates a blank presentation as a functional stub.

        creds = get_scoped_auth(SLIDES_SCOPES)
        slides_service = create_slides_service(creds)

        # Create a blank presentation
        presentation = await retry_with_backoff(
            lambda: slides_service.presentations()
            .create(body={"title": title})
            .execute()
        )
        presentation_id = presentation["presentationId"]

        return {
            "presentationId": presentation_id,
            "url": f"https://docs.google.com/presentation/d/{presentation_id}/edit",
            "slideCount": len(slides_spec),
            "stub": True,
            "message": (
                f"Created presentation '{title}' (stub mode). "
                f"{len(slides_spec)} slides were specified but the full "
                "branded template engine is not yet ported."
            ),
        }

    # ------------------------------------------------------------------
    # Tool 2: create_vopak_document (STUB)
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("create_vopak_document")
    async def create_vopak_document(
        title: str,
        markdown_content: str,
        folder_id: Optional[str] = None,
    ) -> dict:
        """Create a branded Google Doc from Markdown content.

        Currently a stub that creates a plain Google Doc and inserts the
        Markdown as unformatted text. The full pipeline (Markdown → HTML →
        inline CSS → branded Google Doc) will be ported in a follow-up phase.
        """
        # TODO: Port the full Markdown → branded Google Doc pipeline:
        #   - Convert Markdown → HTML via a Python Markdown library
        #   - Apply Vopak brand CSS (Deep Blue headings, branded tables)
        #   - Inline CSS for Google Docs compatibility (juice equivalent)
        #   - Optional: prepend 3-page corporate front-matter (Cover, Admin, Revision)
        #   - Upload as HTML with import conversion
        #   - Set A4 portrait page size
        #   Currently creates a plain text Doc as a functional stub.

        creds = get_scoped_auth(DOCS_SCOPES)
        docs_service = create_docs_service(creds)
        drive_service = create_drive_service(creds)

        # Create a blank Google Doc
        doc = await retry_with_backoff(
            lambda: docs_service.documents()
            .create(body={"title": title})
            .execute()
        )
        document_id = doc["documentId"]

        # Move to target folder if specified
        if folder_id:
            await retry_with_backoff(
                lambda: drive_service.files()
                .update(
                    fileId=document_id,
                    addParents=folder_id,
                    removeParents="root",
                    fields="id,parents",
                )
                .execute()
            )

        # Insert the markdown content as plain text
        if markdown_content.strip():
            await retry_with_backoff(
                lambda: docs_service.documents()
                .batchUpdate(
                    documentId=document_id,
                    body={
                        "requests": [
                            {
                                "insertText": {
                                    "location": {"index": 1},
                                    "text": markdown_content,
                                }
                            }
                        ]
                    },
                )
                .execute()
            )

        return {
            "documentId": document_id,
            "url": f"https://docs.google.com/document/d/{document_id}/edit",
            "title": title,
            "charCount": len(markdown_content),
            "stub": True,
            "message": (
                f"Created Google Doc '{title}' (stub mode). "
                "Markdown was inserted as plain text. Full branded conversion "
                "(CSS, cover pages, A4 page size) is not yet ported."
            ),
        }

    # ------------------------------------------------------------------
    # Tool 3: docker_health_check
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("docker_health_check")
    async def docker_health_check(
        test_drive: bool = True,
        test_slides: bool = False,
    ) -> dict:
        """Verify container environment health, credential existence, and Google API access.

        Checks:
        - GWS CLI availability
        - gcloud auth status
        - ADC credentials file
        - Google Drive API connectivity (optional)
        - Google Slides API connectivity (optional)

        Read-only — no confirmation required.
        """
        # --- System info ---
        system_info: dict[str, Any] = {
            "platform": sys.platform,
            "arch": platform.machine(),
            "pythonVersion": platform.python_version(),
            "pid": os.getpid(),
        }

        # --- Check GWS CLI availability ---
        gws_binary = os.environ.get("GWS_BINARY_PATH", "gws")
        gws_available = shutil.which(gws_binary) is not None
        gws_check: dict[str, Any] = {
            "binary": gws_binary,
            "available": gws_available,
        }

        if gws_available:
            rc, stdout, stderr = await _run_subprocess([gws_binary, "--version"])
            gws_check["version"] = stdout if rc == 0 else None
            gws_check["error"] = stderr if rc != 0 else None

        # --- Check gcloud auth ---
        gcloud_check: dict[str, Any] = {"available": False}
        gcloud_binary = shutil.which("gcloud")
        if gcloud_binary:
            gcloud_check["available"] = True
            rc, stdout, stderr = await _run_subprocess(
                ["gcloud", "auth", "print-access-token"]
            )
            gcloud_check["authenticated"] = rc == 0
            if rc != 0:
                gcloud_check["error"] = stderr
        else:
            gcloud_check["error"] = "gcloud CLI not found"

        # --- Check ADC credentials ---
        adc_path = os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS",
            str(
                Path.home()
                / ".config"
                / "gcloud"
                / "application_default_credentials.json"
            ),
        )
        adc_exists = os.path.isfile(adc_path)
        adc_size: Optional[int] = None
        if adc_exists:
            adc_size = os.path.getsize(adc_path)

        credentials_info: dict[str, Any] = {
            "adcPath": adc_path,
            "adcExists": adc_exists,
            "adcSize": adc_size,
        }

        # --- Google API connectivity checks ---
        api_access: dict[str, dict[str, Any]] = {}

        if test_drive:
            try:
                creds = get_scoped_auth(DRIVE_SCOPES_RO)
                drive = create_drive_service(creds)
                await retry_with_backoff(
                    lambda: drive.files()
                    .list(pageSize=1, fields="files(id,name)")
                    .execute()
                )
                api_access["drive"] = {
                    "status": "ok",
                    "message": "Successfully listed files",
                }
            except Exception as err:
                api_access["drive"] = {
                    "status": "error",
                    "message": str(err),
                }

        if test_slides:
            try:
                creds = get_scoped_auth(
                    ["https://www.googleapis.com/auth/presentations.readonly"]
                )
                slides = create_slides_service(creds)
                # Attempt to access a known resource (will fail gracefully
                # if template ID is not set)
                await retry_with_backoff(
                    lambda: slides.presentations()
                    .get(presentationId="1")
                    .execute()
                )
                api_access["slides"] = {
                    "status": "ok",
                    "message": "Slides API accessible",
                }
            except Exception as err:
                # A 404 for a fake presentation ID is actually success — it
                # proves the API is reachable and auth works.
                err_msg = str(err)
                if "404" in err_msg or "not found" in err_msg.lower():
                    api_access["slides"] = {
                        "status": "ok",
                        "message": "Slides API accessible (auth verified via 404 probe)",
                    }
                else:
                    api_access["slides"] = {
                        "status": "error",
                        "message": err_msg,
                    }

        has_errors = any(
            v.get("status") == "error" for v in api_access.values()
        )
        status = (
            "unhealthy"
            if not adc_exists
            else ("degraded" if has_errors else "healthy")
        )

        return {
            "status": status,
            "system": system_info,
            "gwsCli": gws_check,
            "gcloudAuth": gcloud_check,
            "credentials": credentials_info,
            "apiAccess": api_access,
        }
