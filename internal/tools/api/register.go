// Package api registers the 3 Workspace API bridge tools.
package api

import (
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/middleware"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
)

// Register adds all 3 API bridge tools to the MCP server.
func Register(s *mcp.Server, clients *workspace.Clients) {
	mcp.AddTool(s, &mcp.Tool{
		Name:        "api_read",
		Description: "Generic Google Workspace API read operation. Sends a GET request to any Workspace REST endpoint. Use this for operations not covered by granular tools: reading speaker notes, listing Gmail messages, fetching Calendar events. Specify the full API path (e.g. 'gmail/v1/users/me/messages').",
	}, middleware.Wrap("api_read", handleRead(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "api_write",
		Description: "Generic Google Workspace API write operation. Sends a POST/PUT/PATCH request to any Workspace REST endpoint. Use this for operations not covered by granular tools: updating speaker notes, creating Calendar events, sending Gmail drafts. Specify the full API path, HTTP method, and JSON body.",
	}, middleware.Wrap("api_write", handleWrite(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "api_delete",
		Description: "DESTRUCTIVE: Generic Google Workspace API delete operation. Sends a DELETE request to any Workspace REST endpoint. This action cannot be undone. Specify the full API path.",
	}, middleware.Wrap("api_delete", handleDelete(clients)))
}
