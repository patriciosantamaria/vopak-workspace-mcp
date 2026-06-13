package docs

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
	docsapi "google.golang.org/api/docs/v1"
)

type BatchUpdateArgs struct {
	DocumentID string `json:"document_id" jsonschema:"Google Doc ID"`
	Requests   string `json:"requests" jsonschema:"JSON array of Docs API request objects"`
}

func handleBatchUpdate(clients *workspace.Clients) mcp.ToolHandlerFor[BatchUpdateArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args BatchUpdateArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Docs(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Docs client: "+err.Error(), "AUTH_FAILED")
		}

		var requests []*docsapi.Request
		if err := json.Unmarshal([]byte(args.Requests), &requests); err != nil {
			return agentresult.ErrorResult("Invalid JSON in requests: "+err.Error(), "INVALID_ARGS")
		}

		resp, err := svc.Documents.BatchUpdate(args.DocumentID, &docsapi.BatchUpdateDocumentRequest{
			Requests: requests,
		}).Do()
		if err != nil {
			return agentresult.ErrorResult("BatchUpdate failed: "+err.Error(), "API_ERROR")
		}

		return agentresult.SuccessResult(fmt.Sprintf("BatchUpdate executed %d requests", len(requests)), map[string]any{
			"replies_count": len(resp.Replies),
		})
	}
}
