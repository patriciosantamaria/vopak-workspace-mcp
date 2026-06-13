package sheets

import (
	"context"
	"fmt"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
	sheetsapi "google.golang.org/api/sheets/v4"
)

type WriteDataArgs struct {
	SpreadsheetID string          `json:"spreadsheet_id" jsonschema:"description=Google Spreadsheet ID"`
	Range         string          `json:"range" jsonschema:"description=A1 notation target range"`
	Values        [][]interface{} `json:"values" jsonschema:"description=2D array of values to write"`
}

type CreateChartArgs struct {
	SpreadsheetID string `json:"spreadsheet_id" jsonschema:"description=Google Spreadsheet ID"`
	SheetID       int64  `json:"sheet_id" jsonschema:"description=Sheet ID (tab) to create the chart on"`
	ChartType     string `json:"chart_type" jsonschema:"description=Chart type: BAR LINE PIE COLUMN AREA"`
	DataRange     string `json:"data_range" jsonschema:"description=A1 notation range containing chart data"`
	Title         string `json:"title,omitempty" jsonschema:"description=Optional chart title"`
}

func handleWriteData(clients *workspace.Clients) mcp.ToolHandlerFor[WriteDataArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args WriteDataArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Sheets(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Sheets client: "+err.Error(), "AUTH_FAILED")
		}
		vr := &sheetsapi.ValueRange{Values: args.Values}
		resp, err := svc.Spreadsheets.Values.Update(args.SpreadsheetID, args.Range, vr).ValueInputOption("USER_ENTERED").Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to write data: "+err.Error(), "API_ERROR")
		}
		return agentresult.SuccessResult(fmt.Sprintf("Updated %d cells in %s", resp.UpdatedCells, args.Range), map[string]any{
			"updated_cells": resp.UpdatedCells, "updated_range": resp.UpdatedRange,
		})
	}
}

func handleCreateChart(clients *workspace.Clients) mcp.ToolHandlerFor[CreateChartArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args CreateChartArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Sheets(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Sheets client: "+err.Error(), "AUTH_FAILED")
		}

		chartTypeMap := map[string]string{
			"BAR": "BAR", "LINE": "LINE", "PIE": "PIE", "COLUMN": "COLUMN", "AREA": "AREA",
		}
		apiType, ok := chartTypeMap[strings.ToUpper(args.ChartType)]
		if !ok {
			return agentresult.ErrorResult(fmt.Sprintf("Unknown chart type %q — use BAR, LINE, PIE, COLUMN, or AREA", args.ChartType), "INVALID_ARGS")
		}

		addChart := &sheetsapi.AddChartRequest{
			Chart: &sheetsapi.EmbeddedChart{
				Spec: &sheetsapi.ChartSpec{
					Title: args.Title,
					BasicChart: &sheetsapi.BasicChartSpec{
						ChartType: apiType,
						Domains: []*sheetsapi.BasicChartDomain{{
							Domain: &sheetsapi.ChartData{
								SourceRange: &sheetsapi.ChartSourceRange{
									Sources: []*sheetsapi.GridRange{{SheetId: args.SheetID}},
								},
							},
						}},
					},
				},
				Position: &sheetsapi.EmbeddedObjectPosition{
					OverlayPosition: &sheetsapi.OverlayPosition{
						AnchorCell: &sheetsapi.GridCoordinate{SheetId: args.SheetID, RowIndex: 0, ColumnIndex: 0},
					},
				},
			},
		}

		batchReq := &sheetsapi.BatchUpdateSpreadsheetRequest{
			Requests: []*sheetsapi.Request{{AddChart: addChart}},
		}
		resp, err := svc.Spreadsheets.BatchUpdate(args.SpreadsheetID, batchReq).Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to create chart: "+err.Error(), "API_ERROR")
		}

		var chartID int64
		for _, reply := range resp.Replies {
			if reply.AddChart != nil {
				chartID = reply.AddChart.Chart.ChartId
			}
		}
		return agentresult.SuccessResult(fmt.Sprintf("Created %s chart (ID: %d)", apiType, chartID), map[string]any{"chart_id": chartID})
	}
}
