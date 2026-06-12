"""slides.py — Google Slides MCP tools (Python port of slides_bridge.ts).

Ports all 19 Slides tools from the TypeScript vopak-content-bridge.
Uses the Google Slides API v1 and Drive API v3 (for comments).

Read Tools (8):
    slides_get_presentation, slides_get_slide_content, slides_get_speaker_notes,
    slides_get_element_styles, slides_get_comments, slides_search_text,
    slides_measure_text_bounds, slides_audit_deck

Write Tools (8):
    slides_update_text, slides_format_text, slides_update_and_format_text,
    slides_duplicate_slide, slides_reorder_slides, slides_update_speaker_notes,
    slides_bulk_update_speaker_notes, slides_batch_update

Delete Tools (2):
    slides_delete_slide, slides_remove_speaker_notes

Visual QA (1):
    slides_get_thumbnail
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
from typing import Any, Optional

from fastmcp import FastMCP

from src.shared.common import (
    get_scoped_auth,
    create_slides_service,
    create_drive_service,
    retry_with_backoff,
    safe_execute,
)

logger = logging.getLogger(__name__)

# ==========================================
# CONSTANTS
# ==========================================

PT_TO_EMU = 12_700
"""1 typographic point = 12,700 EMU."""

DEFAULT_FONT_SIZE_PT = 10
"""Default font size in PT when not specified in text style."""

AVG_CHAR_WIDTH_RATIO = 0.55
"""Average character width as a fraction of font size (Calibri/Arial approximation)."""

LINE_HEIGHT_MULTIPLIER = 1.35
"""Line height multiplier (1.0 spacing ≈ 1.15× font size in most renderers)."""

PARAGRAPH_SPACING_PT = 4
"""Paragraph spacing (before + after) in PT — approximate for Google Slides default."""

# ==========================================
# SCOPES
# ==========================================

SLIDES_SCOPES_RO = ["https://www.googleapis.com/auth/presentations.readonly"]
SLIDES_SCOPES = ["https://www.googleapis.com/auth/presentations"]
DRIVE_SCOPES_RO = ["https://www.googleapis.com/auth/drive.readonly"]


# ==========================================
# HELPER FUNCTIONS
# ==========================================


def _find_substring_positions(
    text: str, substring: str
) -> list[dict[str, int]]:
    """Find all non-overlapping positions of *substring* in *text*."""
    positions: list[dict[str, int]] = []
    if not substring:
        return positions
    search_from = 0
    while search_from < len(text):
        idx = text.find(substring, search_from)
        if idx == -1:
            break
        positions.append({"startIndex": idx, "endIndex": idx + len(substring)})
        search_from = idx + len(substring)
    return positions


def _escape_regex(s: str) -> str:
    """Escape special regex characters for safe use in ``re.compile``."""
    return re.escape(s)


def _flatten_page_elements(
    elements: list[dict[str, Any]],
    parent_group_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Recursively flatten PageElements, descending into elementGroup children.

    Tracks the parent group ID for each leaf element via a ``_parentGroupId`` key.
    """
    result: list[dict[str, Any]] = []
    for el in elements:
        group = el.get("elementGroup")
        if group and group.get("children"):
            result.extend(
                _flatten_page_elements(group["children"], el.get("objectId"))
            )
        else:
            entry = {**el}
            if parent_group_id:
                entry["_parentGroupId"] = parent_group_id
            result.append(entry)
    return result


def _extract_element_text_deep(element: dict[str, Any]) -> str:
    """Extract text from a single element, including table cells.

    For shapes: reads ``shape.text.textElements``.
    For tables: reads each cell's ``text.textElements``.
    """
    shape = element.get("shape")
    if shape and shape.get("text", {}).get("textElements"):
        return "".join(
            te.get("textRun", {}).get("content", "")
            for te in shape["text"]["textElements"]
            if te.get("textRun")
        )

    table = element.get("table")
    if table and table.get("tableRows"):
        parts: list[str] = []
        for row in table["tableRows"]:
            for cell in row.get("tableCells", []):
                for te in cell.get("text", {}).get("textElements", []):
                    tr = te.get("textRun")
                    if tr:
                        parts.append(tr.get("content", ""))
        return "".join(parts)

    return ""


def _estimate_text_bounds(
    text_elements: list[dict[str, Any]],
    container_width_emu: int,
    container_height_emu: int,
) -> dict[str, Any]:
    """Estimate the rendered text height of a Slides text element.

    Uses font-metric heuristics — not pixel-perfect, but catches overflow
    with ~90% accuracy.
    """
    runs: list[dict[str, Any]] = []
    total_chars = 0
    paragraph_count = 0

    for te in text_elements:
        tr = te.get("textRun")
        if tr and tr.get("content"):
            font_size = (
                tr.get("style", {}).get("fontSize", {}).get("magnitude")
                or DEFAULT_FONT_SIZE_PT
            )
            content = tr["content"]
            runs.append({"text": content, "fontSizePt": font_size})
            total_chars += len(content)
            paragraph_count += content.count("\n")

    if total_chars == 0:
        return {
            "estimatedHeightEmu": 0,
            "containerHeightEmu": container_height_emu,
            "isOverflowing": False,
            "overflowAmountEmu": 0,
            "lineCount": 0,
            "charCount": 0,
        }

    # Estimate line count
    total_lines = 0
    for run in runs:
        char_width_emu = run["fontSizePt"] * PT_TO_EMU * AVG_CHAR_WIDTH_RATIO
        chars_per_line = max(1, math.floor(container_width_emu / char_width_emu))
        segments = run["text"].split("\n")
        for seg in segments:
            if len(seg) == 0:
                total_lines += 1  # empty line from newline
            else:
                total_lines += math.ceil(len(seg) / chars_per_line)
        # Subtract 1 for the trailing newline the Slides API always appends
        if run["text"].endswith("\n"):
            total_lines -= 1

    # Average font size across runs (weighted by char count)
    weighted_font_sum = sum(r["fontSizePt"] * len(r["text"]) for r in runs)
    avg_font_size_pt = (
        weighted_font_sum / total_chars if total_chars > 0 else DEFAULT_FONT_SIZE_PT
    )

    # Calculate total height
    line_height_emu = avg_font_size_pt * PT_TO_EMU * LINE_HEIGHT_MULTIPLIER
    paragraph_spacing_emu = (
        PARAGRAPH_SPACING_PT * PT_TO_EMU * max(0, paragraph_count - 1)
    )
    estimated_height_emu = round(total_lines * line_height_emu + paragraph_spacing_emu)
    overflow_amount_emu = max(0, estimated_height_emu - container_height_emu)

    return {
        "estimatedHeightEmu": estimated_height_emu,
        "containerHeightEmu": container_height_emu,
        "isOverflowing": overflow_amount_emu > 0,
        "overflowAmountEmu": overflow_amount_emu,
        "lineCount": total_lines,
        "charCount": total_chars,
    }


async def _run_sync(fn: Any) -> Any:
    """Run a synchronous Google API call in a thread executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn)


# ==========================================
# TOOL REGISTRATION
# ==========================================


def register_tools(mcp: FastMCP) -> None:
    """Register all 19 Slides tools on the given FastMCP server."""

    # ──────────────────────────────────────
    # READ TOOLS (8)
    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_get_presentation")
    async def slides_get_presentation(presentation_id: str) -> dict:
        """Return presentation metadata: slide count, slide IDs, titles, and page dimensions. Read-only."""
        creds = get_scoped_auth(SLIDES_SCOPES_RO)
        slides = create_slides_service(creds)

        response = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations().get(presentationId=presentation_id).execute()
            )
        )

        slide_data = []
        for index, slide in enumerate(response.get("slides", [])):
            title_text = ""
            for el in _flatten_page_elements(slide.get("pageElements", [])):
                p_type = (
                    el.get("shape", {}).get("placeholder", {}).get("type")
                )
                if p_type in ("TITLE", "CENTERED_TITLE"):
                    title_text = _extract_element_text_deep(el).strip()
                    break
            slide_data.append(
                {
                    "slideIndex": index,
                    "objectId": slide.get("objectId"),
                    "title": title_text or "(no title)",
                }
            )

        return {
            "presentationId": presentation_id,
            "title": response.get("title"),
            "slideCount": len(slide_data),
            "pageSize": response.get("pageSize"),
            "slides": slide_data,
        }

    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_get_slide_content")
    async def slides_get_slide_content(
        presentation_id: str, slide_index: int
    ) -> dict:
        """Return all text elements from a specific slide (by 0-based index): objectId, text, placeholder type, position."""
        creds = get_scoped_auth(SLIDES_SCOPES_RO)
        slides = create_slides_service(creds)

        # Fetch presentation to resolve slide_index → objectId
        pres = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations().get(presentationId=presentation_id).execute()
            )
        )
        all_slides = pres.get("slides", [])
        if slide_index < 0 or slide_index >= len(all_slides):
            raise IndexError(
                f"slide_index {slide_index} out of range "
                f"(presentation has {len(all_slides)} slides)"
            )
        slide_object_id = all_slides[slide_index]["objectId"]

        response = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations()
                .pages()
                .get(
                    presentationId=presentation_id,
                    pageObjectId=slide_object_id,
                )
                .execute()
            )
        )

        flat_elements = _flatten_page_elements(response.get("pageElements", []))
        elements = []
        for el in flat_elements:
            text = _extract_element_text_deep(el).strip()
            p_type = el.get("shape", {}).get("placeholder", {}).get("type")
            if text or p_type:
                element_type = (
                    "shape"
                    if el.get("shape")
                    else "table"
                    if el.get("table")
                    else "image"
                    if el.get("image")
                    else "other"
                )
                elements.append(
                    {
                        "objectId": el.get("objectId"),
                        "placeholderType": p_type or None,
                        "placeholderIndex": el.get("shape", {})
                        .get("placeholder", {})
                        .get("index"),
                        "text": text,
                        "elementType": element_type,
                        "parentGroupId": el.get("_parentGroupId"),
                        "size": el.get("size"),
                        "transform": el.get("transform"),
                    }
                )

        return {
            "slideObjectId": slide_object_id,
            "elementCount": len(elements),
            "elements": elements,
        }

    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_get_speaker_notes")
    async def slides_get_speaker_notes(
        presentation_id: str, slide_index: Optional[int] = None
    ) -> dict:
        """Read speaker notes from one or all slides. Returns notes text for each slide along with element IDs."""
        creds = get_scoped_auth(SLIDES_SCOPES_RO)
        slides = create_slides_service(creds)

        pres = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations().get(presentationId=presentation_id).execute()
            )
        )
        all_slides = pres.get("slides", [])

        if slide_index is not None:
            if slide_index < 0 or slide_index >= len(all_slides):
                raise IndexError(
                    f"slide_index {slide_index} out of range "
                    f"(presentation has {len(all_slides)} slides)"
                )
            target_slides = [(slide_index, all_slides[slide_index])]
        else:
            target_slides = list(enumerate(all_slides))

        results = []
        for idx, slide in target_slides:
            notes_page = slide.get("slideProperties", {}).get("notesPage")
            notes_text = ""
            notes_element_id: Optional[str] = None
            for el in (notes_page or {}).get("pageElements", []):
                shape = el.get("shape", {})
                if (
                    shape.get("placeholder", {}).get("type") == "BODY"
                    and shape.get("text", {}).get("textElements")
                ):
                    notes_element_id = el.get("objectId")
                    notes_text = "".join(
                        te.get("textRun", {}).get("content", "")
                        for te in shape["text"]["textElements"]
                        if te.get("textRun")
                    )
                    break
            results.append(
                {
                    "slideIndex": idx,
                    "slideObjectId": slide.get("objectId", ""),
                    "notesElementId": notes_element_id,
                    "notesText": notes_text.strip(),
                    "charCount": len(notes_text.strip()),
                }
            )

        return {
            "presentationId": presentation_id,
            "slideCount": len(results),
            "slidesWithNotes": sum(1 for r in results if r["charCount"] > 0),
            "slides": results,
        }

    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_get_element_styles")
    async def slides_get_element_styles(
        presentation_id: str, slide_index: int
    ) -> dict:
        """Return detailed text styling for all elements on a slide: per-run font, bold, italic, color, links.

        Essential for replicating existing formatting when updating text.
        Searches recursively inside element groups."""
        creds = get_scoped_auth(SLIDES_SCOPES_RO)
        slides = create_slides_service(creds)

        pres = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations().get(presentationId=presentation_id).execute()
            )
        )
        all_slides = pres.get("slides", [])
        if slide_index < 0 or slide_index >= len(all_slides):
            raise IndexError(
                f"slide_index {slide_index} out of range "
                f"(presentation has {len(all_slides)} slides)"
            )
        slide = all_slides[slide_index]

        elements_result = []
        for el in _flatten_page_elements(slide.get("pageElements", [])):
            text_elements = el.get("shape", {}).get("text", {}).get("textElements", [])
            if not text_elements:
                continue

            text_runs = []
            for te in text_elements:
                tr = te.get("textRun")
                if not tr:
                    continue
                style = tr.get("style", {})
                text_runs.append(
                    {
                        "startIndex": te.get("startIndex", 0),
                        "endIndex": te.get("endIndex", 0),
                        "content": tr.get("content", ""),
                        "style": {
                            "fontFamily": style.get("fontFamily"),
                            "fontSize": style.get("fontSize", {}).get("magnitude"),
                            "bold": style.get("bold", False),
                            "italic": style.get("italic", False),
                            "underline": style.get("underline", False),
                            "foregroundColor": style.get("foregroundColor", {})
                            .get("opaqueColor", {})
                            .get("rgbColor"),
                            "backgroundColor": style.get("backgroundColor", {})
                            .get("opaqueColor", {})
                            .get("rgbColor"),
                            "link": style.get("link", {}).get("url"),
                        },
                    }
                )

            paragraphs = []
            for te in text_elements:
                pm = te.get("paragraphMarker")
                if not pm:
                    continue
                pm_style = pm.get("style", {})
                paragraphs.append(
                    {
                        "startIndex": te.get("startIndex", 0),
                        "endIndex": te.get("endIndex", 0),
                        "alignment": pm_style.get("alignment"),
                        "lineSpacing": pm_style.get("lineSpacing"),
                        "spaceAbove": (pm_style.get("spaceAbove") or {}).get("magnitude"),
                        "spaceBelow": (pm_style.get("spaceBelow") or {}).get("magnitude"),
                        "bulletPreset": (pm.get("bullet") or {}).get("listId"),
                    }
                )

            shape = el.get("shape", {})
            shape_props = shape.get("shapeProperties", {})
            bg_fill = (
                shape_props.get("shapeBackgroundFill", {})
                .get("solidFill", {})
                .get("color", {})
                .get("rgbColor")
            )

            elements_result.append(
                {
                    "elementObjectId": el.get("objectId"),
                    "slideIndex": slide_index,
                    "fullText": "".join(r["content"] for r in text_runs),
                    "textRunCount": len(text_runs),
                    "textRuns": text_runs,
                    "paragraphs": paragraphs,
                    "shapeProperties": {
                        "shapeType": shape.get("shapeType"),
                        "placeholderType": shape.get("placeholder", {}).get("type"),
                        "size": el.get("size"),
                        "transform": el.get("transform"),
                        "backgroundFill": bg_fill,
                    },
                }
            )

        return {
            "slideIndex": slide_index,
            "elementCount": len(elements_result),
            "elements": elements_result,
        }

    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_get_comments")
    async def slides_get_comments(
        file_id: str,
        include_resolved: bool = True,
        include_replies: bool = True,
    ) -> dict:
        """Retrieve all comments on a Google Slides presentation (or any Drive file).

        Returns structured comment data: author, content, quoted text,
        resolution status, and reply threads. Uses the Drive Comments API."""
        creds = get_scoped_auth(DRIVE_SCOPES_RO)
        drive = create_drive_service(creds)

        response = await retry_with_backoff(
            lambda: _run_sync(
                lambda: drive.comments()
                .list(
                    fileId=file_id,
                    fields=(
                        "comments(id,content,resolved,"
                        "author(displayName),"
                        "quotedFileContent(value),"
                        "createdTime,modifiedTime,"
                        "replies(id,content,author(displayName),createdTime))"
                    ),
                    pageSize=100,
                )
                .execute()
            )
        )

        comments = []
        for c in response.get("comments", []):
            replies = []
            if include_replies:
                for r in c.get("replies", []):
                    replies.append(
                        {
                            "replyId": r.get("id"),
                            "author": (r.get("author") or {}).get(
                                "displayName", "[REDACTED]"
                            ),
                            "content": r.get("content"),
                            "createdTime": r.get("createdTime"),
                        }
                    )
            comment = {
                "commentId": c.get("id"),
                "author": (c.get("author") or {}).get("displayName", "[REDACTED]"),
                "content": c.get("content"),
                "resolved": c.get("resolved", False),
                "quotedText": (c.get("quotedFileContent") or {}).get("value"),
                "createdTime": c.get("createdTime"),
                "modifiedTime": c.get("modifiedTime"),
                "replies": replies,
            }
            comments.append(comment)

        if not include_resolved:
            comments = [c for c in comments if not c["resolved"]]

        return {
            "fileId": file_id,
            "totalComments": len(comments),
            "openComments": sum(1 for c in comments if not c["resolved"]),
            "resolvedComments": sum(1 for c in comments if c["resolved"]),
            "comments": comments,
        }

    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_search_text")
    async def slides_search_text(
        presentation_id: str,
        query: str,
        case_sensitive: bool = False,
    ) -> dict:
        """Search for text across an entire presentation. Returns all matches with slide index,
        element ID, matched text, and surrounding context. Searches recursively inside
        element groups and table cells. Supports plain text matching."""
        creds = get_scoped_auth(SLIDES_SCOPES_RO)
        slides = create_slides_service(creds)

        pres = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations().get(presentationId=presentation_id).execute()
            )
        )

        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(_escape_regex(query), flags)
        except re.error as e:
            raise ValueError(f"Invalid search pattern: {e}")

        matches: list[dict[str, Any]] = []
        for slide_index, slide in enumerate(pres.get("slides", [])):
            flat_elements = _flatten_page_elements(slide.get("pageElements", []))
            for el in flat_elements:
                text = _extract_element_text_deep(el)
                if not text:
                    continue
                for m in pattern.finditer(text):
                    ctx_start = max(0, m.start() - 40)
                    ctx_end = min(len(text), m.end() + 40)
                    context = (
                        ("..." if ctx_start > 0 else "")
                        + text[ctx_start:ctx_end].strip()
                        + ("..." if ctx_end < len(text) else "")
                    )
                    element_type = (
                        "shape"
                        if el.get("shape")
                        else "table"
                        if el.get("table")
                        else "other"
                    )
                    matches.append(
                        {
                            "slideIndex": slide_index,
                            "slideObjectId": slide.get("objectId", ""),
                            "elementObjectId": el.get("objectId", ""),
                            "elementType": element_type,
                            "matchedText": m.group(0),
                            "context": context,
                            "startOffset": m.start(),
                        }
                    )

        return {
            "presentationId": presentation_id,
            "query": query,
            "totalMatches": len(matches),
            "slidesWithMatches": len({m["slideIndex"] for m in matches}),
            "matches": matches,
        }

    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_measure_text_bounds")
    async def slides_measure_text_bounds(
        presentation_id: str,
        slide_index: int,
        element_id: str,
    ) -> dict:
        """Estimate rendered text height vs container size for overflow detection.

        Uses font-metric heuristics (~90% accuracy). Returns isOverflowing boolean
        and overflow amount in EMU. Much faster than thumbnail-based visual inspection."""
        creds = get_scoped_auth(SLIDES_SCOPES_RO)
        slides = create_slides_service(creds)

        pres = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations().get(presentationId=presentation_id).execute()
            )
        )
        all_slides = pres.get("slides", [])
        if slide_index < 0 or slide_index >= len(all_slides):
            raise IndexError(
                f"slide_index {slide_index} out of range "
                f"(presentation has {len(all_slides)} slides)"
            )

        target_element = None
        for el in _flatten_page_elements(
            all_slides[slide_index].get("pageElements", [])
        ):
            if el.get("objectId") == element_id:
                target_element = el
                break

        if not target_element:
            raise ValueError(f"Element {element_id} not found on slide {slide_index}")

        text_elements = (
            target_element.get("shape", {}).get("text", {}).get("textElements", [])
        )

        size_width = target_element.get("size", {}).get("width", {}).get("magnitude", 0)
        size_height = target_element.get("size", {}).get("height", {}).get("magnitude", 0)
        scale_x = target_element.get("transform", {}).get("scaleX", 1)
        scale_y = target_element.get("transform", {}).get("scaleY", 1)
        container_width_emu = round(size_width * abs(scale_x))
        container_height_emu = round(size_height * abs(scale_y))

        bounds = _estimate_text_bounds(
            text_elements, container_width_emu, container_height_emu
        )

        return {
            "elementObjectId": element_id,
            "containerWidth": container_width_emu,
            "containerHeight": container_height_emu,
            **bounds,
        }

    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_audit_deck")
    async def slides_audit_deck(
        presentation_id: str,
        slide_indices: Optional[list[int]] = None,
        include_thumbnails: bool = True,
        check_overflow: bool = True,
        full_text: bool = False,
    ) -> dict:
        """Batch audit: for each specified slide, return title, body text, char count,
        element positions, text overflow status, and optionally a thumbnail URL — all in one call.
        Eliminates N × get_slide_content + N × get_thumbnail calls."""
        creds = get_scoped_auth(SLIDES_SCOPES_RO)
        slides = create_slides_service(creds)

        pres = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations().get(presentationId=presentation_id).execute()
            )
        )
        all_slides = pres.get("slides", [])
        indices = slide_indices if slide_indices is not None else list(range(len(all_slides)))

        audit_results = []
        for idx in indices:
            if idx < 0 or idx >= len(all_slides):
                continue
            slide = all_slides[idx]

            title_text = ""
            body_char_count = 0
            elements = []
            overflow_warnings: list[str] = []

            for el in _flatten_page_elements(slide.get("pageElements", [])):
                text = _extract_element_text_deep(el).strip()
                p_type = el.get("shape", {}).get("placeholder", {}).get("type")
                if p_type in ("TITLE", "CENTERED_TITLE"):
                    title_text = text
                if text:
                    body_char_count += len(text)

                # Overflow check
                overflow_info = None
                if (
                    check_overflow
                    and el.get("shape", {}).get("text", {}).get("textElements")
                ):
                    size_w = el.get("size", {}).get("width", {}).get("magnitude", 0)
                    size_h = el.get("size", {}).get("height", {}).get("magnitude", 0)
                    sc_x = el.get("transform", {}).get("scaleX", 1)
                    sc_y = el.get("transform", {}).get("scaleY", 1)
                    c_w = round(size_w * abs(sc_x))
                    c_h = round(size_h * abs(sc_y))
                    if c_w > 0 and c_h > 0:
                        bounds = _estimate_text_bounds(
                            el["shape"]["text"]["textElements"], c_w, c_h
                        )
                        if bounds["isOverflowing"]:
                            overflow_info = {
                                "isOverflowing": True,
                                "overflowEmu": bounds["overflowAmountEmu"],
                                "charCount": bounds["charCount"],
                            }
                            overflow_warnings.append(
                                f"Element {el.get('objectId')} overflows by "
                                f"~{round(bounds['overflowAmountEmu'] / PT_TO_EMU)}pt "
                                f"({bounds['charCount']} chars)"
                            )

                display_text = (
                    text
                    if full_text
                    else (text[:100] + "..." if len(text) > 100 else text)
                )
                elements.append(
                    {
                        "objectId": el.get("objectId"),
                        "placeholderType": p_type or None,
                        "text": display_text,
                        "charCount": len(text),
                        "overflow": overflow_info,
                    }
                )

            # Thumbnail
            thumbnail_url = None
            slide_oid = slide.get("objectId")
            if include_thumbnails and slide_oid:
                try:
                    thumb_resp = await retry_with_backoff(
                        lambda _oid=slide_oid: _run_sync(
                            lambda: slides.presentations()
                            .pages()
                            .getThumbnail(
                                presentationId=presentation_id,
                                pageObjectId=_oid,
                                **{"thumbnailProperties.thumbnailSize": "LARGE"},
                            )
                            .execute()
                        )
                    )
                    thumbnail_url = thumb_resp.get("contentUrl")
                except Exception:
                    thumbnail_url = "(failed to generate)"

            audit_results.append(
                {
                    "index": idx,
                    "objectId": slide_oid,
                    "title": title_text or "(no title)",
                    "totalCharCount": body_char_count,
                    "elementCount": len(elements),
                    "elements": elements,
                    "overflowWarnings": overflow_warnings,
                    "thumbnailUrl": thumbnail_url,
                }
            )

        return {
            "presentationId": presentation_id,
            "title": pres.get("title"),
            "slidesAudited": len(audit_results),
            "totalSlides": len(all_slides),
            "slides": audit_results,
        }

    # ──────────────────────────────────────
    # WRITE TOOLS (8)
    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_update_text")
    async def slides_update_text(
        presentation_id: str, element_id: str, text: str
    ) -> dict:
        """Replace all text in a specific element (shape/text box) by objectId. Deletes existing then inserts new."""
        creds = get_scoped_auth(SLIDES_SCOPES)
        slides = create_slides_service(creds)

        await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations()
                .batchUpdate(
                    presentationId=presentation_id,
                    body={
                        "requests": [
                            {
                                "deleteText": {
                                    "objectId": element_id,
                                    "textRange": {"type": "ALL"},
                                }
                            },
                            {
                                "insertText": {
                                    "objectId": element_id,
                                    "text": text,
                                    "insertionIndex": 0,
                                }
                            },
                        ]
                    },
                )
                .execute()
            )
        )

        return {
            "elementObjectId": element_id,
            "textLength": len(text),
            "message": f"Updated text ({len(text)} chars)",
        }

    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_format_text")
    async def slides_format_text(
        presentation_id: str,
        element_id: str,
        bold: Optional[bool] = None,
        italic: Optional[bool] = None,
        font_size: Optional[int] = None,
        font_color_hex: Optional[str] = None,
        font_family: Optional[str] = None,
    ) -> dict:
        """Apply text formatting to ALL text in an element. Use slides_update_and_format_text
        for substring-level formatting."""
        creds = get_scoped_auth(SLIDES_SCOPES)
        slides = create_slides_service(creds)

        style: dict[str, Any] = {}
        fields: list[str] = []

        if bold is not None:
            style["bold"] = bold
            fields.append("bold")
        if italic is not None:
            style["italic"] = italic
            fields.append("italic")
        if font_size is not None:
            style["fontSize"] = {"magnitude": font_size, "unit": "PT"}
            fields.append("fontSize")
        if font_color_hex is not None:
            hex_clean = font_color_hex.lstrip("#")
            r = int(hex_clean[0:2], 16) / 255.0
            g = int(hex_clean[2:4], 16) / 255.0
            b = int(hex_clean[4:6], 16) / 255.0
            style["foregroundColor"] = {
                "opaqueColor": {"rgbColor": {"red": r, "green": g, "blue": b}}
            }
            fields.append("foregroundColor")
        if font_family is not None:
            style["fontFamily"] = font_family
            fields.append("fontFamily")

        if not fields:
            return {"formatsApplied": 0, "message": "No formatting specified"}

        requests = [
            {
                "updateTextStyle": {
                    "objectId": element_id,
                    "textRange": {"type": "ALL"},
                    "style": style,
                    "fields": ",".join(fields),
                }
            }
        ]

        await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations()
                .batchUpdate(
                    presentationId=presentation_id,
                    body={"requests": requests},
                )
                .execute()
            )
        )

        return {
            "elementObjectId": element_id,
            "formatsApplied": len(fields),
            "message": f"Applied formatting: {', '.join(fields)}",
        }

    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_update_and_format_text")
    async def slides_update_and_format_text(
        presentation_id: str,
        element_id: str,
        text: str,
        bold: Optional[bool] = None,
        italic: Optional[bool] = None,
        font_size: Optional[int] = None,
        font_color_hex: Optional[str] = None,
        font_family: Optional[str] = None,
    ) -> dict:
        """Atomic combo: replace text AND apply formatting in a single API call.

        Eliminates the 2-call pattern (update_text + format_text). Text replacement
        strips ALL formatting, so this tool re-applies formatting after the text
        update in one API round-trip."""
        creds = get_scoped_auth(SLIDES_SCOPES)
        slides = create_slides_service(creds)

        # Phase 1: Delete + Insert (replaces text)
        requests: list[dict[str, Any]] = [
            {
                "deleteText": {
                    "objectId": element_id,
                    "textRange": {"type": "ALL"},
                }
            },
            {
                "insertText": {
                    "objectId": element_id,
                    "text": text,
                    "insertionIndex": 0,
                }
            },
        ]

        # Phase 2: Apply formatting on the NEW text
        style: dict[str, Any] = {}
        fields: list[str] = []

        if bold is not None:
            style["bold"] = bold
            fields.append("bold")
        if italic is not None:
            style["italic"] = italic
            fields.append("italic")
        if font_size is not None:
            style["fontSize"] = {"magnitude": font_size, "unit": "PT"}
            fields.append("fontSize")
        if font_color_hex is not None:
            hex_clean = font_color_hex.lstrip("#")
            r = int(hex_clean[0:2], 16) / 255.0
            g = int(hex_clean[2:4], 16) / 255.0
            b = int(hex_clean[4:6], 16) / 255.0
            style["foregroundColor"] = {
                "opaqueColor": {"rgbColor": {"red": r, "green": g, "blue": b}}
            }
            fields.append("foregroundColor")
        if font_family is not None:
            style["fontFamily"] = font_family
            fields.append("fontFamily")

        if fields:
            requests.append(
                {
                    "updateTextStyle": {
                        "objectId": element_id,
                        "textRange": {"type": "ALL"},
                        "style": style,
                        "fields": ",".join(fields),
                    }
                }
            )

        formats_applied = len(fields)

        await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations()
                .batchUpdate(
                    presentationId=presentation_id,
                    body={"requests": requests},
                )
                .execute()
            )
        )

        return {
            "elementObjectId": element_id,
            "textLength": len(text),
            "formatsApplied": formats_applied,
            "message": (
                f"Updated text ({len(text)} chars) + "
                f"applied {formats_applied} format operations"
            ),
        }

    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_duplicate_slide")
    async def slides_duplicate_slide(
        presentation_id: str,
        slide_index: int,
        insert_at: Optional[int] = None,
    ) -> dict:
        """Duplicate a slide by index. Returns the new slide ID and all new element details
        for immediate use without re-fetching."""
        creds = get_scoped_auth(SLIDES_SCOPES)
        slides = create_slides_service(creds)

        # Resolve slide_index → objectId
        pres = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations().get(presentationId=presentation_id).execute()
            )
        )
        all_slides = pres.get("slides", [])
        if slide_index < 0 or slide_index >= len(all_slides):
            raise IndexError(
                f"slide_index {slide_index} out of range "
                f"(presentation has {len(all_slides)} slides)"
            )
        slide_object_id = all_slides[slide_index]["objectId"]

        # Duplicate
        dup_response = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations()
                .batchUpdate(
                    presentationId=presentation_id,
                    body={
                        "requests": [
                            {"duplicateObject": {"objectId": slide_object_id}}
                        ]
                    },
                )
                .execute()
            )
        )

        replies = dup_response.get("replies", [])
        new_slide_id = (replies[0] if replies else {}).get("duplicateObject", {}).get(
            "objectId"
        )
        if not new_slide_id:
            raise RuntimeError("Duplication failed: no new object ID returned")

        # Reposition if requested
        if insert_at is not None:
            await retry_with_backoff(
                lambda: _run_sync(
                    lambda: slides.presentations()
                    .batchUpdate(
                        presentationId=presentation_id,
                        body={
                            "requests": [
                                {
                                    "updateSlidesPosition": {
                                        "slideObjectIds": [new_slide_id],
                                        "insertionIndex": insert_at,
                                    }
                                }
                            ]
                        },
                    )
                    .execute()
                )
            )

        # Fetch updated presentation to return new element info
        updated = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations().get(presentationId=presentation_id).execute()
            )
        )
        new_slide = None
        for s in updated.get("slides", []):
            if s.get("objectId") == new_slide_id:
                new_slide = s
                break

        new_elements = []
        if new_slide:
            for el in _flatten_page_elements(new_slide.get("pageElements", [])):
                new_elements.append(
                    {
                        "objectId": el.get("objectId", ""),
                        "placeholderType": el.get("shape", {})
                        .get("placeholder", {})
                        .get("type"),
                        "text": _extract_element_text_deep(el).strip(),
                        "parentGroupId": el.get("_parentGroupId"),
                    }
                )

        return {
            "newSlideId": new_slide_id,
            "newElements": new_elements,
            "message": f"Duplicated → {new_slide_id} ({len(new_elements)} elements)",
        }

    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_reorder_slides")
    async def slides_reorder_slides(
        presentation_id: str, slide_id: str, new_index: int
    ) -> dict:
        """Move a single slide to a new position. Handles API ordering constraints internally."""
        creds = get_scoped_auth(SLIDES_SCOPES)
        slides = create_slides_service(creds)

        pres = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations().get(presentationId=presentation_id).execute()
            )
        )
        all_slides = pres.get("slides", [])
        slide_count = len(all_slides)

        if new_index >= slide_count:
            raise IndexError(
                f"Target {new_index} out of bounds ({slide_count} slides)"
            )
        if not any(s.get("objectId") == slide_id for s in all_slides):
            raise ValueError(f"Slide {slide_id} not found")

        await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations()
                .batchUpdate(
                    presentationId=presentation_id,
                    body={
                        "requests": [
                            {
                                "updateSlidesPosition": {
                                    "slideObjectIds": [slide_id],
                                    "insertionIndex": new_index,
                                }
                            }
                        ]
                    },
                )
                .execute()
            )
        )

        return {
            "slideObjectId": slide_id,
            "newPosition": new_index,
            "totalSlides": slide_count,
        }

    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_update_speaker_notes")
    async def slides_update_speaker_notes(
        presentation_id: str, slide_index: int, notes: str
    ) -> dict:
        """Add or replace speaker notes on a specific slide. Automatically finds the notes page
        BODY element, clears existing text, and inserts new text."""
        creds = get_scoped_auth(SLIDES_SCOPES)
        slides = create_slides_service(creds)

        pres = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations().get(presentationId=presentation_id).execute()
            )
        )
        all_slides = pres.get("slides", [])
        if slide_index < 0 or slide_index >= len(all_slides):
            raise IndexError(
                f"slide_index {slide_index} out of range "
                f"(presentation has {len(all_slides)} slides)"
            )
        slide = all_slides[slide_index]
        slide_object_id = slide.get("objectId", "")

        notes_page = slide.get("slideProperties", {}).get("notesPage")
        notes_element = None
        for el in (notes_page or {}).get("pageElements", []):
            if el.get("shape", {}).get("placeholder", {}).get("type") == "BODY":
                notes_element = el
                break

        if not notes_element or not notes_element.get("objectId"):
            raise ValueError(
                f"Notes BODY element not found on slide index {slide_index} ({slide_object_id})"
            )

        notes_oid = notes_element["objectId"]
        existing_text = "".join(
            te.get("textRun", {}).get("content", "")
            for te in notes_element.get("shape", {})
            .get("text", {})
            .get("textElements", [])
            if te.get("textRun")
        )

        requests: list[dict[str, Any]] = []
        if len(existing_text) > 1:
            requests.append(
                {"deleteText": {"objectId": notes_oid, "textRange": {"type": "ALL"}}}
            )
        if notes.strip():
            requests.append(
                {
                    "insertText": {
                        "objectId": notes_oid,
                        "insertionIndex": 0,
                        "text": notes,
                    }
                }
            )

        if requests:
            await retry_with_backoff(
                lambda: _run_sync(
                    lambda: slides.presentations()
                    .batchUpdate(
                        presentationId=presentation_id,
                        body={"requests": requests},
                    )
                    .execute()
                )
            )

        return {
            "slideObjectId": slide_object_id,
            "notesElementId": notes_oid,
            "previousLength": len(existing_text.strip()),
            "newLength": len(notes.strip()),
            "message": f"Speaker notes updated on slide {slide_object_id} ({len(notes.strip())} chars)",
        }

    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_bulk_update_speaker_notes")
    async def slides_bulk_update_speaker_notes(
        presentation_id: str, updates: list[dict]
    ) -> dict:
        """Add or replace speaker notes on multiple slides in a single API call.

        Each dict in *updates* must have ``slide_index`` (int, 0-based) and ``notes`` (str).
        Much more efficient than calling slides_update_speaker_notes in a loop."""
        creds = get_scoped_auth(SLIDES_SCOPES)
        slides = create_slides_service(creds)

        pres = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations().get(presentationId=presentation_id).execute()
            )
        )
        all_slides = pres.get("slides", [])

        requests: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []

        for update in updates:
            s_idx = update.get("slide_index")
            notes_text = update.get("notes", "")
            if s_idx is None:
                raise ValueError("Each update must have a 'slide_index' key")
            if s_idx < 0 or s_idx >= len(all_slides):
                raise IndexError(
                    f"slide_index {s_idx} out of range "
                    f"(presentation has {len(all_slides)} slides)"
                )

            slide = all_slides[s_idx]
            notes_page = slide.get("slideProperties", {}).get("notesPage")
            notes_element = None
            for el in (notes_page or {}).get("pageElements", []):
                if el.get("shape", {}).get("placeholder", {}).get("type") == "BODY":
                    notes_element = el
                    break

            if not notes_element or not notes_element.get("objectId"):
                raise ValueError(
                    f"Notes BODY element not found on slide index {s_idx} "
                    f"({slide.get('objectId')})"
                )

            notes_oid = notes_element["objectId"]
            existing_text = "".join(
                te.get("textRun", {}).get("content", "")
                for te in notes_element.get("shape", {})
                .get("text", {})
                .get("textElements", [])
                if te.get("textRun")
            )

            if len(existing_text) > 1:
                requests.append(
                    {
                        "deleteText": {
                            "objectId": notes_oid,
                            "textRange": {"type": "ALL"},
                        }
                    }
                )
            if notes_text.strip():
                requests.append(
                    {
                        "insertText": {
                            "objectId": notes_oid,
                            "insertionIndex": 0,
                            "text": notes_text,
                        }
                    }
                )

            results.append(
                {
                    "slideIndex": s_idx,
                    "slideObjectId": slide.get("objectId", ""),
                    "notesElementId": notes_oid,
                    "previousLength": len(existing_text.strip()),
                    "newLength": len(notes_text.strip()),
                }
            )

        if requests:
            await retry_with_backoff(
                lambda: _run_sync(
                    lambda: slides.presentations()
                    .batchUpdate(
                        presentationId=presentation_id,
                        body={"requests": requests},
                    )
                    .execute()
                )
            )

        return {
            "presentationId": presentation_id,
            "slidesUpdated": len(results),
            "totalRequests": len(requests),
            "slides": results,
            "message": f"Updated speaker notes on {len(results)} slides in a single batch",
        }

    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_batch_update")
    async def slides_batch_update(
        presentation_id: str, requests: list[dict]
    ) -> dict:
        """Execute raw Slides API batchUpdate requests. Escape hatch for advanced operations."""
        creds = get_scoped_auth(SLIDES_SCOPES)
        slides = create_slides_service(creds)

        response = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations()
                .batchUpdate(
                    presentationId=presentation_id,
                    body={"requests": requests},
                )
                .execute()
            )
        )

        return {
            "requestCount": len(requests),
            "replies": response.get("replies"),
        }

    # ──────────────────────────────────────
    # DELETE TOOLS (2)
    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_delete_slide")
    async def slides_delete_slide(
        presentation_id: str, slide_id: str
    ) -> dict:
        """⚠️ DESTRUCTIVE — Permanently delete a slide from a presentation. Cannot be undone."""
        creds = get_scoped_auth(SLIDES_SCOPES)
        slides = create_slides_service(creds)

        await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations()
                .batchUpdate(
                    presentationId=presentation_id,
                    body={
                        "requests": [
                            {"deleteObject": {"objectId": slide_id}}
                        ]
                    },
                )
                .execute()
            )
        )

        return {
            "deletedSlideId": slide_id,
            "message": f"Permanently deleted slide {slide_id}",
        }

    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_remove_speaker_notes")
    async def slides_remove_speaker_notes(
        presentation_id: str,
        slide_indices: Optional[list[int]] = None,
    ) -> dict:
        """⚠️ DESTRUCTIVE — Permanently delete speaker notes from all or specified slides.

        Used for creating participant-facing decks without instructor notes.
        Returns count of slides cleared. Cannot be undone."""
        creds = get_scoped_auth(SLIDES_SCOPES)
        slides = create_slides_service(creds)

        pres = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations().get(presentationId=presentation_id).execute()
            )
        )
        all_slides = pres.get("slides", [])
        indices = (
            slide_indices if slide_indices is not None else list(range(len(all_slides)))
        )

        requests: list[dict[str, Any]] = []
        cleared_slides: list[dict[str, Any]] = []

        for idx in indices:
            if idx < 0 or idx >= len(all_slides):
                continue
            slide = all_slides[idx]
            notes_page = slide.get("slideProperties", {}).get("notesPage")
            if not notes_page:
                continue

            for el in notes_page.get("pageElements", []):
                shape = el.get("shape", {})
                if (
                    shape.get("placeholder", {}).get("type") == "BODY"
                    and shape.get("text", {}).get("textElements")
                ):
                    note_text = "".join(
                        te.get("textRun", {}).get("content", "")
                        for te in shape["text"]["textElements"]
                        if te.get("textRun")
                    ).strip()
                    if len(note_text) > 0 and el.get("objectId"):
                        requests.append(
                            {
                                "deleteText": {
                                    "objectId": el["objectId"],
                                    "textRange": {"type": "ALL"},
                                }
                            }
                        )
                        cleared_slides.append(
                            {
                                "index": idx,
                                "objectId": slide.get("objectId", ""),
                                "notesChars": len(note_text),
                            }
                        )

        if not requests:
            return {
                "presentationId": presentation_id,
                "slidesCleared": 0,
                "message": "No speaker notes found on the specified slides.",
            }

        await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations()
                .batchUpdate(
                    presentationId=presentation_id,
                    body={"requests": requests},
                )
                .execute()
            )
        )

        total_chars_removed = sum(s["notesChars"] for s in cleared_slides)
        return {
            "presentationId": presentation_id,
            "slidesCleared": len(cleared_slides),
            "totalCharsRemoved": total_chars_removed,
            "slides": cleared_slides,
            "message": (
                f"Cleared speaker notes from {len(cleared_slides)} slide(s), "
                f"removing {total_chars_removed} characters total."
            ),
        }

    # ──────────────────────────────────────
    # VISUAL QA (1)
    # ──────────────────────────────────────

    @mcp.tool()
    @safe_execute("slides_get_thumbnail")
    async def slides_get_thumbnail(
        presentation_id: str,
        slide_index: int = 0,
        thumbnail_size: str = "LARGE",
    ) -> dict:
        """Export a slide as a PNG image URL for visual inspection.

        Uses ``presentations.pages.getThumbnail()`` API. The URL has a ~30-minute TTL.
        Valid thumbnail_size values: SMALL, MEDIUM, LARGE."""
        creds = get_scoped_auth(SLIDES_SCOPES_RO)
        slides = create_slides_service(creds)

        pres = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations().get(presentationId=presentation_id).execute()
            )
        )
        all_slides = pres.get("slides", [])
        if slide_index < 0 or slide_index >= len(all_slides):
            raise IndexError(
                f"slide_index {slide_index} out of range "
                f"(presentation has {len(all_slides)} slides)"
            )

        slide_object_id = all_slides[slide_index]["objectId"]
        valid_sizes = ("SMALL", "MEDIUM", "LARGE")
        if thumbnail_size.upper() not in valid_sizes:
            raise ValueError(
                f"Invalid thumbnail_size '{thumbnail_size}'. Must be one of: {', '.join(valid_sizes)}"
            )

        thumb_resp = await retry_with_backoff(
            lambda: _run_sync(
                lambda: slides.presentations()
                .pages()
                .getThumbnail(
                    presentationId=presentation_id,
                    pageObjectId=slide_object_id,
                    **{"thumbnailProperties.thumbnailSize": thumbnail_size.upper()},
                )
                .execute()
            )
        )

        return {
            "presentationId": presentation_id,
            "slideIndex": slide_index,
            "slideObjectId": slide_object_id,
            "thumbnailUrl": thumb_resp.get("contentUrl"),
            "thumbnailSize": thumbnail_size.upper(),
            "message": f"Thumbnail generated for slide {slide_index} ({thumbnail_size.upper()})",
        }
