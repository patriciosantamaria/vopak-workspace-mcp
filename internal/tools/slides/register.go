// Package slides registers all 14 Slides MCP tools.
package slides

import (
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/middleware"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
)

// Register adds all 14 Slides tools to the MCP server.
func Register(s *mcp.Server, clients *workspace.Clients) {
	// --- Read tools ---

	mcp.AddTool(s, &mcp.Tool{
		Name:        "slides_get_content",
		Description: "Read the full content of a specific slide, including text, images, tables, and shapes. Set include_styles=true to also return font, color, and size metadata for each text run.",
	}, middleware.Wrap("slides_get_content", handleGetContent(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "slides_get_thumbnail",
		Description: "Get a thumbnail image URL for a specific slide. Returns a short-lived URL that can be used to preview the slide visually.",
	}, middleware.Wrap("slides_get_thumbnail", handleGetThumbnail(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "slides_search_text",
		Description: "Search for text across all slides in a presentation. Returns matching slide indices, element IDs, and surrounding context for each match.",
	}, middleware.Wrap("slides_search_text", handleSearchText(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "slides_list",
		Description: "List all slides in a presentation with their index, object ID, and layout name. Use this to enumerate slides before operating on them.",
	}, middleware.Wrap("slides_list", handleList(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "slides_read_table",
		Description: "Read the structure and content of a table on a slide. Returns rows, columns, and the text content of each cell. Use table_index to select which table (0-based) when a slide has multiple tables.",
	}, middleware.Wrap("slides_read_table", handleReadTable(clients)))

	// --- Write tools ---

	mcp.AddTool(s, &mcp.Tool{
		Name:        "slides_add",
		Description: "Add a new blank slide to the presentation. Specify an optional layout name (e.g. 'TITLE_AND_BODY', 'BLANK') and insertion index.",
	}, middleware.Wrap("slides_add", handleAdd(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "slides_duplicate",
		Description: "Duplicate an existing slide by its object ID. The copy is inserted immediately after the original. Returns the new slide's object ID.",
	}, middleware.Wrap("slides_duplicate", handleDuplicate(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "slides_reorder",
		Description: "Move one or more slides to a new position. Specify slide object IDs and the target insertion index (0-based).",
	}, middleware.Wrap("slides_reorder", handleReorder(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "slides_replace_text",
		Description: "Find and replace text in a presentation. Accepts a single replacement or an array of {find, replace} pairs for bulk operations. Replacements inherit the formatting of the matched text.",
	}, middleware.Wrap("slides_replace_text", handleReplaceText(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "slides_insert_image",
		Description: "Insert an image into a slide. Provide a publicly accessible image URL and optional position/size in EMU (1 px = 9525 EMU). If element_id is provided, the image replaces that element.",
	}, middleware.Wrap("slides_insert_image", handleInsertImage(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "slides_update_cell",
		Description: "Update the text content of a specific cell in a table on a slide. Specify the table element ID, row index, and column index (all 0-based).",
	}, middleware.Wrap("slides_update_cell", handleUpdateCell(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "slides_insert_chart",
		Description: "Generate a chart image using QuickChart.io and insert it into a slide. Provide a Chart.js configuration object, chart type (bar, line, pie, doughnut, radar), and optional position/size.",
	}, middleware.Wrap("slides_insert_chart", handleInsertChart(clients)))

	// --- Destructive tools ---

	mcp.AddTool(s, &mcp.Tool{
		Name:        "slides_delete",
		Description: "DESTRUCTIVE: Delete a slide from the presentation by its object ID. This action cannot be undone.",
	}, middleware.Wrap("slides_delete", handleDelete(clients)))

	// --- Batch escape hatch ---

	mcp.AddTool(s, &mcp.Tool{
		Name:        "slides_batch_update",
		Description: "Raw Slides API BatchUpdate escape hatch. Send an array of API request objects directly. Use this for advanced operations not covered by other tools: CreateTable, CreateShape, UpdatePageProperties (background), CreateSheetsChart (embed linked chart). See tool_guard skill for examples.",
	}, middleware.Wrap("slides_batch_update", handleBatchUpdate(clients)))
}
