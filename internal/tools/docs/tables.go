package docs

import (
	"context"
	"fmt"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
	docsapi "google.golang.org/api/docs/v1"
)

type ReadTableArgs struct {
	DocumentID string `json:"document_id" jsonschema:"description=Google Doc ID"`
	TableIndex int    `json:"table_index" jsonschema:"description=Which table (0-based index)"`
}

type UpdateCellArgs struct {
	DocumentID string `json:"document_id" jsonschema:"description=Google Doc ID"`
	TableIndex int    `json:"table_index" jsonschema:"description=Which table (0-based)"`
	RowIndex   int    `json:"row_index" jsonschema:"description=Row index (0-based)"`
	ColIndex   int    `json:"col_index" jsonschema:"description=Column index (0-based)"`
	Text       string `json:"text" jsonschema:"description=New cell text"`
}

type AddTableRowArgs struct {
	DocumentID string   `json:"document_id" jsonschema:"description=Google Doc ID"`
	TableIndex int      `json:"table_index" jsonschema:"description=Which table (0-based)"`
	RowIndex   int      `json:"row_index,omitempty" jsonschema:"description=Row to insert at (-1 = append)"`
	Values     []string `json:"values" jsonschema:"description=Cell values for the new row"`
}

type InsertTableArgs struct {
	DocumentID  string `json:"document_id" jsonschema:"description=Google Doc ID"`
	Rows        int    `json:"rows" jsonschema:"description=Number of rows"`
	Columns     int    `json:"columns" jsonschema:"description=Number of columns"`
	InsertIndex int    `json:"insert_index" jsonschema:"description=Character index for table insertion"`
}

// findTables returns all table elements from a doc body.
func findTables(doc *docsapi.Document) []*docsapi.Table {
	var tables []*docsapi.Table
	for _, elem := range doc.Body.Content {
		if elem.Table != nil {
			tables = append(tables, elem.Table)
		}
	}
	return tables
}

// extractCellText extracts the text from a table cell.
func extractCellText(cell *docsapi.TableCell) string {
	var sb strings.Builder
	for _, elem := range cell.Content {
		if elem.Paragraph != nil {
			for _, pe := range elem.Paragraph.Elements {
				if pe.TextRun != nil {
					sb.WriteString(pe.TextRun.Content)
				}
			}
		}
	}
	return strings.TrimSuffix(sb.String(), "\n")
}

func handleReadTable(clients *workspace.Clients) mcp.ToolHandlerFor[ReadTableArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args ReadTableArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Docs(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Docs client: "+err.Error(), "AUTH_FAILED")
		}
		doc, err := svc.Documents.Get(args.DocumentID).Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to get document: "+err.Error(), "API_ERROR")
		}

		tables := findTables(doc)
		if args.TableIndex >= len(tables) {
			return agentresult.ErrorResult(fmt.Sprintf("Table index %d out of range (document has %d tables)", args.TableIndex, len(tables)), "NOT_FOUND")
		}
		table := tables[args.TableIndex]

		rows := make([][]string, 0, len(table.TableRows))
		for _, row := range table.TableRows {
			cells := make([]string, 0, len(row.TableCells))
			for _, cell := range row.TableCells {
				cells = append(cells, extractCellText(cell))
			}
			rows = append(rows, cells)
		}

		return agentresult.SuccessResult(fmt.Sprintf("Table has %d rows × %d columns", len(rows), table.Columns), map[string]any{
			"rows": len(rows), "columns": table.Columns, "data": rows,
		})
	}
}

func handleUpdateCell(clients *workspace.Clients) mcp.ToolHandlerFor[UpdateCellArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args UpdateCellArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Docs(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Docs client: "+err.Error(), "AUTH_FAILED")
		}
		doc, err := svc.Documents.Get(args.DocumentID).Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to get document: "+err.Error(), "API_ERROR")
		}

		tables := findTables(doc)
		if args.TableIndex >= len(tables) {
			return agentresult.ErrorResult(fmt.Sprintf("Table index %d out of range", args.TableIndex), "NOT_FOUND")
		}
		table := tables[args.TableIndex]
		if args.RowIndex >= len(table.TableRows) {
			return agentresult.ErrorResult(fmt.Sprintf("Row index %d out of range", args.RowIndex), "INVALID_ARGS")
		}
		row := table.TableRows[args.RowIndex]
		if args.ColIndex >= len(row.TableCells) {
			return agentresult.ErrorResult(fmt.Sprintf("Column index %d out of range", args.ColIndex), "INVALID_ARGS")
		}
		cell := row.TableCells[args.ColIndex]

		// Find cell content range
		requests := []*docsapi.Request{}

		// Delete existing cell content (if any text exists)
		if len(cell.Content) > 0 {
			// Cell content starts after the cell's first paragraph start
			first := cell.Content[0]
			last := cell.Content[len(cell.Content)-1]
			contentStart := first.StartIndex + 1 // skip the paragraph marker
			contentEnd := last.EndIndex - 1       // leave the trailing newline
			if contentEnd > contentStart {
				requests = append(requests, &docsapi.Request{
					DeleteContentRange: &docsapi.DeleteContentRangeRequest{
						Range: &docsapi.Range{
							StartIndex:      contentStart,
							EndIndex:        contentEnd,
							SegmentId:       "",
						},
					},
				})
			}
		}

		// Insert new text at cell start
		insertIndex := cell.Content[0].StartIndex + 1
		if args.Text != "" {
			requests = append(requests, &docsapi.Request{
				InsertText: &docsapi.InsertTextRequest{
					Text:     args.Text,
					Location: &docsapi.Location{Index: insertIndex},
				},
			})
		}

		if len(requests) > 0 {
			_, err = svc.Documents.BatchUpdate(args.DocumentID, &docsapi.BatchUpdateDocumentRequest{
				Requests: requests,
			}).Do()
			if err != nil {
				return agentresult.ErrorResult("Failed to update cell: "+err.Error(), "API_ERROR")
			}
		}

		return agentresult.SuccessResult(fmt.Sprintf("Updated cell [%d,%d] in table %d", args.RowIndex, args.ColIndex, args.TableIndex), nil)
	}
}

func handleAddTableRow(clients *workspace.Clients) mcp.ToolHandlerFor[AddTableRowArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args AddTableRowArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Docs(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Docs client: "+err.Error(), "AUTH_FAILED")
		}
		doc, err := svc.Documents.Get(args.DocumentID).Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to get document: "+err.Error(), "API_ERROR")
		}

		tables := findTables(doc)
		if args.TableIndex >= len(tables) {
			return agentresult.ErrorResult(fmt.Sprintf("Table index %d out of range", args.TableIndex), "NOT_FOUND")
		}
		table := tables[args.TableIndex]

		rowIdx := args.RowIndex
		if rowIdx < 0 || rowIdx >= len(table.TableRows) {
			rowIdx = len(table.TableRows) - 1 // append after last row
		}

		// Find the table start index for the row insertion
		targetRow := table.TableRows[rowIdx]
		insertBelow := true

		requests := []*docsapi.Request{{
			InsertTableRow: &docsapi.InsertTableRowRequest{
				TableCellLocation: &docsapi.TableCellLocation{
					TableStartLocation: &docsapi.Location{Index: targetRow.TableCells[0].Content[0].StartIndex - 2},
					RowIndex:           int64(rowIdx),
					ColumnIndex:        0,
				},
				InsertBelow: insertBelow,
			},
		}}

		_, err = svc.Documents.BatchUpdate(args.DocumentID, &docsapi.BatchUpdateDocumentRequest{
			Requests: requests,
		}).Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to add table row: "+err.Error(), "API_ERROR")
		}

		return agentresult.SuccessResult(fmt.Sprintf("Added row to table %d", args.TableIndex), nil)
	}
}

func handleInsertTable(clients *workspace.Clients) mcp.ToolHandlerFor[InsertTableArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args InsertTableArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Docs(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Docs client: "+err.Error(), "AUTH_FAILED")
		}

		requests := []*docsapi.Request{{
			InsertTable: &docsapi.InsertTableRequest{
				Rows:     int64(args.Rows),
				Columns:  int64(args.Columns),
				Location: &docsapi.Location{Index: int64(args.InsertIndex)},
			},
		}}

		_, err = svc.Documents.BatchUpdate(args.DocumentID, &docsapi.BatchUpdateDocumentRequest{
			Requests: requests,
		}).Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to insert table: "+err.Error(), "API_ERROR")
		}

		return agentresult.SuccessResult(fmt.Sprintf("Inserted %dx%d table at index %d", args.Rows, args.Columns, args.InsertIndex), nil)
	}
}
