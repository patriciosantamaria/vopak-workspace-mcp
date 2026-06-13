package slides

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
	"google.golang.org/api/slides/v1"
)

// ---------------------------------------------------------------------------
// slides_delete
// ---------------------------------------------------------------------------

// DeleteArgs are the arguments for the slides_delete tool.
type DeleteArgs struct {
	PresentationID string `json:"presentation_id" jsonschema:"The ID of the presentation"`
	SlideObjectID  string `json:"slide_object_id" jsonschema:"The object ID of the slide to delete"`
}

func handleDelete(clients *workspace.Clients) mcp.ToolHandlerFor[DeleteArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args DeleteArgs) (*mcp.CallToolResult, any, error) {
		if args.PresentationID == "" {
			return agentresult.ErrorResult("presentation_id is required", "INVALID_ARGS")
		}
		if args.SlideObjectID == "" {
			return agentresult.ErrorResult("slide_object_id is required", "INVALID_ARGS")
		}

		svc, err := clients.Slides(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Slides client: "+err.Error(), "AUTH_FAILED")
		}

		batchReq := &slides.BatchUpdatePresentationRequest{
			Requests: []*slides.Request{
				{
					DeleteObject: &slides.DeleteObjectRequest{
						ObjectId: args.SlideObjectID,
					},
				},
			},
		}

		_, err = svc.Presentations.BatchUpdate(args.PresentationID, batchReq).Context(ctx).Do()
		if err != nil {
			return agentresult.ErrorResult(fmt.Sprintf("Failed to delete slide: %v", err), "API_ERROR")
		}

		return agentresult.SuccessResult("Slide deleted", map[string]any{
			"deleted_slide_object_id": args.SlideObjectID,
		})
	}
}

// ---------------------------------------------------------------------------
// slides_batch_update
// ---------------------------------------------------------------------------

// BatchUpdateArgs are the arguments for the slides_batch_update escape hatch tool.
type BatchUpdateArgs struct {
	PresentationID string `json:"presentation_id" jsonschema:"The ID of the presentation"`
	Requests       string `json:"requests" jsonschema:"Raw JSON array of Slides API request objects"`
}

func handleBatchUpdate(clients *workspace.Clients) mcp.ToolHandlerFor[BatchUpdateArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args BatchUpdateArgs) (*mcp.CallToolResult, any, error) {
		if args.PresentationID == "" {
			return agentresult.ErrorResult("presentation_id is required", "INVALID_ARGS")
		}
		if args.Requests == "" {
			return agentresult.ErrorResult("requests JSON array is required", "INVALID_ARGS")
		}

		// Unmarshal the raw JSON into Slides API request objects.
		var apiRequests []*slides.Request
		if err := json.Unmarshal([]byte(args.Requests), &apiRequests); err != nil {
			return agentresult.ErrorResult(
				fmt.Sprintf("Failed to parse requests JSON: %v", err),
				"INVALID_ARGS",
			)
		}

		if len(apiRequests) == 0 {
			return agentresult.ErrorResult("requests array must contain at least one request", "INVALID_ARGS")
		}

		svc, err := clients.Slides(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Slides client: "+err.Error(), "AUTH_FAILED")
		}

		batchReq := &slides.BatchUpdatePresentationRequest{
			Requests: apiRequests,
		}

		resp, err := svc.Presentations.BatchUpdate(args.PresentationID, batchReq).Context(ctx).Do()
		if err != nil {
			return agentresult.ErrorResult(fmt.Sprintf("BatchUpdate failed: %v", err), "API_ERROR")
		}

		// Serialize the full response for the agent to inspect.
		respJSON, err := json.Marshal(resp)
		if err != nil {
			return agentresult.ErrorResult(fmt.Sprintf("Failed to marshal response: %v", err), "API_ERROR")
		}

		var responseData any
		if err := json.Unmarshal(respJSON, &responseData); err != nil {
			// Fallback: return the raw JSON string.
			return agentresult.SuccessResult(
				fmt.Sprintf("BatchUpdate executed %d request(s)", len(apiRequests)),
				map[string]any{"raw_response": string(respJSON)},
			)
		}

		return agentresult.SuccessResult(
			fmt.Sprintf("BatchUpdate executed %d request(s)", len(apiRequests)),
			map[string]any{
				"request_count": len(apiRequests),
				"response":      responseData,
			},
		)
	}
}
