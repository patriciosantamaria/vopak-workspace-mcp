package slides

import (
	"context"
	"fmt"
	"net/url"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
)

// InsertChartArgs are the arguments for the slides_insert_chart tool.
type InsertChartArgs struct {
	PresentationID string `json:"presentation_id" jsonschema:"description=The ID of the presentation"`
	SlideObjectID  string `json:"slide_object_id" jsonschema:"description=The object ID of the slide to insert the chart into"`
	ChartType      string `json:"chart_type" jsonschema:"description=Type of chart: bar, line, pie, doughnut, or radar"`
	ChartConfig    string `json:"chart_config" jsonschema:"description=Chart.js configuration as a JSON string"`
	Width          int64  `json:"width,omitempty" jsonschema:"description=Width in EMU (1 px = 9525 EMU). Optional"`
	Height         int64  `json:"height,omitempty" jsonschema:"description=Height in EMU (1 px = 9525 EMU). Optional"`
	TranslateX     int64  `json:"translate_x,omitempty" jsonschema:"description=Horizontal position offset in EMU. Optional"`
	TranslateY     int64  `json:"translate_y,omitempty" jsonschema:"description=Vertical position offset in EMU. Optional"`
}

// validChartTypes lists the allowed chart type values.
var validChartTypes = map[string]bool{
	"bar":      true,
	"line":     true,
	"pie":      true,
	"doughnut": true,
	"radar":    true,
}

func handleInsertChart(clients *workspace.Clients) mcp.ToolHandlerFor[InsertChartArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args InsertChartArgs) (*mcp.CallToolResult, any, error) {
		if args.PresentationID == "" {
			return agentresult.ErrorResult("presentation_id is required", "INVALID_ARGS")
		}
		if args.SlideObjectID == "" {
			return agentresult.ErrorResult("slide_object_id is required", "INVALID_ARGS")
		}
		if args.ChartConfig == "" {
			return agentresult.ErrorResult("chart_config is required", "INVALID_ARGS")
		}
		if !validChartTypes[args.ChartType] {
			return agentresult.ErrorResult(
				fmt.Sprintf("Invalid chart_type %q — must be one of: bar, line, pie, doughnut, radar", args.ChartType),
				"INVALID_ARGS",
			)
		}

		svc, err := clients.Slides(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Slides client: "+err.Error(), "AUTH_FAILED")
		}

		// Build the QuickChart.io URL from the Chart.js config.
		chartURL := fmt.Sprintf(
			"https://quickchart.io/chart?c=%s&w=800&h=600&bkg=transparent",
			url.QueryEscape(args.ChartConfig),
		)

		// Reuse the image insertion logic via InsertImageArgs.
		imageArgs := InsertImageArgs{
			PresentationID: args.PresentationID,
			SlideObjectID:  args.SlideObjectID,
			ImageURL:       chartURL,
			Width:          args.Width,
			Height:         args.Height,
			TranslateX:     args.TranslateX,
			TranslateY:     args.TranslateY,
		}

		imageID, err := insertImageIntoSlide(ctx, svc, imageArgs)
		if err != nil {
			return agentresult.ErrorResult(fmt.Sprintf("Failed to insert chart: %v", err), "API_ERROR")
		}

		return agentresult.SuccessResult("Chart inserted", map[string]any{
			"chart_image_element_id": imageID,
			"chart_type":             args.ChartType,
			"quickchart_url":         chartURL,
		})
	}
}
