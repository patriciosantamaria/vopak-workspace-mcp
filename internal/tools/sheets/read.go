package sheets

import (
	"context"
	"fmt"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
)

// --- Arg structs ---

type ReadRangeArgs struct {
	SpreadsheetID string `json:"spreadsheet_id" jsonschema:"description=Google Spreadsheet ID"`
	Range         string `json:"range" jsonschema:"description=A1 notation range (e.g. Sheet1!A1:D10)"`
}

type GetStructureArgs struct {
	SpreadsheetID string `json:"spreadsheet_id" jsonschema:"description=Google Spreadsheet ID"`
}

type VerifyRangeArgs struct {
	SpreadsheetID  string     `json:"spreadsheet_id" jsonschema:"description=Google Spreadsheet ID"`
	Range          string     `json:"range" jsonschema:"description=A1 notation range to verify"`
	ExpectedValues [][]string `json:"expected_values,omitempty" jsonschema:"description=Optional expected cell values for comparison"`
}

// --- Handlers ---

func handleReadRange(clients *workspace.Clients) mcp.ToolHandlerFor[ReadRangeArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args ReadRangeArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Sheets(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Sheets client: "+err.Error(), "AUTH_FAILED")
		}
		resp, err := svc.Spreadsheets.Values.Get(args.SpreadsheetID, args.Range).Do()
		if err != nil {
			return agentresult.ErrorResult(fmt.Sprintf("Failed to read range %s: %v", args.Range, err), "API_ERROR")
		}
		return agentresult.SuccessResult(fmt.Sprintf("Read %d rows from %s", len(resp.Values), args.Range), map[string]any{
			"range":  resp.Range,
			"values": resp.Values,
		})
	}
}

func handleGetStructure(clients *workspace.Clients) mcp.ToolHandlerFor[GetStructureArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args GetStructureArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Sheets(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Sheets client: "+err.Error(), "AUTH_FAILED")
		}
		ss, err := svc.Spreadsheets.Get(args.SpreadsheetID).Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to get spreadsheet: "+err.Error(), "API_ERROR")
		}
		type sheetInfo struct {
			Title    string `json:"title"`
			SheetID  int64  `json:"sheet_id"`
			Rows     int64  `json:"rows"`
			Columns  int64  `json:"columns"`
		}
		sheets := make([]sheetInfo, 0, len(ss.Sheets))
		for _, s := range ss.Sheets {
			info := sheetInfo{Title: s.Properties.Title, SheetID: s.Properties.SheetId}
			if s.Properties.GridProperties != nil {
				info.Rows = s.Properties.GridProperties.RowCount
				info.Columns = s.Properties.GridProperties.ColumnCount
			}
			sheets = append(sheets, info)
		}
		return agentresult.SuccessResult(fmt.Sprintf("Spreadsheet has %d sheets", len(sheets)), map[string]any{
			"title":  ss.Properties.Title,
			"sheets": sheets,
		})
	}
}

func handleVerifyRange(clients *workspace.Clients) mcp.ToolHandlerFor[VerifyRangeArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args VerifyRangeArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Sheets(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Sheets client: "+err.Error(), "AUTH_FAILED")
		}
		resp, err := svc.Spreadsheets.Values.Get(args.SpreadsheetID, args.Range).Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to read range: "+err.Error(), "API_ERROR")
		}

		emptyCells := 0
		totalCells := 0
		mismatches := []map[string]any{}

		for r, row := range resp.Values {
			for c, cell := range row {
				totalCells++
				cellStr := fmt.Sprintf("%v", cell)
				if cellStr == "" {
					emptyCells++
				}
				if args.ExpectedValues != nil && r < len(args.ExpectedValues) && c < len(args.ExpectedValues[r]) {
					if cellStr != args.ExpectedValues[r][c] {
						mismatches = append(mismatches, map[string]any{
							"row": r, "col": c, "expected": args.ExpectedValues[r][c], "actual": cellStr,
						})
					}
				}
			}
		}

		passed := emptyCells == 0 && len(mismatches) == 0
		return agentresult.SuccessResult(fmt.Sprintf("Verification %s: %d cells, %d empty, %d mismatches",
			map[bool]string{true: "PASSED", false: "FAILED"}[passed], totalCells, emptyCells, len(mismatches)),
			map[string]any{"passed": passed, "total_cells": totalCells, "empty_cells": emptyCells, "mismatches": mismatches})
	}
}
