---
name: Content Editor
description: Edit existing Google Slides, Docs, and Sheets using prebuilt MCP tools. Trigger when modifying, searching, auditing, or reading existing Workspace content. DO NOT write Python/shell scripts — use the tool routing tables below.
---

# Content Editor Skill

> **Purpose**: Guide agents to use prebuilt `vopak-workspace-mcp` MCP tools for editing existing Google Workspace content instead of writing custom scripts.

## When to Activate

Trigger this skill when the task involves:
- Editing, updating, or formatting existing Slides/Docs/Sheets
- Searching for text across a presentation or document
- Reading speaker notes, element styles, or cell values
- Auditing a deck for terminology, overflow, or formatting issues
- Adding or updating speaker notes on slides
- Any Workspace content manipulation that might tempt you to write a Python script

## ⛔ Anti-Pattern: Custom Scripts

**NEVER** do any of the following:
- Write a Python script to parse Slides/Docs/Sheets JSON
- Use `python3 -c` inline to extract or search text
- Pipe `gws_read` output through a script to parse it
- Create scratch files to process Workspace API responses
- Use `slides_batch_update` when a dedicated tool exists

If you catch yourself about to write a parsing/extraction script, **STOP** and check the tool tables below.

---

## Tool Routing Tables

### Google Slides (14 tools)

#### Reading & Inspection

| Task | Tool | Key Parameters |
|:-----|:-----|:---------------|
| List all slides with metadata | `slides_list` | `presentationId` |
| Read all text + optional styles | `slides_get_content` | `presentationId`, `slideIndex`, `includeStyles?` |
| Search text across entire deck | `slides_search_text` | `presentationId`, `query`, `isRegex`, `caseSensitive` |
| Get slide thumbnail for visual QA | `slides_get_thumbnail` | `presentationId`, `slideObjectId` |
| Read table structure (rows, cols, content) | `slides_read_table` | `presentationId`, `slideIndex` |

#### Writing & Formatting

| Task | Tool | Key Parameters |
|:-----|:-----|:---------------|
| Find and replace text (single or bulk) | `slides_replace_text` | `presentationId`, `replacements: [{find, replace}]` |
| Insert an image | `slides_insert_image` | `presentationId`, `slideObjectId`, `imageUrl` |
| Update a table cell | `slides_update_cell` | `presentationId`, `tableObjectId`, `row`, `col`, `text` |
| Insert chart via QuickChart | `slides_insert_chart` | `presentationId`, `slideObjectId`, `chartConfig` |
| Add a new slide | `slides_add` | `presentationId`, `layoutId` |
| Delete a slide (DESTRUCTIVE) | `slides_delete` | `presentationId`, `slideObjectId` |
| Duplicate a slide | `slides_duplicate` | `presentationId`, `slideObjectId` |
| Move slides to new position | `slides_reorder` | `presentationId`, `slideObjectIds`, `insertionIndex` |
| Raw API escape hatch | `slides_batch_update` | `presentationId`, `requests` — **last resort only** |

> **Via `api_read`/`api_write`:** Speaker notes (get/update). Use `api_read` with `service=slides` for notes.
> **Via `slides_batch_update`:** Insert table, insert shape, set background, embed Sheets chart. See `tool_guard` skill.

### Google Docs (12 tools)

| Task | Tool | Key Parameters |
|:-----|:-----|:---------------|
| Read document structure (headings, tables) | `docs_get_structure` | `documentId` |
| Read full text or a section | `docs_read_text` | `documentId`, `sectionHeading?` |
| Search text with regex | `docs_search_text` | `documentId`, `query`, `isRegex` |
| Read table structure (rows, cols, content) | `docs_read_table` | `documentId`, `tableIndex` |
| Find and replace text | `docs_replace_text` | `documentId`, `find`, `replace` |
| Insert text at position | `docs_insert_text` | `documentId`, `text`, `index` |
| Apply formatting by substring | `docs_set_style` | `documentId`, `substring`, `style` |
| Insert inline image | `docs_insert_image` | `documentId`, `imageUrl`, `index` |
| Update text in a table cell | `docs_update_cell` | `documentId`, `tableIndex`, `row`, `col`, `text` |
| Add a row to an existing table | `docs_add_table_row` | `documentId`, `tableIndex` |
| Create a new table | `docs_insert_table` | `documentId`, `rows`, `cols`, `index` |
| Raw API escape hatch | `docs_batch_update` | `documentId`, `requests` — **last resort only** |

> **Via `docs_batch_update`:** Page breaks, headers/footers, named ranges. See `tool_guard` skill.

### Google Sheets (5 tools)

| Task | Tool | Key Parameters |
|:-----|:-----|:---------------|
| Read cell values | `sheets_read_range` | `spreadsheetId`, `range` (e.g., `'Sheet1!A1:C10'`) |
| Get spreadsheet metadata (tabs, dimensions) | `sheets_get_structure` | `spreadsheetId` |
| Write structured data | `sheets_write_data` | `spreadsheetId`, `range`, `values` |
| Write + readback verification | `sheets_verify_range` | `spreadsheetId`, `range`, `values` |
| Create a chart in a spreadsheet | `sheets_create_chart` | `spreadsheetId`, `sheetId`, `chartType` |

---

## Common Workflows

### Terminology Audit (Search & Replace across a deck)

```
1. slides_search_text({ query: "old term", isRegex: false })
   → Returns all matches with slideIndex, elementObjectId, context
2. slides_replace_text({
     presentationId: "...",
     replacements: [{ find: "old term", replace: "new term" }]
   })
3. slides_search_text({ query: "old term" })
   → Verify 0 matches remain
```

### Bulk Speaker Notes from an Outline

```
1. Read the outline file with view_file (the agent's native tool)
2. Reason about which content maps to which slide
3. For each slide, use api_write:
   api_write({
     service: "slides",
     method: "presentations.pages.updateSpeakerNotes",
     presentationId: "...",
     slideObjectId: "...",
     body: { notesText: "TALKING POINTS:\n- Point 1\n..." }
   })
```

**DO NOT** write a Python script to parse the outline. The agent can read and reason about markdown natively.

### Format Inspection & Replication

```
1. slides_get_content({ slideIndex: 0, includeStyles: true })
   → Returns text + font, size, bold, italic, colors, backgroundFill
2. Use the returned styles to format target elements via slides_batch_update
   with updateTextStyle requests
```

### Read & Update Spreadsheet

```
1. sheets_get_structure({ spreadsheetId: "..." })
   → Returns tab names, dimensions, named ranges
2. sheets_read_range({ spreadsheetId: "...", range: "Sheet1!A1:Z100" })
   → Returns 2D array of cell values
3. Process data using agent reasoning (NOT a Python script)
4. sheets_write_data({ ... }) or sheets_verify_range({ ... })
```
