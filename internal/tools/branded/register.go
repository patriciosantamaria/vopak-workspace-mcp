// Package branded registers all 3 Branded MCP tools and the template registry.
package branded

import (
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/middleware"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
)

// Register adds all 3 Branded tools to the MCP server.
func Register(s *mcp.Server, clients *workspace.Clients) {
	mcp.AddTool(s, &mcp.Tool{
		Name:        "branded_create_presentation",
		Description: "Create a new Vopak-branded presentation from a corporate template. Copies the template, fills title/subtitle/date placeholders, and returns the new presentation URL. All formatting and branding is inherited from the template.",
	}, middleware.Wrap("branded_create_presentation", handleCreatePresentation(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "branded_create_document",
		Description: "Create a new Vopak-branded document from a corporate template. Copies the template (including 3-page front-matter: cover, admin block, TOC), fills metadata placeholders, and returns the new document URL. Specify template_key to select the document type (e.g. doc_add, doc_guideline, doc_policy).",
	}, middleware.Wrap("branded_create_document", handleCreateDocument(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "branded_health_check",
		Description: "Verify the MCP server environment: ADC credentials, Google API access, template folder access, and Docker container health. Returns a detailed status report.",
	}, middleware.Wrap("branded_health_check", handleHealthCheck(clients)))
}
