// Package docs registers all 12 Docs MCP tools.
package docs

import (
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/middleware"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
)

// Register adds all 12 Docs tools to the MCP server.
func Register(s *mcp.Server, clients *workspace.Clients) {
	// --- Read tools ---

	mcp.AddTool(s, &mcp.Tool{
		Name:        "docs_read_text",
		Description: "Read the text content of a Google Doc. Returns the full body text with paragraph breaks preserved. Optionally specify a start and end index to read a range.",
	}, middleware.Wrap("docs_read_text", handleReadText(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "docs_get_structure",
		Description: "Get the structural elements of a Google Doc: headings, paragraphs, tables, lists, and their indices. Use this to understand the document layout before making targeted edits.",
	}, middleware.Wrap("docs_get_structure", handleGetStructure(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "docs_search_text",
		Description: "Search for text in a Google Doc. Returns all matches with their start/end indices and surrounding context.",
	}, middleware.Wrap("docs_search_text", handleSearchText(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "docs_read_table",
		Description: "Read the structure and content of a table in a Google Doc. Returns rows, columns, and the text content of each cell. Use table_index (0-based) to select which table.",
	}, middleware.Wrap("docs_read_table", handleReadTable(clients)))

	// --- Write tools ---

	mcp.AddTool(s, &mcp.Tool{
		Name:        "docs_insert_text",
		Description: "Insert text at a specific position in a Google Doc. Specify the character index where text should be inserted. Use docs_get_structure to find the right index.",
	}, middleware.Wrap("docs_insert_text", handleInsertText(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "docs_replace_text",
		Description: "Find and replace text throughout a Google Doc. Replaces all occurrences of the search text with the replacement text. Supports case-sensitive matching.",
	}, middleware.Wrap("docs_replace_text", handleReplaceText(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "docs_set_style",
		Description: "Apply text formatting to a range in a Google Doc. Supports font family, font size, bold, italic, underline, foreground color, and background color. Specify start_index and end_index for the target range.",
	}, middleware.Wrap("docs_set_style", handleSetStyle(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "docs_insert_image",
		Description: "Insert an inline image into a Google Doc at a specific position. Provide a publicly accessible image URL and the character index for insertion.",
	}, middleware.Wrap("docs_insert_image", handleInsertImage(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "docs_update_cell",
		Description: "Update the text content of a specific cell in a table in a Google Doc. Specify table_index, row_index, and col_index (all 0-based).",
	}, middleware.Wrap("docs_update_cell", handleUpdateCell(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "docs_add_table_row",
		Description: "Add a new row to an existing table in a Google Doc. Specify table_index and optionally the row_index to insert at (default: append). Provide cell values as an array of strings.",
	}, middleware.Wrap("docs_add_table_row", handleAddTableRow(clients)))

	mcp.AddTool(s, &mcp.Tool{
		Name:        "docs_insert_table",
		Description: "Create a new table at a specific position in a Google Doc. Specify the number of rows, columns, and the character index for insertion.",
	}, middleware.Wrap("docs_insert_table", handleInsertTable(clients)))

	// --- Batch escape hatch ---

	mcp.AddTool(s, &mcp.Tool{
		Name:        "docs_batch_update",
		Description: "Raw Docs API BatchUpdate escape hatch. Send an array of API request objects directly. Use this for advanced operations not covered by other tools: InsertPageBreak, UpdateSectionStyle, CreateHeader, CreateFooter. See tool_guard skill for examples.",
	}, middleware.Wrap("docs_batch_update", handleBatchUpdate(clients)))
}
