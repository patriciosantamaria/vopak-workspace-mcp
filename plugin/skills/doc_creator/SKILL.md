---
name: Google Doc Creator
description: Create branded Google Docs from Markdown via the `branded_create_document` MCP tool. Converts MD → HTML → inline CSS → native Google Doc with Vopak branding (Deep Blue headings, branded tables). Supports optional 3-page corporate front-matter (Cover, Admin, Revision History).
---

# Google Doc Creator

Create branded Vopak Google Docs from Markdown content. The pipeline converts Markdown to styled HTML with inline CSS, then uploads to Google Drive as a native Google Doc with full brand fidelity.

## Quick Reference

### Primary Method: `branded_create_document` MCP Tool

This is the **recommended and fastest approach**. The tool runs inside the Docker container with pre-authenticated `googleapis` credentials — no local auth setup needed.

```
Tool: branded_create_document (workspace-branded)
Parameters:
  - markdown (required): The Markdown content to convert
  - title (required): Document title (used as filename in Drive)
  - folderId (optional): Google Drive folder ID (default: "root")
  - documentMeta (optional): Corporate front-matter metadata (see below)
```

**Usage Example (basic):**

```markdown
Use the `branded_create_document` tool with:
- markdown: <paste full markdown content here>
- title: "Q1 Security Audit Report"
- folderId: "1abc123def456"
```

**Usage Example (with corporate front-matter):**

```markdown
Use the `branded_create_document` tool with:
- markdown: <paste full markdown content here>
- title: "CAA Architecture Design"
- folderId: "1abc123def456"
- documentMeta:
    documentType: "Architecture Design Document"
    author: "IT Security Team"
    version: "1.0"
    status: "Draft"
    documentNumber: "MYDOCS-2025-042"
```

> **Important:** The `branded_create_document` MCP tool handles the entire pipeline — Markdown parsing, CSS inlining, and Drive upload — in a single call.

### Fallback Method: `md2gdoc.ts` Standalone Script

Use this when running outside the Docker container (e.g., local terminal, CI/CD). Requires Application Default Credentials (ADC).

```bash
# Prerequisites (one-time)
cd plugin/skills/doc_creator/scripts
npm install

# Run
npx tsx md2gdoc.ts <input.md> [options]

# Options
--folder-id <id>   # Google Drive folder ID (default: "root")
--name <title>     # Document title (default: from H1 or filename)
--css <path>       # Custom CSS (default: ../templates/vopak_doc.css)
--meta <json>      # Corporate front-matter metadata (JSON string)
--dry-run          # Output HTML without uploading
--output <path>    # Save HTML to local file
```

**Auth:** The script uses `google-auth-library` (ADC). Run `gcloud auth application-default login --scopes=https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/documents` first.

## Corporate Front-Matter Template

When `documentMeta` is provided (MCP tool) or `--meta` is used (CLI), the pipeline prepends **3 corporate template pages** before the content, matching the Vopak standard document template.

### Pages Generated

| Page | Content |
|:-----|:--------|
| **1. Cover** | Vopak logo, document type (36pt), document topic (16pt) |
| **2. Document Administration** | 10-row info table + authors/contributors table |
| **3. Revision History** | Version history table + Table of Contents placeholder |

### `documentMeta` Fields

| Field | Type | Required | Default | Description |
|:------|:-----|:---------|:--------|:------------|
| `documentType` | string | ✅ | — | e.g. "Technical Design Document" |
| `documentTopic` | string | ❌ | title | Topic/subject line on cover |
| `author` | string | ❌ | `""` | Document creator name |
| `version` | string | ❌ | `"0.1"` | Version number |
| `status` | string | ❌ | `"Draft"` | Document status |
| `documentNumber` | string | ❌ | `""` | MyDocs reference number |
| `logoUrl` | string | ❌ | built-in SVG | Public URL to Vopak logo |

> **Note:** Without `documentMeta`, documents are created exactly as before (content-only, no cover pages). The feature is fully backwards-compatible.

## Brand Specification (Documents)

Documents use a **Deep Blue + black/gray** color scheme. No Cyan.

| Element | Color | Hex |
|:--------|:------|:----|
| H1, H2, H3, H4 headings | Deep Blue | `#0a2373` |
| Heading underlines (H1, H2) | Deep Blue | `#0a2373` |
| Body text | Dark gray | `#333333` |
| Bold text (`<strong>`) | Deep Blue | `#0a2373` |
| Italic text (`<em>`) | Slate gray | `#46555a` |
| Table headers | White on Deep Blue | `#ffffff` on `#0a2373` |
| Table even rows | Light blue-gray | `#f0f5fa` |
| Table odd rows | White | `#ffffff` |
| Blockquote border | Deep Blue | `#0a2373` |
| Blockquote background | Light blue-gray | `#f0f5fa` |
| Code background | Light blue-gray | `#f0f5fa` |
| Code text | Deep Blue | `#0a2373` |
| Links | Deep Blue | `#0a2373` |
| Horizontal rules | Deep Blue | `#0a2373` |
| Font | Arial, sans-serif | — |
| Body font size | 10pt | — |

> **Rule:** Cyan (`#00cfe1`) is used in slides and UI designs, but **NOT in documents**. Documents are Deep Blue + black/gray only.

## Pipeline Architecture

```
Markdown Content
    │
    ▼
marked.parse()         → Raw HTML (no styling)
    │
    ▼
[if documentMeta]      → generateCoverPages()  → 3-page HTML front-matter
    │                     (Cover, Admin, Revision History)
    ▼
assembleHtml()         → Full HTML with <style> block
    │                     (cover pages + content body)
    ▼
juice()                → CSS inlined into style="" attributes
    │                    (critical: Google Docs ignores <style> blocks)
    ▼
Drive API multipart    → Native Google Doc with preserved formatting
upload (HTML → Doc)
    │
    ▼
Docs API batchUpdate   → A4 portrait page size (210×297mm)
```

### CSS Inlining — Critical Requirement

Google Docs **strips all `<style>` blocks** during HTML-to-Doc conversion. The `juice` library converts CSS rules into inline `style=""` attributes on each HTML element, which Google Docs does preserve.

Without this step, the document would render as plain unstyled text.

## File Structure

```
plugin/skills/doc_creator/
├── SKILL.md                          # This file
├── templates/
│   └── vopak_doc.css                 # Brand CSS template (standalone script)
└── scripts/
    ├── md2gdoc.ts                    # Standalone conversion script
    └── package.json                  # Script dependencies
```

> **Note:** The `branded_create_document` MCP tool (Go server) handles the pipeline internally.
> The standalone `md2gdoc.ts` script is a fallback for use outside the Docker container.

### CSS Sources

There are **two copies** of the brand CSS, kept in sync:

1. **Go server (internal)** — Embedded in the Go binary via `//go:embed` (inside Docker)
2. **`templates/vopak_doc.css`** — Standalone CSS file used by the `md2gdoc.ts` script

> **Critical:** When updating brand colors, update **both** files.

## Supported Markdown Elements

| Element | Markdown | Branded? |
|:--------|:---------|:---------|
| H1 heading | `# Title` | ✅ Deep Blue, 22pt, 3px underline |
| H2 heading | `## Section` | ✅ Deep Blue, 16pt, 2px underline |
| H3 heading | `### Subsection` | ✅ Deep Blue, 12pt |
| H4 heading | `#### Detail` | ✅ Deep Blue, 11pt |
| Bold | `**text**` | ✅ Deep Blue color |
| Italic | `*text*` | ✅ Slate gray |
| Tables | Pipe syntax | ✅ Blue headers, alternating rows |
| Blockquotes | `> text` | ✅ Deep Blue left border |
| Code inline | `` `code` `` | ✅ Light background, blue text |
| Code blocks | Triple backticks | ✅ Blue left border |
| Lists | `- item` | ✅ Standard formatting |
| Horizontal rules | `---` | ✅ Deep Blue line |
| Links | `[text](url)` | ✅ Deep Blue |

## Troubleshooting

### Auth Errors

**MCP Tool (branded_create_document):**
- Auth is handled by the Docker container's ADC credentials. If the tool returns an auth error, check `gcloud auth application-default login`.

**Standalone Script (md2gdoc.ts):**
- Requires ADC: `gcloud auth application-default login --scopes=https://www.googleapis.com/auth/drive`
- Uses `google-auth-library` (not `gcloud` CLI) for token retrieval

### Unstyled Output

If the Google Doc appears unstyled (plain text):
1. Check that `juice` is installed (`npm ls juice`)
2. Verify CSS is being read (the script logs the CSS path)
3. Confirm `removeStyleTags: true` is set in juice options
4. Check the HTML output with `--dry-run` — every element should have `style=""` attributes

### Sandbox Restrictions

The Antigravity IDE sandbox blocks access to `~/.config/gcloud/` (EPERM). In this environment:
- Use the **`branded_create_document` MCP tool** (recommended — runs inside Docker with its own auth)
- Or run the standalone script from a **normal terminal** outside the sandbox
