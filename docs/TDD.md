# Technical Design Document: Vopak Workspace MCP Server (Go)

| Field | Value |
|:------|:------|
| **Document Owner** | Patricio Santamaria |
| **Version** | 2.0.0 |
| **Date** | June 2026 |
| **Status** | Draft — Pending Review |
| **Target Audience** | Backend Engineers (Go), Template Designers |

---

## 1. Technology Stack

| Component | Technology | Version |
|:----------|:----------|:--------|
| Language | Go | 1.25+ |
| MCP SDK | `github.com/modelcontextprotocol/go-sdk` | v1.6+ (official, maintained by MCP project + Google) |
| Google Slides API | `google.golang.org/api/slides/v1` | v1 |
| Google Docs API | `google.golang.org/api/docs/v1` | v1 |
| Google Sheets API | `google.golang.org/api/sheets/v4` | v4 |
| Google Drive API | `google.golang.org/api/drive/v3` | v3 |
| Auth | `google.golang.org/api/option` + ADC | — |
| Rate Limiting | `golang.org/x/time/rate` | latest |
| Concurrency | `golang.org/x/sync/errgroup` | latest |
| Container | Docker multi-stage (Alpine) | — |
| Testing | `testing` + `testify` | — |

---

## 2. Project Structure

```
vopak-workspace-mcp/
├── cmd/
│   └── server/
│       └── main.go                 # Entry point, CLI flags, server routing
│
├── internal/
│   ├── middleware/
│   │   ├── safeexec.go             # SafeExecute: panic recovery + AgentResult
│   │   ├── ratelimit.go            # Token bucket rate limiter
│   │   └── batch.go                # BatchUpdate request aggregator
│   │
│   ├── workspace/
│   │   ├── auth.go                 # Scoped OAuth credentials factory
│   │   ├── clients.go              # Slides/Docs/Sheets/Drive service builders
│   │   └── batch.go                # Generic BatchUpdate executor
│   │
│   └── tools/
│       ├── slides/
│       │   ├── read.go             # get_content (with include_styles), get_thumbnail
│       │   ├── write.go            # add, duplicate, reorder, replace_text
│       │   ├── search.go           # search_text, list
│       │   ├── tables.go           # read_table, update_cell
│       │   ├── charts.go           # insert_chart (QuickChart)
│       │   └── register.go         # RegisterSlidesTools(server)
│       │
│       ├── docs/
│       │   ├── read.go             # read_text, get_structure, read_table
│       │   ├── write.go            # insert_text, set_style, insert_image
│       │   ├── tables.go           # update_cell, add_table_row, insert_table
│       │   ├── search.go           # search_text
│       │   └── register.go         # RegisterDocsTools(server)
│       │
│       ├── sheets/
│       │   ├── read.go             # read_range, get_structure
│       │   ├── write.go            # write_data, create_chart
│       │   └── register.go         # RegisterSheetTools(server)
│       │
│       ├── drive/
│       │   ├── list.go             # list
│       │   ├── manage.go           # create_folders
│       │   └── register.go         # RegisterDriveTools(server)
│       │
│       ├── branded/
│       │   ├── presentation.go     # branded_create_presentation
│       │   ├── document.go         # branded_create_document
│       │   ├── health.go           # branded_health_check
│       │   └── register.go         # RegisterBrandedTools(server)
│       │
│       └── api/
│           ├── bridge.go           # api_read/write/delete
│           └── register.go         # RegisterAPITools(server)
│
├── pkg/
│   └── agentresult/
│       └── result.go               # AgentResult type + helpers
│
├── config/
│   └── templates.json              # Template registry (17 templates)
│

├── tests/
│   ├── slides_test.go
│   ├── docs_test.go
│   ├── middleware_test.go
│   └── testdata/                   # Mock API responses
│
├── docs/
│   ├── ADD.md                      # Architecture Design Document
│   ├── TDD.md                      # This document
│   ├── reference/                  # API reference & usage guides
│   └── assets/
│
├── go.mod
├── go.sum
├── Dockerfile
├── docker-compose.yml
├── mcp_config.example.json
├── .gitignore
└── README.md
```

---

## 3. Core Data Types

### 3.1 AgentResult (`pkg/agentresult/result.go`)

Every MCP tool returns a JSON-serialized `AgentResult`. No tool ever returns raw data or unstructured errors.

```go
package agentresult

// AgentResult is the standard response from every MCP tool.
type AgentResult struct {
    Success   bool        `json:"success"`
    Message   string      `json:"message"`
    Data      interface{} `json:"data,omitempty"`
    ErrorCode string      `json:"error_code,omitempty"`
}

func Success(msg string, data interface{}) AgentResult {
    return AgentResult{Success: true, Message: msg, Data: data}
}

func Error(msg string, code string) AgentResult {
    return AgentResult{Success: false, Message: msg, ErrorCode: code}
}
```

### 3.2 Tool Registration Pattern

Each tool group exposes a `Register*Tools(server)` function using the official SDK's type-safe struct pattern:

```go
package slides

import (
    "context"
    "github.com/modelcontextprotocol/go-sdk/mcp"
)

// Input structs — schema auto-generated from jsonschema tags
type GetSlideContentArgs struct {
    PresentationID string `json:"presentation_id" jsonschema:"required,description=Google Slides presentation ID"`
    SlideIndex     int    `json:"slide_index"     jsonschema:"required,description=Zero-based slide index"`
}

type UpdateSpeakerNotesArgs struct {
    PresentationID string `json:"presentation_id" jsonschema:"required,description=Google Slides presentation ID"`
    SlideIndex     int    `json:"slide_index"     jsonschema:"required,description=Zero-based slide index"`
    Notes          string `json:"notes"           jsonschema:"required,description=New speaker notes content"`
}

func RegisterSlideTools(s *mcp.Server) {
    // Read tools
    mcp.AddTool(s, &mcp.Tool{
        Name:        "slides_get_content",
        Description: "Read the full content of a specific slide",
    }, handleGetSlideContent)

    // Write tools
    mcp.AddTool(s, &mcp.Tool{
        Name:        "slides_replace_text",
        Description: "Find and replace text in a presentation",
    }, handleReplaceText)
}

// Handler — type-safe args, no runtime string parsing
func handleGetSlideContent(ctx context.Context, req *mcp.CallToolRequest, args GetSlideContentArgs) (*mcp.CallToolResult, any, error) {
    // args.PresentationID and args.SlideIndex are already typed
    // ...
    return &mcp.CallToolResult{
        Content: []mcp.Content{&mcp.TextContent{Text: resultJSON}},
    }, nil, nil
}
```

---

## 4. Middleware Specifications

### 4.1 SafeExecute (`internal/middleware/safeexec.go`)

Wraps every tool handler with panic recovery and structured error responses.
The official SDK supports middleware via `mcp.ServerOption` or per-tool wrapping:

```go
// SafeExecute wraps a tool handler with panic recovery + AgentResult
func SafeExecute[T any](toolName string, handler mcp.ToolHandlerFunc[T]) mcp.ToolHandlerFunc[T] {
    return func(ctx context.Context, req *mcp.CallToolRequest, args T) (*mcp.CallToolResult, any, error) {
        defer func() {
            if r := recover(); r != nil {
                log.Printf("[%s] panic recovered: %v", toolName, r)
            }
        }()
        result, metadata, err := handler(ctx, req, args)
        if err != nil {
            return agentResultError(toolName, err), nil, nil
        }
        return result, metadata, nil
    }
}
```

### 4.2 Token Bucket Rate Limiter (`internal/middleware/ratelimit.go`)

Prevents Google API `429 Too Many Requests` errors by throttling outbound requests:

```go
var limiter = rate.NewLimiter(rate.Limit(5), 10) // 5 req/s, burst 10

func WaitForToken(ctx context.Context) error {
    return limiter.Wait(ctx)
}
```

Every Google API call must call `WaitForToken(ctx)` before execution.

### 4.3 BatchUpdate Aggregator (`internal/middleware/batch.go`)

Coalesces multiple mutations into a single `BatchUpdate` API call:

```go
type BatchCollector struct {
    mu       sync.Mutex
    requests []*slides.Request
}

func (b *BatchCollector) Add(req *slides.Request) {
    b.mu.Lock()
    defer b.mu.Unlock()
    b.requests = append(b.requests, req)
}

func (b *BatchCollector) Flush(ctx context.Context, svc *slides.Service, presentationID string) error {
    b.mu.Lock()
    reqs := b.requests
    b.requests = nil
    b.mu.Unlock()

    if len(reqs) == 0 {
        return nil
    }

    if err := WaitForToken(ctx); err != nil {
        return err
    }
    _, err := svc.Presentations.BatchUpdate(presentationID, &slides.BatchUpdatePresentationRequest{
        Requests: reqs,
    }).Context(ctx).Do()
    return err
}
```

---

## 5. Authentication (`internal/workspace/auth.go`)

### 5.1 Development: Application Default Credentials

```go
func GetScopedCredentials(ctx context.Context, scopes ...string) (*google.Credentials, error) {
    return google.FindDefaultCredentials(ctx, scopes...)
}
```

### 5.2 Production: Domain-Wide Delegation

```go
func GetImpersonatedCredentials(ctx context.Context, subject string, scopes ...string) (*google.Credentials, error) {
    data, err := os.ReadFile(os.Getenv("GOOGLE_APPLICATION_CREDENTIALS"))
    if err != nil {
        return nil, err
    }
    conf, err := google.JWTConfigFromJSON(data, scopes...)
    if err != nil {
        return nil, err
    }
    conf.Subject = subject // impersonate the employee
    return &google.Credentials{
        TokenSource: conf.TokenSource(ctx),
    }, nil
}
```

---

## 6. Template Preparation Specification

### 6.0 Template Source

All corporate templates live in a single Google Drive folder. The server reads individual template IDs from an embedded registry (`templates.json`), but the folder ID is the env-configured root.

| Config | Value |
|:-------|:------|
| **Folder URL** | [AI Agent Templates](https://drive.google.com/drive/folders/1DcCliXLB4qp8jOStQKPS4iCJUHPE8Lxm) |
| **Folder ID** | `1DcCliXLB4qp8jOStQKPS4iCJUHPE8Lxm` |
| **Env variable** | `TEMPLATE_FOLDER_ID` |
| **Contents** | 1 Slide deck (30 layouts) + 17 Doc templates |

```yaml
# docker-compose.yml
environment:
  TEMPLATE_FOLDER_ID: "1DcCliXLB4qp8jOStQKPS4iCJUHPE8Lxm"
```

> [!NOTE]
> Individual template IDs are compiled into the binary via `//go:embed templates.json`. The folder ID is only used by `branded_health_check` to verify template access at startup.

### 6.1 Text Placeholders

| Placeholder | Format | Example |
|:------------|:-------|:--------|
| Simple text | `{{KEY}}` | `{{CLIENT_NAME}}` |
| Date | `{{DATE_KEY}}` | `{{REPORT_DATE}}` |
| Multi-line | `{{BODY_KEY}}` | `{{EXECUTIVE_SUMMARY}}` |
| Angle-bracket (Docs) | `<key>` | `<document name>`, `<mydocs number>` |

Rules:
- Apply the final font family, size, weight, and color **to the placeholder text itself**
- The replacement inherits the formatting of the placeholder
- Slides use `{{MUSTACHE}}` format; Doc templates use `<angle bracket>` format

### 6.2 Bounding Box (Dynamic Zone) Placeholders

For dynamic content injection (charts, data tables):

1. Draw a **Rectangle** shape in the target area
2. Set Fill → **Transparent**, Border → **Transparent**
3. Right-click → **Alt Text** → Set Title to `{{DYNAMIC_ZONE_1}}`

The server locates zones by iterating `PageElements`:

```go
func FindZone(page *slides.Page, zoneTag string) (*slides.PageElement, error) {
    for _, el := range page.PageElements {
        if el.Shape != nil && el.Shape.Placeholder == nil {
            title := el.Title
            desc := el.Description
            if title == zoneTag || desc == zoneTag {
                return el, nil
            }
        }
    }
    return nil, fmt.Errorf("zone %q not found", zoneTag)
}
```

### 6.3 CSS-to-EMU Conversion Reference

| CSS Property | Slides API Equivalent | Conversion |
|:-------------|:---------------------|:-----------|
| `width: 100px` | `Size.Width.Magnitude` | `100 × 9525 = 952500 EMU` |
| `height: 50px` | `Size.Height.Magnitude` | `50 × 9525 = 476250 EMU` |
| `left: 20px` | `Transform.TranslateX` | `20 × 9525 = 190500 EMU` |
| `color: #0a2373` | `TextStyle.ForegroundColor` | `R:10/255, G:35/255, B:115/255` |
| `font-size: 24px` | `TextStyle.FontSize.Magnitude` | `24` (pt, not EMU) |
| `font-family: Inter` | `TextStyle.FontFamily` | `"Inter"` |

Constant: **1 CSS px = 9,525 EMU**

### 6.4 Chart Injection Strategy

| Chart Need | Strategy | Tool |
|:-----------|:---------|:-----|
| Simple charts (bar, pie, line) | QuickChart.io API → PNG image | `slides_insert_chart` |
| Live-updating data | Linked Google Sheets chart | `slides_batch_update` (CreateSheetsChart) |
| Data tables / KPIs | Native Slides table elements | `slides_update_cell` |

QuickChart flow:
```
1. Agent constructs Chart.js JSON config
2. slides_insert_chart → calls https://quickchart.io/chart?c=<config>&w=800&h=400
3. Finds bounding box shape by Alt-Text tag
4. Deletes placeholder shape, inserts image at same position/size
```

### 6.5 Document Template Front-Matter (3-Page Pattern)

All Vopak formal document templates (v4.1 family) share a mandatory 3-page front-matter structure. The agent MUST preserve pages 1-3 intact and only fill placeholders:

```
┌── Page 1: COVER ──────────────────────────────────┐
│  • Vopak logo (image — DON'T TOUCH)               │
│  • Department banner (image — DON'T TOUCH)         │
│  • Title: "Global IT <Type>"                       │  ← FILL
│  • Subtitle: "<document name>"                     │  ← FILL
└────────────────────────────────────────────────────┘
┌── Page 2: DOCUMENT ADMIN BLOCK (3 tables) ────────┐
│  TABLE 1: Document Information (10 rows)           │
│    Document name, number, type, status,            │  ← FILL cells
│    version, dates, creator, owner, approver        │
│                                                    │
│  TABLE 2: Authors & Contributors (3 cols)          │
│    Name, Contribution, Contact details             │  ← ADD ROWS
│                                                    │
│  TABLE 3: Revision History (3 cols)                │
│    Version, Date, Description                      │  ← ADD ROWS
└────────────────────────────────────────────────────┘
┌── Page 3: TABLE OF CONTENTS ──────────────────────┐
│  Auto-linked TOC with heading anchors              │  ← AUTO-UPDATES
└────────────────────────────────────────────────────┘
┌── Page 4+: BODY CONTENT ──────────────────────────┐
│  Section 1: Introduction + Document Purpose        │  ← WRITE
│  Section 2-N: Type-specific content                │  ← WRITE
│  References table                                  │  ← ADD ROWS
│  Terms & definitions table                         │  ← ADD ROWS
│  Footer: "Page X of Y"                             │  ← AUTO
└────────────────────────────────────────────────────┘
```

**Agent workflow for formal documents:**
1. Copy template → `drive.Files.Copy(templateId)`
2. Page 1 — `docs_replace_text` for cover title/subtitle placeholders
3. Page 2 — `docs_update_cell` for Document Info + `docs_add_table_row` for authors/revisions
4. Page 3 — TOC auto-updates when body headings are written
5. Page 4+ — `docs_replace_text` for section placeholder text, `docs_insert_text` for body content

**Critical rule:** Logos, department banners, horizontal rules, page borders, table styling, and all visual formatting are baked into the template. The agent NEVER recreates or modifies formatting — only fills text content.

---

## 7. Docker Build

### Multi-stage Dockerfile

```dockerfile
# Stage 1: Build
FROM golang:1.25-alpine AS builder
WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /server ./cmd/server

# Stage 2: Runtime
FROM alpine:3.21
RUN apk --no-cache add ca-certificates
COPY --from=builder /server /app/server
ENTRYPOINT ["sleep", "infinity"]
```

### docker-compose.yml

```yaml
services:
  workspace-mcp:
    build: .
    container_name: vopak-workspace-mcp
    restart: unless-stopped
    volumes:
      - ${HOME}/.config/gcloud:/root/.config/gcloud:ro
volumes: {}
```

---

## 8. MCP Config Example

```json
{
  "mcpServers": {
    "workspace-slides": {
      "command": "docker",
      "args": ["exec", "-i", "vopak-workspace-mcp", "/app/server", "--server", "slides"],
      "timeout": 30
    },
    "workspace-docs": {
      "command": "docker",
      "args": ["exec", "-i", "vopak-workspace-mcp", "/app/server", "--server", "docs"],
      "timeout": 30
    },
    "workspace-sheets": {
      "command": "docker",
      "args": ["exec", "-i", "vopak-workspace-mcp", "/app/server", "--server", "sheets"],
      "timeout": 30
    },
    "workspace-drive": {
      "command": "docker",
      "args": ["exec", "-i", "vopak-workspace-mcp", "/app/server", "--server", "drive"],
      "timeout": 30
    },
    "workspace-branded": {
      "command": "docker",
      "args": ["exec", "-i", "vopak-workspace-mcp", "/app/server", "--server", "branded"],
      "timeout": 30
    },
    "workspace-api": {
      "command": "docker",
      "args": ["exec", "-i", "vopak-workspace-mcp", "/app/server", "--server", "api"],
      "timeout": 30
    }
  }
}
```

---

## 9. Testing Strategy

### Unit Tests

Mock Google API responses using `httptest.NewServer`:

```go
func TestGetSlideContent(t *testing.T) {
    // Create a fake Slides API server
    ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        json.NewEncoder(w).Encode(slides.Presentation{
            Slides: []*slides.Page{{ObjectId: "slide1"}},
        })
    }))
    defer ts.Close()

    // Point the client at the test server
    svc, _ := slides.NewService(context.Background(), option.WithEndpoint(ts.URL))
    // ... test
}
```

### Integration Tests

Run against a real Google Workspace sandbox with a dedicated test account. Guarded by `INTEGRATION_TEST=true` env var.

### Coverage Target

Minimum **80%** coverage on `internal/tools/` and `internal/middleware/`.

---

## 10. Tool Catalog (39 Tools)

> **Optimization rationale:** Research shows tool selection accuracy drops below 85% above 30 tools. We reduced from 49 to 39 by merging similar tools, deferring rare operations to `batch_update` escape hatches, and routing simple operations (speaker notes) to the API bridge. Combined with tool profiles (disabling unused servers), the active tool count during typical sessions is ~27–33.

### Slides (14 tools)

| Tool | Type | Description |
|:-----|:-----|:------------|
| `slides_get_content` | Read | All content + optional style details (`include_styles` param) |
| `slides_get_thumbnail` | Read | Slide thumbnail image URL (separate API endpoint) |
| `slides_search_text` | Read | Find text across all slides |
| `slides_list` | Read | All slides with metadata |
| `slides_read_table` | Read | Read table structure (rows, cols, cell content) |
| `slides_add` | Write | Insert a new slide |
| `slides_delete` | Destructive | Remove a slide (DESTRUCTIVE) |
| `slides_duplicate` | Write | Copy a slide |
| `slides_replace_text` | Write | Find and replace text (accepts single or array of replacements) |
| `slides_insert_image` | Write | Add an image to a slide |
| `slides_update_cell` | Write | Update text/formatting in a table cell |
| `slides_insert_chart` | Write | Generate chart via QuickChart and insert as image |
| `slides_reorder` | Write | Move slides to a new position |
| `slides_batch_update` | Batch | Raw BatchUpdate escape hatch (covers: insert_table, insert_shape, set_background, embed_chart) |

> **Deferred to `slides_batch_update`:** `CreateTable`, `CreateShape`, `UpdatePageProperties` (background), `CreateSheetsChart` (embed). See `tool_guard` skill for usage examples.
>
> **Deferred to `api_read`/`api_write`:** Speaker notes (get/update). Simple text operations that don't require pixel-perfect control.

### Docs (12 tools)

| Tool | Type | Description |
|:-----|:-----|:------------|
| `docs_read_text` | Read | Read document text content |
| `docs_get_structure` | Read | Document structural elements |
| `docs_search_text` | Read | Find text in document |
| `docs_read_table` | Read | Read table structure (rows, cols, cell content) |
| `docs_insert_text` | Write | Insert text at position |
| `docs_replace_text` | Write | Find and replace |
| `docs_set_style` | Write | Apply formatting |
| `docs_insert_image` | Write | Add inline image |
| `docs_update_cell` | Write | Update text in a specific table cell |
| `docs_add_table_row` | Write | Add a row to an existing table |
| `docs_insert_table` | Write | Create a new table at position |
| `docs_batch_update` | Batch | Raw BatchUpdate escape hatch (covers: insert_break, set_page_setup, manage_ranges) |

> **Deferred to `docs_batch_update`:** `InsertPageBreak`, `CreateHeader`/`CreateFooter`, `UpdateDocumentStyle`, `CreateNamedRange`/`DeleteNamedRange`. See `tool_guard` skill for usage examples.

### Sheets (5 tools)

| Tool | Type | Description |
|:-----|:-----|:------------|
| `sheets_read_range` | Read | Read cell values |
| `sheets_get_structure` | Read | Sheet names, dimensions |
| `sheets_write_data` | Write | Write structured data |
| `sheets_verify_range` | Read | Cell-by-cell comparison |
| `sheets_create_chart` | Write | Create a chart in a spreadsheet |

### Drive (2 tools)

| Tool | Type | Description |
|:-----|:-----|:------------|
| `drive_list` | Read | Search/list files |
| `drive_create_folders` | Write | Create nested folder structures |

### Branded (3 tools)

| Tool | Type | Description |
|:-----|:-----|:------------|
| `branded_create_presentation` | Write | Create branded presentation from template |
| `branded_create_document` | Write | Create branded document from template |
| `branded_health_check` | Read | Environment, credentials, and dependency verification |

### Workspace API Bridge (3 tools)

Generic REST bridge for **any** Google Workspace API. Replaces the need for Google's developer-preview MCP servers (`gws-gmail`, `gws-calendar`, etc.). One ADC credential, no separate GCP project required.

| Tool | Type | Description |
|:-----|:-----|:------------|
| `api_read` | Read | Call any Google Workspace REST API (GET operations) |
| `api_write` | Write | Call any Google Workspace REST API (POST/PUT/PATCH) |
| `api_delete` | Destructive | Call any Google Workspace REST API (DELETE) — HITL required (DESTRUCTIVE) |

**Supported services:** `gmail`, `calendar`, `drive`, `forms`, `tasks`, `admin`, `groups`, `chat`, `people`, `sites`

```go
type WorkspaceAPIReadArgs struct {
    Service string         `json:"service"  jsonschema:"required,description=Google Workspace API (gmail\u002ccalendar\u002cforms\u002ctasks\u002cadmin\u002cetc.)"`
    Method  string         `json:"method"   jsonschema:"required,description=API method (e.g. users.messages.list)"`
    Params  map[string]any `json:"params"   jsonschema:"description=Method parameters as key-value pairs"`
}
```

---

## 11. Template Registry

The server loads a template registry at startup from `config/templates.json`.
Discovery: embedded via `//go:embed config/templates.json` at compile time (no runtime file lookup).

```go
type TemplateRegistry struct {
    FolderID  string                      `json:"folder_id"`
    Templates map[string]TemplateEntry    `json:"templates"`
}

type TemplateEntry struct {
    ID           string   `json:"id"`
    Type         string   `json:"type"`         // "presentation" | "document"
    Category     string   `json:"category"`     // "formal" | "operational" | "correspondence"
    Version      string   `json:"version"`      // template version (e.g. "4.1", "2.0")
    Placeholders []string `json:"placeholders"` // known placeholder patterns
}
```

### Registered Templates (17)

| Key | Template | Type | Category |
|:----|:---------|:-----|:---------|
| `slides_corporate` | Vopak Corporate Template for AI Agent | Presentation | — |
| `doc_add` | Architectural Decision Document (v4.1) | Document | Formal |
| `doc_guideline` | Global IT Guideline (v4.1) | Document | Formal |
| `doc_procedure` | Global IT Procedure (v4.1) | Document | Formal |
| `doc_policy` | Global IT Policy (v4.1) | Document | Formal |
| `doc_process` | Global IT Process (v4.1) | Document | Formal |
| `doc_project_brief` | Global IT Project Brief (v4.1) | Document | Formal |
| `doc_standard` | Empty template for Vopak Standard | Document | Formal |
| `doc_standard_gocc` | Global Projects Document (v1.0) | Document | Formal |
| `doc_incident_report` | Global IT Incident Report (v2.0) | Document | Operational |
| `doc_change_plan` | Change Implementation Plan | Document | Formal |
| `doc_generic` | Generic Document (v4.1) | Document | Formal |
| `doc_proposal` | DevOps Proposal (v1.1) | Document | Formal |
| `doc_meeting_tracker` | Agenda, Action & Decision Tracker | Document | Operational |
| `doc_memo` | Memo for internal use | Document | Correspondence |
| `doc_letter_en` | Letter template English 2024 | Document | Correspondence |
| `doc_letter_nl` | Nieuwe template brief KV Nederlands | Document | Correspondence |

---

## 12. Error Code Taxonomy

All tools return `AgentResult` with standardized error codes:

| Error Code | Meaning | Example |
|:-----------|:--------|:--------|
| `AUTH_FAILED` | Credentials invalid or expired | ADC not configured |
| `NOT_FOUND` | Requested resource doesn't exist | Presentation ID invalid |
| `TEMPLATE_NOT_FOUND` | Template key not in registry | `doc_foo` not a valid key |
| `ZONE_NOT_FOUND` | Bounding box zone not found | `{{DYNAMIC_ZONE_99}}` missing |
| `DATA_SOURCE_MISSING` | Chart requested without data | No sheet range or explicit data |
| `QUOTA_EXCEEDED` | Google API rate limit hit | 429 Too Many Requests |
| `PERMISSION_DENIED` | Insufficient OAuth scopes | Missing `drive` scope |
| `INVALID_ARGS` | Tool arguments malformed | Missing required field |
| `API_ERROR` | Google API returned an error | 500 from Slides API |
| `BRAND_VIOLATION` | Content doesn't match brand rules | Wrong color hex used |

---

## 13. Logging Strategy

All output goes to **stderr** (MCP protocol uses stdout for JSON-RPC).

```go
// Structured JSON logging format
{
    "level": "info|warn|error",
    "tool": "slides_replace_text",
    "presentation_id": "1abc...",
    "duration_ms": 234,
    "message": "Replaced 5 instances of {{TITLE}}"
}
```

Rules:
- **Never log PII** — no names, emails, or user IDs (replace with `[REDACTED]`)
- **Always log tool name** — for tracing multi-tool workflows
- **Log API call duration** — for performance monitoring
- **Log error codes** — match the taxonomy in Section 12
