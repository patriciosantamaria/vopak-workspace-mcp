// Package sheets registers all 5 Sheets MCP tools.
package sheets

import (
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/middleware"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
)

// Register adds all 5 Sheets tools to the MCP server.
func Register(s *mcp.Server, clients *workspace.Clients) {
	mcp.AddTool(s, &mcp.Tool{
		Name:        "sheets_read_range",
		Description: "Read cell values from a specific range in a Google Sheet. Specify the range in A1 notation (e.g. 'Sheet1!A1:D10'). Returns a 2D array of cell values.",
	}, middleware.Wrap("sheets_read_range", handleReadRange(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "sheets_get_structure",
		Description: "Get the structure of a Google Spreadsheet: sheet names, row/column counts, and named ranges. Use this to discover available sheets before reading data.",
	}, middleware.Wrap("sheets_get_structure", handleGetStructure(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "sheets_verify_range",
		Description: "Verify that a range in a Google Sheet contains expected data. Checks that cells are non-empty and optionally validates against expected values. Returns a pass/fail report.",
	}, middleware.Wrap("sheets_verify_range", handleVerifyRange(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "sheets_write_data",
		Description: "Write data to a specific range in a Google Sheet. Provide a 2D array of values and the target range in A1 notation. Existing data in the range is overwritten.",
	}, middleware.Wrap("sheets_write_data", handleWriteData(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "sheets_create_chart",
		Description: "Create a chart in a Google Sheet from a data range. Specify chart type (BAR, LINE, PIE, COLUMN, AREA), data range, and optional title. The chart is embedded in the sheet.",
	}, middleware.Wrap("sheets_create_chart", handleCreateChart(clients)))
}
