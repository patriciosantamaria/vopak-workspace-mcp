---
name: setup-guide
description: "Setup guide for installing and configuring the vopak-workspace-mcp Go MCP server. Use when a developer needs to set up the Workspace MCP tools for the first time."
---

# Workspace MCP Setup

This skill guides developers through installing and configuring the `vopak-workspace-mcp` Go MCP server for use with Google Antigravity.

## Prerequisites

- Docker and Docker Compose installed
- Google Cloud project with Workspace APIs enabled
- Service Account with Domain-Wide Delegation (for production) or ADC (for development)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/patriciosantamaria/vopak-workspace-mcp.git
cd vopak-workspace-mcp
```

### 2. Build and Start the Docker Container

```bash
docker compose up -d --build
```

### 3. Register in Antigravity

Add the following entry to your `~/.gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "workspace-slides": {
      "command": "docker",
      "args": ["exec", "-i", "vopak-workspace-mcp", "/app/server", "--transport", "stdio", "--server", "slides"]
    }
  }
}
```

Repeat for each server: `slides`, `docs`, `sheets`, `drive`, `branded`, `api`.

### 4. Install the Plugin

Symlink or copy the `plugin/` directory to your Antigravity plugins:

```bash
ln -s $(pwd)/plugin ~/.gemini/config/plugins/vopak-workspace
```

### 5. Verify

Open Antigravity IDE and check that the Workspace MCP tools appear in your tool list.

## Authentication

### Development (ADC)

```bash
gcloud auth application-default login
```

Mount credentials into Docker via volumes in `docker-compose.yml`.

### Production (Domain-Wide Delegation)

Set `GOOGLE_APPLICATION_CREDENTIALS` to point to your service account key. The server will impersonate users via the `subject` parameter.
