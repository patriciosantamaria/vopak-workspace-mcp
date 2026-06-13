// Package main is the entry point for the Vopak Workspace MCP Server.
// It starts an MCP server exposing Google Workspace tools (Slides, Docs, Sheets, Drive, Branded, API bridge)
// via the Model Context Protocol using stdio transport.
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/middleware"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/tools/api"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/tools/branded"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/tools/docs"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/tools/drive"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/tools/sheets"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/tools/slides"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
)

const (
	serverName    = "vopak-workspace-mcp"
	serverVersion = "2.0.0"
)

func main() {
	// CLI flags
	serverGroup := flag.String("server", "", "Server group to run: slides, docs, sheets, drive, branded, api (required)")
	flag.Parse()

	if *serverGroup == "" {
		fmt.Fprintln(os.Stderr, "Error: --server flag is required (slides|docs|sheets|drive|branded|api)")
		flag.Usage()
		os.Exit(1)
	}

	// Create shared API clients (lazily initialized per scope)
	clients := workspace.NewClients()

	// Create MCP server
	server := mcp.NewServer(&mcp.Implementation{
		Name:    fmt.Sprintf("workspace-%s", *serverGroup),
		Version: serverVersion,
	}, nil)

	// Register tools based on server group
	switch *serverGroup {
	case "slides":
		slides.Register(server, clients)
	case "docs":
		docs.Register(server, clients)
	case "sheets":
		sheets.Register(server, clients)
	case "drive":
		drive.Register(server, clients)
	case "branded":
		branded.Register(server, clients)
	case "api":
		api.Register(server, clients)
	default:
		fmt.Fprintf(os.Stderr, "Error: unknown server group %q\n", *serverGroup)
		os.Exit(1)
	}

	// Context with signal handling
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	// Start server via stdio
	middleware.LogInfo("main", fmt.Sprintf("Starting %s server (v%s) via stdio...", *serverGroup, serverVersion))
	if err := server.Run(ctx, &mcp.StdioTransport{}); err != nil {
		middleware.LogError("main", fmt.Sprintf("Server error: %v", err))
		os.Exit(1)
	}
}
