// Package drive registers all 2 Drive MCP tools.
package drive

import (
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/middleware"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
)

// Register adds all 2 Drive tools to the MCP server.
func Register(s *mcp.Server, clients *workspace.Clients) {
	mcp.AddTool(s, &mcp.Tool{
		Name:        "drive_list",
		Description: "Search and list files in Google Drive. Supports query filters by name, MIME type, folder, and modification date. Returns file ID, name, MIME type, and web link for each result.",
	}, middleware.Wrap("drive_list", handleList(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "drive_create_folders",
		Description: "Create a folder structure in Google Drive. Specify a path like 'Projects/2025/Q1' and the parent folder ID. Creates all intermediate folders that don't exist. Returns the final folder ID.",
	}, middleware.Wrap("drive_create_folders", handleCreateFolders(clients)))
}
