package slides

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/middleware"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
	slidesapi "google.golang.org/api/slides/v1"
)

// ---------------------------------------------------------------------------
// slides_read_table
// ---------------------------------------------------------------------------

// ReadTableArgs defines the input for the slides_read_table tool.
type ReadTableArgs struct {
	PresentationID string `json:"presentation_id" jsonschema:"The ID of the Google Slides presentation"`
	SlideIndex     int    `json:"slide_index"      jsonschema:"Zero-based index of the slide containing the table"`
	TableIndex     int    `json:"table_index"       jsonschema:"Zero-based index of the table on the slide (use 0 for the first table)"`
}


// ReadTableResult is the response from slides_read_table.
type ReadTableResult struct {
	SlideIndex int          `json:"slide_index"`
	TableID    string       `json:"table_id"`
	Rows       int64        `json:"rows"`
	Cols       int64        `json:"cols"`
	Cells      [][]string   `json:"cells"`
}

func handleReadTable(clients *workspace.Clients) mcp.ToolHandlerFor[ReadTableArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args ReadTableArgs) (*mcp.CallToolResult, any, error) {
		start := time.Now()

		svc, err := clients.Slides(ctx)
		if err != nil {
			middleware.LogErrorWithCode("slides_read_table", "auth failed", "AUTH_FAILED")
			return agentresult.ErrorResult("Failed to initialize Slides client: "+err.Error(), "AUTH_FAILED")
		}

		pres, err := svc.Presentations.Get(args.PresentationID).Do()
		if err != nil {
			middleware.LogErrorWithCode("slides_read_table", "API call failed: "+err.Error(), "API_ERROR")
			return agentresult.ErrorResult("Failed to get presentation: "+err.Error(), "API_ERROR")
		}

		if args.SlideIndex < 0 || args.SlideIndex >= len(pres.Slides) {
			return agentresult.ErrorResult(
				fmt.Sprintf("slide_index %d is out of range — presentation has %d slides (0-%d)",
					args.SlideIndex, len(pres.Slides), len(pres.Slides)-1),
				"INVALID_ARGS",
			)
		}

		slide := pres.Slides[args.SlideIndex]
		tables := findTables(slide.PageElements)

		if len(tables) == 0 {
			return agentresult.ErrorResult(
				fmt.Sprintf("slide %d has no tables", args.SlideIndex),
				"NOT_FOUND",
			)
		}
		if args.TableIndex < 0 || args.TableIndex >= len(tables) {
			return agentresult.ErrorResult(
				fmt.Sprintf("table_index %d is out of range — slide has %d tables (0-%d)",
					args.TableIndex, len(tables), len(tables)-1),
				"INVALID_ARGS",
			)
		}

		tablePE := tables[args.TableIndex]
		table := tablePE.Table

		rows := table.Rows
		cols := table.Columns
		cells := make([][]string, rows)

		for r := int64(0); r < rows; r++ {
			cells[r] = make([]string, cols)
			if int(r) < len(table.TableRows) {
				row := table.TableRows[r]
				for c := int64(0); c < cols; c++ {
					if int(c) < len(row.TableCells) {
						cells[r][c] = extractCellText(row.TableCells[c])
					}
				}
			}
		}

		result := ReadTableResult{
			SlideIndex: args.SlideIndex,
			TableID:    tablePE.ObjectId,
			Rows:       rows,
			Cols:       cols,
			Cells:      cells,
		}

		middleware.LogWithDuration("slides_read_table",
			fmt.Sprintf("read table %d (%dx%d) on slide %d", args.TableIndex, rows, cols, args.SlideIndex),
			time.Since(start))

		return agentresult.SuccessResult(
			fmt.Sprintf("Read table with %d rows × %d columns", rows, cols),
			result,
		)
	}
}

// findTables returns all PageElements that contain a Table on a slide.
func findTables(elements []*slidesapi.PageElement) []*slidesapi.PageElement {
	var tables []*slidesapi.PageElement
	for _, pe := range elements {
		if pe.Table != nil {
			tables = append(tables, pe)
		}
		// Also search inside groups.
		if pe.ElementGroup != nil {
			nested := findTables(pe.ElementGroup.Children)
			tables = append(tables, nested...)
		}
	}
	return tables
}

// extractCellText concatenates all text runs in a table cell.
func extractCellText(cell *slidesapi.TableCell) string {
	if cell.Text == nil {
		return ""
	}
	var sb strings.Builder
	for _, te := range cell.Text.TextElements {
		if te.TextRun != nil {
			sb.WriteString(te.TextRun.Content)
		}
	}
	return strings.TrimRight(sb.String(), "\n")
}

// ---------------------------------------------------------------------------
// slides_update_cell
// ---------------------------------------------------------------------------

// UpdateCellArgs defines the input for the slides_update_cell tool.
type UpdateCellArgs struct {
	PresentationID string `json:"presentation_id" jsonschema:"The ID of the Google Slides presentation"`
	TableID        string `json:"table_id"         jsonschema:"The object ID of the table element on the slide"`
	RowIndex       int    `json:"row_index"         jsonschema:"Zero-based row index of the cell to update"`
	ColIndex       int    `json:"col_index"         jsonschema:"Zero-based column index of the cell to update"`
	Text           string `json:"text"              jsonschema:"The new text content for the cell"`
}

// UpdateCellResult confirms the cell update.
type UpdateCellResult struct {
	TableID  string `json:"table_id"`
	RowIndex int    `json:"row_index"`
	ColIndex int    `json:"col_index"`
	NewText  string `json:"new_text"`
}

func handleUpdateCell(clients *workspace.Clients) mcp.ToolHandlerFor[UpdateCellArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args UpdateCellArgs) (*mcp.CallToolResult, any, error) {
		start := time.Now()

		svc, err := clients.Slides(ctx)
		if err != nil {
			middleware.LogErrorWithCode("slides_update_cell", "auth failed", "AUTH_FAILED")
			return agentresult.ErrorResult("Failed to initialize Slides client: "+err.Error(), "AUTH_FAILED")
		}

		if args.TableID == "" {
			return agentresult.ErrorResult("table_id must not be empty", "INVALID_ARGS")
		}
		if args.RowIndex < 0 {
			return agentresult.ErrorResult("row_index must be >= 0", "INVALID_ARGS")
		}
		if args.ColIndex < 0 {
			return agentresult.ErrorResult("col_index must be >= 0", "INVALID_ARGS")
		}

		cellLocation := &slidesapi.TableCellLocation{
			RowIndex:    int64(args.RowIndex),
			ColumnIndex: int64(args.ColIndex),
		}

		// Build batch: first delete all existing text, then insert new text.
		requests := []*slidesapi.Request{
			{
				DeleteText: &slidesapi.DeleteTextRequest{
					ObjectId: args.TableID,
					CellLocation: cellLocation,
					TextRange: &slidesapi.Range{
						Type: "ALL",
					},
				},
			},
		}

		// Only insert text if the replacement string is non-empty.
		if args.Text != "" {
			requests = append(requests, &slidesapi.Request{
				InsertText: &slidesapi.InsertTextRequest{
					ObjectId:       args.TableID,
					CellLocation:   cellLocation,
					Text:           args.Text,
					InsertionIndex: 0,
				},
			})
		}

		_, err = svc.Presentations.BatchUpdate(args.PresentationID, &slidesapi.BatchUpdatePresentationRequest{
			Requests: requests,
		}).Do()
		if err != nil {
			middleware.LogErrorWithCode("slides_update_cell", "batch update failed: "+err.Error(), "API_ERROR")
			return agentresult.ErrorResult("Failed to update cell: "+err.Error(), "API_ERROR")
		}

		result := UpdateCellResult{
			TableID:  args.TableID,
			RowIndex: args.RowIndex,
			ColIndex: args.ColIndex,
			NewText:  args.Text,
		}

		middleware.LogWithDuration("slides_update_cell",
			fmt.Sprintf("updated cell [%d,%d] in table %s", args.RowIndex, args.ColIndex, args.TableID),
			time.Since(start))

		return agentresult.SuccessResult(
			fmt.Sprintf("Updated cell [%d,%d] in table %s", args.RowIndex, args.ColIndex, args.TableID),
			result,
		)
	}
}
