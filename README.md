# Vopak Workspace MCP

Google Workspace MCP servers for AI agents. Slides, Docs, Sheets, Drive — plus a universal CLI escape hatch for everything else.

## Quick Start (4 steps)

```bash
# 1. Clone
git clone https://github.com/vopak/vopak-workspace-mcp.git
cd vopak-workspace-mcp

# 2. Build & Start
docker compose up -d --build

# 3. Authenticate (one-time)
docker exec -it workspace-mcp gws auth login
docker exec -it workspace-mcp gcloud auth application-default login

# 4. Add to your IDE
# Copy mcp_config.example.json into your Antigravity or Cursor MCP config
```

Done. Your AI agent now has full Google Workspace access.

---

## What You Get

### Server 1: `workspace-tools` (36 granular tools)

Typed, schema-validated tools for precise Workspace operations:

| App | Tools | Examples |
|:----|:-----:|:--------|
| **Slides** | 20 | Create branded presentations, edit text, format, duplicate slides, get thumbnails, audit deck quality |
| **Docs** | 8 | Read/write text, search, find & replace, style formatting, append sections |
| **Sheets** | 4 | Read ranges, write data, verify writes, get structure |
| **Drive** | 2 | List files, manage files (move, copy, rename) |
| **Branded** | 1 | Health check |
| **Infra** | 1 | Docker environment diagnostics |

### Server 2: `workspace-cli` (3 tools)

Universal escape hatch — covers **all** Google Workspace APIs via the [GWS CLI](https://github.com/googleworkspace/cli):

| Tool | Covers | Safety |
|:-----|:-------|:-------|
| `gws_read` | All read-only operations (Gmail, Calendar, Tasks, Forms, etc.) | Server-side verb gating |
| `gws_write` | All create/update operations | Verb gating + reason required |
| `gws_destructive` | All delete/trash operations | ⚠️ HITL confirmation required |

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Docker Container                    │
│                                                  │
│  ┌──────────────────┐  ┌──────────────────────┐ │
│  │ workspace-tools   │  │ workspace-cli         │ │
│  │ (36 granular)     │  │ (3 CLI wrappers)      │ │
│  │                   │  │                       │ │
│  │ Slides API ──────►│  │ gws_read ────────────►│ │
│  │ Docs API ────────►│  │ gws_write ───────────►│ │
│  │ Sheets API ──────►│  │ gws_destructive ─────►│ │
│  │ Drive API ───────►│  │                       │ │
│  └──────────────────┘  └──────────────────────┘ │
│                                                  │
│  Python 3.11 + GWS CLI + gcloud                 │
└─────────────────────────────────────────────────┘
```

---

## Optional: Google Managed MCP Servers (Layer 1)

> ⚠️ **Developer Preview** — requires GCP project + [Developer Preview enrollment](https://developers.google.com/workspace/preview)

For colleagues who already have GCP access, you can add Google's official remote MCP servers for Gmail, Drive, and Calendar alongside this Docker setup. See `docs/TOOL_REFERENCE.md` for configuration.

---

## Project Structure

```
src/
├── servers/
│   ├── workspace_tools.py   # Entry point — 36 granular tools
│   └── workspace_cli.py     # Entry point — 3 CLI wrapper tools
├── tools/
│   ├── slides.py            # 19 Slides tools
│   ├── docs.py              # 8 Docs tools
│   ├── sheets.py            # 4 Sheets tools
│   ├── drive.py             # 2 Drive tools
│   ├── branded.py           # 3 Branded content tools
│   └── cli_wrapper.py       # 3 CLI wrapper tools
└── shared/
    ├── common.py            # @safe_execute, AgentResult, auth helpers
    ├── gws_helpers.py       # Verb sets, query builders
    ├── gws_runner.py        # GWS CLI subprocess runner
    ├── vopak_slides_generator.py
    ├── vopak_cover_template.py
    └── vopak_docs_generator.py
```

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/ tests/
```

---

## Security

- **Server-side verb gating**: CLI wrapper tools enforce verb sets at the server level. `gws_read` cannot execute write verbs, period.
- **HITL for destructive**: `gws_destructive` is tagged with `⚠️ DESTRUCTIVE` which triggers human-in-the-loop confirmation in Antigravity IDE.
- **Scoped OAuth**: Each tool module requests only the minimum OAuth scopes it needs.
- **No PII in logs**: Following Vopak security standards.

## License

MIT
