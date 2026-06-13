package docs

import (
	"context"
	"fmt"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
)

type ReadTextArgs struct {
	DocumentID string `json:"document_id" jsonschema:"description=Google Doc ID"`
	StartIndex int    `json:"start_index,omitempty" jsonschema:"description=Start character index (0 = beginning)"`
	EndIndex   int    `json:"end_index,omitempty" jsonschema:"description=End character index (0 = entire doc)"`
}

type GetStructureArgs struct {
	DocumentID string `json:"document_id" jsonschema:"description=Google Doc ID"`
}

func handleReadText(clients *workspace.Clients) mcp.ToolHandlerFor[ReadTextArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args ReadTextArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Docs(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Docs client: "+err.Error(), "AUTH_FAILED")
		}
		doc, err := svc.Documents.Get(args.DocumentID).Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to get document: "+err.Error(), "API_ERROR")
		}

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

		if args.StartIndex > 0 || args.EndIndex > 0 {
			runes := []rune(text)
			start := args.StartIndex
			end := args.EndIndex
			if end == 0 || end > len(runes) {
				end = len(runes)
			}
			if start < 0 {
				start = 0
			}
			if start > end {
				return agentresult.ErrorResult("start_index exceeds end_index", "INVALID_ARGS")
			}
			text = string(runes[start:end])
		}

		return agentresult.SuccessResult(fmt.Sprintf("Read %d characters from document", len(text)), map[string]any{
			"title": doc.Title, "text": text,
		})
	}
}

func handleGetStructure(clients *workspace.Clients) mcp.ToolHandlerFor[GetStructureArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args GetStructureArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Docs(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Docs client: "+err.Error(), "AUTH_FAILED")
		}
		doc, err := svc.Documents.Get(args.DocumentID).Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to get document: "+err.Error(), "API_ERROR")
		}

		type element struct {
			Type       string `json:"type"`
			StartIndex int64  `json:"start_index"`
			EndIndex   int64  `json:"end_index"`
			Text       string `json:"text,omitempty"`
			Level      string `json:"level,omitempty"`
			Rows       int64  `json:"rows,omitempty"`
			Columns    int64  `json:"columns,omitempty"`
		}

		elements := []element{}
		for _, elem := range doc.Body.Content {
			e := element{StartIndex: elem.StartIndex, EndIndex: elem.EndIndex}
			if elem.Paragraph != nil {
				style := elem.Paragraph.ParagraphStyle
				if style != nil && strings.HasPrefix(style.NamedStyleType, "HEADING") {
					e.Type = "heading"
					e.Level = style.NamedStyleType
				} else {
					e.Type = "paragraph"
				}
				var text strings.Builder
				for _, pe := range elem.Paragraph.Elements {
					if pe.TextRun != nil {
						text.WriteString(pe.TextRun.Content)
					}
				}
				e.Text = strings.TrimSpace(text.String())
			} else if elem.Table != nil {
				e.Type = "table"
				e.Rows = int64(elem.Table.Rows)
				e.Columns = int64(elem.Table.Columns)
			} else if elem.SectionBreak != nil {
				e.Type = "section_break"
			} else if elem.TableOfContents != nil {
				e.Type = "table_of_contents"
			} else {
				continue
			}
			elements = append(elements, e)
		}

		return agentresult.SuccessResult(fmt.Sprintf("Document has %d structural elements", len(elements)), map[string]any{
			"title": doc.Title, "elements": elements,
		})
	}
}
