---
name: Tool Guard
description: "ALWAYS ACTIVE — Routing guard that ensures agents use granular workspace tools (slides_*, docs_*, sheets_*, drive_*, branded_*) before falling back to the api_* bridge. Load this skill at every session boot."
---

# Tool Guard — Granular Tools First, API Bridge as Fallback

> **Priority**: This skill MUST be loaded at every session boot. It acts as a pre-flight check before any workspace operation.

## Purpose

Prevent the agent from using `api_read`, `api_write`, or `api_delete` for operations that already have dedicated granular tools. Without this guard, the agent may call `api_write` to do a Slides text replacement instead of `slides_replace_text` — which is less reliable, harder to debug, and produces worse audit logs.

---

## RULE 1: Granular Tools ALWAYS Take Priority

Before using any `api_*` tool, check if a dedicated tool exists:

### Slides Operations → Use `slides_*` tools

| ❌ Don't | ✅ Do |
|:---------|:------|
| `api_read` with `service=slides` | `slides_get_content` or `slides_list` |
| `api_write` with Slides batch update body | `slides_batch_update` |
| `api_read` for slide thumbnails | `slides_get_thumbnail` |
| `api_write` to replace text | `slides_replace_text` |
| `api_write` to insert image | `slides_insert_image` |

### Docs Operations → Use `docs_*` tools

| ❌ Don't | ✅ Do |
|:---------|:------|
| `api_read` with `service=docs` | `docs_read_text` or `docs_get_structure` |
| `api_write` with Docs batch update body | `docs_batch_update` |
| `api_write` to insert text | `docs_insert_text` |
| `api_write` to find/replace | `docs_replace_text` |

### Sheets Operations → Use `sheets_*` tools

| ❌ Don't | ✅ Do |
|:---------|:------|
| `api_read` with `service=sheets` | `sheets_read_range` or `sheets_get_structure` |
| `api_write` with values update body | `sheets_write_data` |
| `api_write` to create a chart | `sheets_create_chart` |

### Drive Operations → Use `drive_*` tools

| ❌ Don't | ✅ Do |
|:---------|:------|
| `api_read` with `method=files.list` | `drive_list` |
| `api_write` to create folders | `drive_create_folders` |

### Branded Content → Use `branded_*` tools

| ❌ Don't | ✅ Do |
|:---------|:------|
| `api_write` to copy a template file | `branded_create_presentation` or `branded_create_document` |
| Manual file copy + placeholder replacement | `branded_create_*` (does both in one call) |

---

## RULE 2: `api_*` Tools Are ONLY for Services WITHOUT Granular Tools

The following services are **only** accessible via the API bridge:

| Service | Example Operations |
|:--------|:-------------------|
| `gmail` | Search, read, draft, send, label management |
| `calendar` | List, create, update, delete events |
| `tasks` | List, create, update, delete tasks |
| `forms` | Read form structure, list responses |
| `admin` | User/group/OU management |
| `groups` | Group membership management |
| `people` | Directory search, contacts |
| `chat` | Space listing, message sending |
| `sites` | Site/page listing |

---

## RULE 3: Drive Edge Cases

Some Drive operations **are** covered by granular tools, but others need the API bridge:

### ✅ Use Granular Tools
- `drive_list` — search and list files
- `drive_create_folders` — create folder hierarchies

### ✅ Use API Bridge (no granular tool)
- `api_read` → `permissions.list` — list sharing permissions
- `api_write` → `permissions.create` — share a file
- `api_delete` → `permissions.delete` — revoke sharing (DESTRUCTIVE)
- `api_write` → `files.update` — rename or move files
- `api_write` → `files.copy` — copy a non-template file
- `api_delete` → `files.delete` — delete a file (DESTRUCTIVE)

---

## RULE 4: `slides_batch_update` and `docs_batch_update` Are Escape Hatches

These tools accept raw API request bodies for operations that don't have a dedicated tool. Use them for:

### Slides — Valid `slides_batch_update` Use Cases

| Operation | Request Type |
|:----------|:------------|
| Insert a table | `createTable` |
| Insert a shape (text box) | `createShape` |
| Format text (font, size, color, bold) | `updateTextStyle` |
| Format paragraph (alignment, spacing) | `updateParagraphStyle` |
| Set slide background color | `updatePageProperties` |
| Update element position/size | `updatePageElementTransform` |
| Group/ungroup elements | `groupObjects` / `ungroupObjects` |
| Create a line | `createLine` |
| Update line properties | `updateLineProperties` |

### Docs — Valid `docs_batch_update` Use Cases

| Operation | Request Type |
|:----------|:------------|
| Insert page break | `insertPageBreak` |
| Insert section break | `insertSectionBreak` |
| Update table column width | `updateTableColumnProperties` |
| Insert header/footer | `createHeader` / `createFooter` |
| Update document style | `updateDocumentStyle` |
| Create named range | `createNamedRange` |

---

## Decision Flowchart

```
Agent wants to perform a Workspace operation
│
├── Is it Slides/Docs/Sheets content?
│   └── YES → Use the dedicated granular tool (slides_*, docs_*, sheets_*)
│             If no dedicated tool exists → use *_batch_update escape hatch
│
├── Is it Drive file listing or folder creation?
│   └── YES → Use drive_list / drive_create_folders
│
├── Is it Drive permissions, sharing, rename, or move?
│   └── YES → Use api_* (no granular tool for these)
│
├── Is it creating branded content from a Vopak template?
│   └── YES → Use branded_create_presentation / branded_create_document
│
└── Is it Gmail, Calendar, Forms, Tasks, Admin, Groups, Chat, People, or Sites?
    └── YES → Use api_* (these services only have bridge access)
```

## Anti-Patterns

- ❌ **NEVER** use `api_*` for Slides/Docs/Sheets content operations
- ❌ **NEVER** use `api_*` to copy templates — use `branded_*` tools
- ❌ **NEVER** use `api_*` for Drive list/create when `drive_*` tools exist
- ❌ **NEVER** write Python/shell scripts to call Workspace APIs — use MCP tools
- ❌ **NEVER** use `slides_batch_update` when a dedicated `slides_*` tool exists (e.g., don't use batch_update for text replacement when `slides_replace_text` exists)
