package docs

import (
	"context"
	"fmt"
	"strconv"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
	docsapi "google.golang.org/api/docs/v1"
)

type InsertTextArgs struct {
	DocumentID string `json:"document_id" jsonschema:"description=Google Doc ID"`
	Text       string `json:"text" jsonschema:"description=Text to insert"`
	Index      int    `json:"index" jsonschema:"description=Character index for insertion"`
}

type ReplaceTextArgs struct {
	DocumentID    string `json:"document_id" jsonschema:"description=Google Doc ID"`
	Find          string `json:"find" jsonschema:"description=Text to find"`
	Replace       string `json:"replace" jsonschema:"description=Replacement text"`
	CaseSensitive bool   `json:"case_sensitive,omitempty" jsonschema:"description=Case-sensitive matching"`
}

type SetStyleArgs struct {
	DocumentID string   `json:"document_id" jsonschema:"description=Google Doc ID"`
	StartIndex int      `json:"start_index" jsonschema:"description=Start of range"`
	EndIndex   int      `json:"end_index" jsonschema:"description=End of range"`
	FontFamily string   `json:"font_family,omitempty" jsonschema:"description=Font family (e.g. Inter)"`
	FontSize   float64  `json:"font_size,omitempty" jsonschema:"description=Font size in pt"`
	Bold       *bool    `json:"bold,omitempty" jsonschema:"description=Bold formatting"`
	Italic     *bool    `json:"italic,omitempty" jsonschema:"description=Italic formatting"`
	Underline  *bool    `json:"underline,omitempty" jsonschema:"description=Underline formatting"`
	FgColor    string   `json:"fg_color,omitempty" jsonschema:"description=Foreground color as hex (e.g. #0a2373)"`
	BgColor    string   `json:"bg_color,omitempty" jsonschema:"description=Background color as hex"`
}

type InsertImageArgs struct {
	DocumentID string `json:"document_id" jsonschema:"description=Google Doc ID"`
	ImageURL   string `json:"image_url" jsonschema:"description=Publicly accessible image URL"`
	Index      int    `json:"index" jsonschema:"description=Character index for insertion"`
}

func handleInsertText(clients *workspace.Clients) mcp.ToolHandlerFor[InsertTextArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args InsertTextArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Docs(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Docs client: "+err.Error(), "AUTH_FAILED")
		}

		_, err = svc.Documents.BatchUpdate(args.DocumentID, &docsapi.BatchUpdateDocumentRequest{
			Requests: []*docsapi.Request{{
				InsertText: &docsapi.InsertTextRequest{
					Text:     args.Text,
					Location: &docsapi.Location{Index: int64(args.Index)},
				},
			}},
		}).Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to insert text: "+err.Error(), "API_ERROR")
		}

		return agentresult.SuccessResult(fmt.Sprintf("Inserted %d characters at index %d", len(args.Text), args.Index), nil)
	}
}

func handleReplaceText(clients *workspace.Clients) mcp.ToolHandlerFor[ReplaceTextArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args ReplaceTextArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Docs(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Docs client: "+err.Error(), "AUTH_FAILED")
		}

		resp, err := svc.Documents.BatchUpdate(args.DocumentID, &docsapi.BatchUpdateDocumentRequest{
			Requests: []*docsapi.Request{{
				ReplaceAllText: &docsapi.ReplaceAllTextRequest{
					ContainsText: &docsapi.SubstringMatchCriteria{
						Text:      args.Find,
						MatchCase: args.CaseSensitive,
					},
					ReplaceText: args.Replace,
				},
			}},
		}).Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to replace text: "+err.Error(), "API_ERROR")
		}

		count := int64(0)
		for _, reply := range resp.Replies {
			if reply.ReplaceAllText != nil {
				count = reply.ReplaceAllText.OccurrencesChanged
			}
		}

		return agentresult.SuccessResult(fmt.Sprintf("Replaced %d occurrences of %q", count, args.Find), map[string]any{
			"occurrences_changed": count,
		})
	}
}

// parseHexColor converts "#0a2373" to a Docs API Color.
func parseHexColor(hex string) *docsapi.Color {
	hex = strings.TrimPrefix(hex, "#")
	if len(hex) != 6 {
		return nil
	}
	r, _ := strconv.ParseInt(hex[0:2], 16, 64)
	g, _ := strconv.ParseInt(hex[2:4], 16, 64)
	b, _ := strconv.ParseInt(hex[4:6], 16, 64)
	return &docsapi.Color{
		RgbColor: &docsapi.RgbColor{
			Red:   float64(r) / 255.0,
			Green: float64(g) / 255.0,
			Blue:  float64(b) / 255.0,
		},
	}
}

func handleSetStyle(clients *workspace.Clients) mcp.ToolHandlerFor[SetStyleArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args SetStyleArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Docs(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Docs client: "+err.Error(), "AUTH_FAILED")
		}

		style := &docsapi.TextStyle{}
		maskFields := []string{}

		if args.FontFamily != "" {
			style.WeightedFontFamily = &docsapi.WeightedFontFamily{FontFamily: args.FontFamily}
			maskFields = append(maskFields, "weightedFontFamily")
		}
		if args.FontSize > 0 {
			style.FontSize = &docsapi.Dimension{Magnitude: args.FontSize, Unit: "PT"}
			maskFields = append(maskFields, "fontSize")
		}
		if args.Bold != nil {
			style.Bold = *args.Bold
			if !*args.Bold {
				style.ForceSendFields = append(style.ForceSendFields, "Bold")
			}
			maskFields = append(maskFields, "bold")
		}
		if args.Italic != nil {
			style.Italic = *args.Italic
			if !*args.Italic {
				style.ForceSendFields = append(style.ForceSendFields, "Italic")
			}
			maskFields = append(maskFields, "italic")
		}
		if args.Underline != nil {
			style.Underline = *args.Underline
			if !*args.Underline {
				style.ForceSendFields = append(style.ForceSendFields, "Underline")
			}
			maskFields = append(maskFields, "underline")
		}
		if args.FgColor != "" {
			if c := parseHexColor(args.FgColor); c != nil {
				style.ForegroundColor = &docsapi.OptionalColor{Color: c}
				maskFields = append(maskFields, "foregroundColor")
			}
		}
		if args.BgColor != "" {
			if c := parseHexColor(args.BgColor); c != nil {
				style.BackgroundColor = &docsapi.OptionalColor{Color: c}
				maskFields = append(maskFields, "backgroundColor")
			}
		}

		if len(maskFields) == 0 {
			return agentresult.ErrorResult("No style fields specified", "INVALID_ARGS")
		}

		_, err = svc.Documents.BatchUpdate(args.DocumentID, &docsapi.BatchUpdateDocumentRequest{
			Requests: []*docsapi.Request{{
				UpdateTextStyle: &docsapi.UpdateTextStyleRequest{
					TextStyle: style,
					Range: &docsapi.Range{
						StartIndex: int64(args.StartIndex),
						EndIndex:   int64(args.EndIndex),
					},
					Fields: strings.Join(maskFields, ","),
				},
			}},
		}).Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to set style: "+err.Error(), "API_ERROR")
		}

		return agentresult.SuccessResult(fmt.Sprintf("Applied style (%s) to range [%d:%d]", strings.Join(maskFields, ", "), args.StartIndex, args.EndIndex), nil)
	}
}

func handleInsertImage(clients *workspace.Clients) mcp.ToolHandlerFor[InsertImageArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args InsertImageArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Docs(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Docs client: "+err.Error(), "AUTH_FAILED")
		}

		_, err = svc.Documents.BatchUpdate(args.DocumentID, &docsapi.BatchUpdateDocumentRequest{
			Requests: []*docsapi.Request{{
				InsertInlineImage: &docsapi.InsertInlineImageRequest{
					Uri:      args.ImageURL,
					Location: &docsapi.Location{Index: int64(args.Index)},
				},
			}},
		}).Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to insert image: "+err.Error(), "API_ERROR")
		}

		return agentresult.SuccessResult("Image inserted successfully", nil)
	}
}
