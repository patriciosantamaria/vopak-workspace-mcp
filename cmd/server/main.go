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
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
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
		registerSlidesTools(server, clients)
	case "docs":
		registerDocsTools(server, clients)
	case "sheets":
		registerSheetsTools(server, clients)
	case "drive":
		registerDriveTools(server, clients)
	case "branded":
		registerBrandedTools(server, clients)
	case "api":
		registerAPITools(server, clients)
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

// ---------------------------------------------------------------------------
// Placeholder registrations — each will be replaced by internal/tools/<group>/register.go
// as tool implementations are built during Phase 2.
// ---------------------------------------------------------------------------

// PingArgs is the empty argument struct for health check tools.
type PingArgs struct{}

func registerSlidesTools(s *mcp.Server, _ *workspace.Clients) {
	mcp.AddTool(s, &mcp.Tool{
		Name:        "slides_ping",
		Description: "Health check for the Slides MCP server",
	}, middleware.Wrap("slides_ping", func(ctx context.Context, req *mcp.CallToolRequest, args PingArgs) (*mcp.CallToolResult, any, error) {
		return agentresult.SuccessResult("workspace-slides server is healthy", nil)
	}))
}

func registerDocsTools(s *mcp.Server, _ *workspace.Clients) {
	mcp.AddTool(s, &mcp.Tool{
		Name:        "docs_ping",
		Description: "Health check for the Docs MCP server",
	}, middleware.Wrap("docs_ping", func(ctx context.Context, req *mcp.CallToolRequest, args PingArgs) (*mcp.CallToolResult, any, error) {
		return agentresult.SuccessResult("workspace-docs server is healthy", nil)
	}))
}

func registerSheetsTools(s *mcp.Server, _ *workspace.Clients) {
	mcp.AddTool(s, &mcp.Tool{
		Name:        "sheets_ping",
		Description: "Health check for the Sheets MCP server",
	}, middleware.Wrap("sheets_ping", func(ctx context.Context, req *mcp.CallToolRequest, args PingArgs) (*mcp.CallToolResult, any, error) {
		return agentresult.SuccessResult("workspace-sheets server is healthy", nil)
	}))
}

func registerDriveTools(s *mcp.Server, _ *workspace.Clients) {
	mcp.AddTool(s, &mcp.Tool{
		Name:        "drive_ping",
		Description: "Health check for the Drive MCP server",
	}, middleware.Wrap("drive_ping", func(ctx context.Context, req *mcp.CallToolRequest, args PingArgs) (*mcp.CallToolResult, any, error) {
		return agentresult.SuccessResult("workspace-drive server is healthy", nil)
	}))
}

func registerBrandedTools(s *mcp.Server, _ *workspace.Clients) {
	mcp.AddTool(s, &mcp.Tool{
		Name:        "branded_ping",
		Description: "Health check for the Branded MCP server",
	}, middleware.Wrap("branded_ping", func(ctx context.Context, req *mcp.CallToolRequest, args PingArgs) (*mcp.CallToolResult, any, error) {
		return agentresult.SuccessResult("workspace-branded server is healthy", nil)
	}))
}

func registerAPITools(s *mcp.Server, _ *workspace.Clients) {
	mcp.AddTool(s, &mcp.Tool{
		Name:        "api_ping",
		Description: "Health check for the Workspace API bridge server",
	}, middleware.Wrap("api_ping", func(ctx context.Context, req *mcp.CallToolRequest, args PingArgs) (*mcp.CallToolResult, any, error) {
		return agentresult.SuccessResult("workspace-api server is healthy", nil)
	}))
}
