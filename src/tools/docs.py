"""docs.py — Google Docs API tools (read, write, destructive).

Port of the 8 Docs tools from slides_bridge.ts (lines 1197-1548).
Provides structured document reading, text manipulation, and formatting
via the Google Docs API v1.

Read tools (3):  docs_get_structure, docs_read_text, docs_search_text
Write tools (4): docs_insert_text, docs_update_style, docs_append_section, docs_find_and_replace
Delete tools (1): docs_delete_text
"""

from __future__ import annotations

import re
from typing import Any, Optional

from fastmcp import FastMCP

from src.shared.common import (
    get_scoped_auth,
    create_docs_service,
    retry_with_backoff,
    safe_execute,
)

# ==========================================
# SCOPES
# ==========================================

DOCS_SCOPES_RO = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
DOCS_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.readonly",
]


# ==========================================
# INTERNAL HELPERS
# ==========================================


def _extract_doc_structure(
    content: list[dict[str, Any]],
) -> dict[str, Any]:
    """Extract headings, table count, and total characters from a Docs body content array.

    Mirrors the TypeScript ``extractDocStructure()`` helper.
    """
    headings: list[dict[str, Any]] = []
    table_count = 0
    total_characters = 0

    for el in content:
        if "paragraph" in el:
            style = (
                el["paragraph"]
                .get("paragraphStyle", {})
                .get("namedStyleType", "")
            )
            heading_match = re.match(r"^HEADING_(\d)$", style)
            text = "".join(
                pe.get("textRun", {}).get("content", "")
                for pe in el["paragraph"].get("elements", [])
            ).strip()
            total_characters = max(total_characters, el.get("endIndex", 0))
            if heading_match:
                headings.append(
                    {
                        "level": int(heading_match.group(1)),
                        "text": text,
                        "startIndex": el.get("startIndex", 0),
                        "endIndex": el.get("endIndex", 0),
                    }
                )
        elif "table" in el:
            table_count += 1
            total_characters = max(total_characters, el.get("endIndex", 0))

    return {
        "headings": headings,
        "tableCount": table_count,
        "totalCharacters": total_characters,
    }


def _find_substring_positions(
    text: str, substring: str
) -> list[dict[str, int]]:
    """Find all non-overlapping positions of *substring* in *text*.

    Mirrors the TypeScript ``findSubstringPositions()`` helper.
    Returns a list of ``{"startIndex": …, "endIndex": …}`` dicts.
    """
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
    """Escape special regex characters so *s* is treated as a literal string."""
    return re.escape(s)


def _extract_full_text(content: list[dict[str, Any]]) -> str:
    """Build the full text of a document from its body content array."""
    full_text = ""
    for block in content:
        if "paragraph" in block:
            for pe in block["paragraph"].get("elements", []):
                full_text += pe.get("textRun", {}).get("content", "")
    return full_text


# ==========================================
# TOOL REGISTRATION
# ==========================================


def register_tools(mcp: FastMCP) -> None:
    """Register all 8 Docs tools on the given FastMCP server."""

    # ------------------------------------------------------------------
    # READ TOOLS (3)
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("docs_get_structure")
    async def docs_get_structure(document_id: str) -> dict:
        """Return document outline: headings (level, text, indices), table count, total characters."""
        creds = get_scoped_auth(DOCS_SCOPES_RO)
        docs = create_docs_service(creds)

        response = await retry_with_backoff(
            lambda: docs.documents().get(documentId=document_id).execute()
        )

        structure = _extract_doc_structure(
            response.get("body", {}).get("content", [])
        )
        return {
            "documentId": document_id,
            "title": response.get("title"),
            **structure,
        }

    @mcp.tool()
    @safe_execute("docs_read_text")
    async def docs_read_text(
        document_id: str,
        start_index: Optional[int] = None,
        end_index: Optional[int] = None,
    ) -> dict:
        """Read the full text content of a Google Doc, or a specific character range.

        Returns the raw text with heading markers. When *start_index* and
        *end_index* are provided, returns only that slice. Otherwise returns
        the full document with per-section metadata.
        """
        creds = get_scoped_auth(DOCS_SCOPES_RO)
        docs = create_docs_service(creds)

        response = await retry_with_backoff(
            lambda: docs.documents().get(documentId=document_id).execute()
        )
        content = response.get("body", {}).get("content", [])

        # --- Build sections + full text ---
        sections: list[dict[str, Any]] = []
        current_section: Optional[dict[str, Any]] = None
        full_text = ""

        for block in content:
            if "paragraph" in block:
                style_type = (
                    block["paragraph"]
                    .get("paragraphStyle", {})
                    .get("namedStyleType", "")
                )
                block_text = "".join(
                    e.get("textRun", {}).get("content", "")
                    for e in block["paragraph"].get("elements", [])
                    if "textRun" in e
                )

                if style_type.startswith("HEADING_"):
                    if current_section is not None:
                        current_section["endIndex"] = block.get(
                            "startIndex", current_section["endIndex"]
                        )
                        sections.append(current_section)
                    current_section = {
                        "heading": block_text.strip(),
                        "level": int(style_type.replace("HEADING_", "")),
                        "startIndex": block.get("startIndex", 0),
                        "endIndex": block.get("endIndex", 0),
                        "text": block_text,
                    }
                elif current_section is not None:
                    current_section["text"] += block_text
                    current_section["endIndex"] = block.get(
                        "endIndex", current_section["endIndex"]
                    )
                full_text += block_text

            elif "table" in block:
                table_text = "".join(
                    e.get("textRun", {}).get("content", "")
                    for row in block["table"].get("tableRows", [])
                    for cell in row.get("tableCells", [])
                    for c in cell.get("content", [])
                    for e in c.get("paragraph", {}).get("elements", [])
                    if "textRun" in e
                )
                if current_section is not None:
                    current_section["text"] += table_text
                    current_section["endIndex"] = block.get(
                        "endIndex", current_section["endIndex"]
                    )
                full_text += table_text

        if current_section is not None:
            sections.append(current_section)

        # --- Range slice ---
        if start_index is not None and end_index is not None:
            sliced = full_text[start_index:end_index]
            return {
                "documentId": document_id,
                "title": response.get("title"),
                "startIndex": start_index,
                "endIndex": end_index,
                "text": sliced,
                "charCount": len(sliced),
            }

        return {
            "documentId": document_id,
            "title": response.get("title"),
            "text": full_text.strip(),
            "charCount": len(full_text.strip()),
            "sectionCount": len(sections),
            "sections": [
                {
                    "heading": s["heading"],
                    "level": s["level"],
                    "charCount": len(s["text"].strip()),
                }
                for s in sections
            ],
        }

    @mcp.tool()
    @safe_execute("docs_search_text")
    async def docs_search_text(
        document_id: str,
        query: str,
        case_sensitive: bool = False,
    ) -> dict:
        """Search for text across a Google Doc.

        Returns all matches with surrounding context. Supports plain text
        matching. Useful for auditing terminology or finding specific content.
        """
        creds = get_scoped_auth(DOCS_SCOPES_RO)
        docs = create_docs_service(creds)

        response = await retry_with_backoff(
            lambda: docs.documents().get(documentId=document_id).execute()
        )
        content = response.get("body", {}).get("content", [])
        full_text = _extract_full_text(content)

        flags = re.IGNORECASE if not case_sensitive else 0
        pattern = re.compile(_escape_regex(query), flags)

        matches: list[dict[str, Any]] = []
        for m in pattern.finditer(full_text):
            ctx_start = max(0, m.start() - 60)
            ctx_end = min(len(full_text), m.end() + 60)
            context = (
                ("..." if ctx_start > 0 else "")
                + full_text[ctx_start:ctx_end].strip()
                + ("..." if ctx_end < len(full_text) else "")
            )
            matches.append(
                {
                    "matchedText": m.group(0),
                    "context": context,
                    "charIndex": m.start(),
                }
            )

        return {
            "documentId": document_id,
            "title": response.get("title"),
            "query": query,
            "totalMatches": len(matches),
            "matches": matches,
        }

    # ------------------------------------------------------------------
    # WRITE TOOLS (4)
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("docs_insert_text")
    async def docs_insert_text(
        document_id: str,
        text: str,
        index: int,
    ) -> dict:
        """Insert text at a specific character index in a Google Doc.

        Use index=1 for start of document. The Docs API uses 1-based indexing.
        """
        creds = get_scoped_auth(DOCS_SCOPES)
        docs = create_docs_service(creds)

        await retry_with_backoff(
            lambda: docs.documents()
            .batchUpdate(
                documentId=document_id,
                body={
                    "requests": [
                        {
                            "insertText": {
                                "location": {"index": index},
                                "text": text,
                            }
                        }
                    ]
                },
            )
            .execute()
        )

        return {
            "insertedAt": index,
            "length": len(text),
            "message": f"Inserted {len(text)} chars at index {index}",
        }

    @mcp.tool()
    @safe_execute("docs_update_style")
    async def docs_update_style(
        document_id: str,
        start_index: int,
        end_index: int,
        bold: Optional[bool] = None,
        italic: Optional[bool] = None,
        font_size: Optional[int] = None,
        font_color_hex: Optional[str] = None,
        font_family: Optional[str] = None,
    ) -> dict:
        """Apply text formatting to a range in a Google Doc.

        Specify *start_index* / *end_index* (1-based, matching Docs API offsets)
        and one or more style properties. Only provided properties are changed.
        """
        creds = get_scoped_auth(DOCS_SCOPES)
        docs = create_docs_service(creds)

        # Build the style dict and fields list for the updateTextStyle request
        text_style: dict[str, Any] = {}
        fields: list[str] = []

        if bold is not None:
            text_style["bold"] = bold
            fields.append("bold")
        if italic is not None:
            text_style["italic"] = italic
            fields.append("italic")
        if font_size is not None:
            text_style["fontSize"] = {
                "magnitude": font_size,
                "unit": "PT",
            }
            fields.append("fontSize")
        if font_family is not None:
            text_style["weightedFontFamily"] = {"fontFamily": font_family}
            fields.append("weightedFontFamily")
        if font_color_hex is not None:
            # Parse hex color → RGB float values (0-1)
            hex_clean = font_color_hex.lstrip("#")
            if len(hex_clean) != 6:
                raise ValueError(
                    f"font_color_hex must be a 6-digit hex string, got '{font_color_hex}'"
                )
            r = int(hex_clean[0:2], 16) / 255.0
            g = int(hex_clean[2:4], 16) / 255.0
            b = int(hex_clean[4:6], 16) / 255.0
            text_style["foregroundColor"] = {
                "color": {"rgbColor": {"red": r, "green": g, "blue": b}}
            }
            fields.append("foregroundColor")

        if not fields:
            return {
                "formatsApplied": 0,
                "message": "No style properties specified — nothing changed",
            }

        await retry_with_backoff(
            lambda: docs.documents()
            .batchUpdate(
                documentId=document_id,
                body={
                    "requests": [
                        {
                            "updateTextStyle": {
                                "range": {
                                    "startIndex": start_index,
                                    "endIndex": end_index,
                                },
                                "textStyle": text_style,
                                "fields": ",".join(fields),
                            }
                        }
                    ]
                },
            )
            .execute()
        )

        return {
            "startIndex": start_index,
            "endIndex": end_index,
            "fieldsUpdated": fields,
            "formatsApplied": 1,
            "message": (
                f"Applied {', '.join(fields)} to range [{start_index}, {end_index})"
            ),
        }

    @mcp.tool()
    @safe_execute("docs_append_section")
    async def docs_append_section(
        document_id: str,
        heading: str,
        body: str,
        heading_level: int = 2,
    ) -> dict:
        """Append a heading + body section to the end of a Google Doc with proper heading style.

        *heading_level* maps to HEADING_1 through HEADING_6 (default 2).
        """
        if not 1 <= heading_level <= 6:
            raise ValueError(
                f"heading_level must be 1-6, got {heading_level}"
            )

        creds = get_scoped_auth(DOCS_SCOPES)
        docs = create_docs_service(creds)

        # Fetch the document to find the end index
        doc_response = await retry_with_backoff(
            lambda: docs.documents().get(documentId=document_id).execute()
        )
        doc_body = doc_response.get("body", {}).get("content", [])
        last_el = doc_body[-1] if doc_body else {}
        end_index = (last_el.get("endIndex", 1)) - 1

        full_text = f"\n{heading}\n{body}\n"
        heading_start = end_index + 1  # +1 for the leading \n
        heading_end = heading_start + len(heading)

        await retry_with_backoff(
            lambda: docs.documents()
            .batchUpdate(
                documentId=document_id,
                body={
                    "requests": [
                        {
                            "insertText": {
                                "location": {"index": end_index},
                                "text": full_text,
                            }
                        },
                        {
                            "updateParagraphStyle": {
                                "range": {
                                    "startIndex": heading_start,
                                    "endIndex": heading_end + 1,
                                },
                                "paragraphStyle": {
                                    "namedStyleType": f"HEADING_{heading_level}"
                                },
                                "fields": "namedStyleType",
                            }
                        },
                    ]
                },
            )
            .execute()
        )

        return {
            "appendedAt": end_index,
            "headingLevel": heading_level,
            "message": f'Appended "{heading}" section',
        }

    @mcp.tool()
    @safe_execute("docs_find_and_replace")
    async def docs_find_and_replace(
        document_id: str,
        find_text: str,
        replace_text: str,
        match_case: bool = False,
    ) -> dict:
        """Find and replace all occurrences of text in a Google Doc.

        Uses the native Docs API ``replaceAllText`` request for efficient
        bulk replacement.
        """
        creds = get_scoped_auth(DOCS_SCOPES)
        docs = create_docs_service(creds)

        response = await retry_with_backoff(
            lambda: docs.documents()
            .batchUpdate(
                documentId=document_id,
                body={
                    "requests": [
                        {
                            "replaceAllText": {
                                "containsText": {
                                    "text": find_text,
                                    "matchCase": match_case,
                                },
                                "replaceText": replace_text,
                            }
                        }
                    ]
                },
            )
            .execute()
        )

        count = (
            response.get("replies", [{}])[0]
            .get("replaceAllText", {})
            .get("occurrencesChanged", 0)
        )
        return {
            "occurrencesChanged": count,
            "message": f'Replaced {count} occurrences of "{find_text}"',
        }

    # ------------------------------------------------------------------
    # DELETE TOOLS (1)
    # ------------------------------------------------------------------

    @mcp.tool()
    @safe_execute("docs_delete_text")
    async def docs_delete_text(
        document_id: str,
        start_index: int,
        end_index: int,
    ) -> dict:
        """⚠️ DESTRUCTIVE: Delete a range of text from a Google Doc by character indices.

        Use docs_read_text or docs_get_structure to find the correct indices
        before deleting. *start_index* is inclusive (1-based), *end_index* is
        exclusive.
        """
        if end_index <= start_index:
            raise ValueError(
                f"end_index ({end_index}) must be greater than start_index ({start_index})"
            )

        creds = get_scoped_auth(DOCS_SCOPES)
        docs = create_docs_service(creds)

        # Read current text at range for the deletion preview
        doc = await retry_with_backoff(
            lambda: docs.documents().get(documentId=document_id).execute()
        )
        deleted_preview = ""
        for block in doc.get("body", {}).get("content", []):
            if "paragraph" in block:
                for el in block["paragraph"].get("elements", []):
                    if "textRun" in el:
                        el_start = el.get("startIndex")
                        el_end = el.get("endIndex")
                        if (
                            el_start is not None
                            and el_end is not None
                        ):
                            overlap_start = max(el_start, start_index)
                            overlap_end = min(el_end, end_index)
                            if overlap_start < overlap_end:
                                content = el["textRun"].get("content", "")
                                rel_start = overlap_start - el_start
                                rel_end = overlap_end - el_start
                                deleted_preview += content[rel_start:rel_end]

        await retry_with_backoff(
            lambda: docs.documents()
            .batchUpdate(
                documentId=document_id,
                body={
                    "requests": [
                        {
                            "deleteContentRange": {
                                "range": {
                                    "startIndex": start_index,
                                    "endIndex": end_index,
                                    "segmentId": "",
                                }
                            }
                        }
                    ]
                },
            )
            .execute()
        )

        chars_deleted = end_index - start_index
        preview = deleted_preview[:200] + (
            "..." if len(deleted_preview) > 200 else ""
        )
        return {
            "documentId": document_id,
            "startIndex": start_index,
            "endIndex": end_index,
            "charsDeleted": chars_deleted,
            "deletedPreview": preview,
            "message": (
                f"Deleted {chars_deleted} characters from index "
                f"{start_index} to {end_index}"
            ),
        }
