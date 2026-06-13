package docs

import (
	"context"
	"fmt"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
)

type SearchTextArgs struct {
	DocumentID    string `json:"document_id" jsonschema:"Google Doc ID"`
	Query         string `json:"query" jsonschema:"Text to search for"`
	CaseSensitive bool   `json:"case_sensitive,omitempty" jsonschema:"Case-sensitive search (default false)"`
}

func handleSearchText(clients *workspace.Clients) mcp.ToolHandlerFor[SearchTextArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args SearchTextArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Docs(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Docs client: "+err.Error(), "AUTH_FAILED")
		}
		doc, err := svc.Documents.Get(args.DocumentID).Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to get document: "+err.Error(), "API_ERROR")
		}

		// Extract full text
		var sb strings.Builder
		for _, elem := range doc.Body.Content {
			if elem.Paragraph != nil {
				for _, pe := range elem.Paragraph.Elements {
					if pe.TextRun != nil {
						sb.WriteString(pe.TextRun.Content)
					}
				}
			}
		}
		text := sb.String()

		searchText := text
		searchQuery := args.Query
		if !args.CaseSensitive {
			searchText = strings.ToLower(text)
			searchQuery = strings.ToLower(args.Query)
		}

		type match struct {
			StartIndex int    `json:"start_index"`
			EndIndex   int    `json:"end_index"`
			Context    string `json:"context"`
		}

		matches := []match{}
		offset := 0
		for {
			idx := strings.Index(searchText[offset:], searchQuery)
			if idx == -1 {
				break
			}
			absIdx := offset + idx
			endIdx := absIdx + len(args.Query)

			// Context window: 40 chars before and after
			ctxStart := absIdx - 40
			if ctxStart < 0 {
				ctxStart = 0
			}
			ctxEnd := endIdx + 40
			if ctxEnd > len(text) {
				ctxEnd = len(text)
			}

			matches = append(matches, match{
				StartIndex: absIdx, EndIndex: endIdx,
				Context: text[ctxStart:ctxEnd],
			})
			offset = endIdx
		}

		return agentresult.SuccessResult(fmt.Sprintf("Found %d matches for %q", len(matches), args.Query), map[string]any{
			"matches": matches, "total": len(matches),
		})
	}
}
