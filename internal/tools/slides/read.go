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
// slides_get_content
// ---------------------------------------------------------------------------

// GetContentArgs defines the input for the slides_get_content tool.
type GetContentArgs struct {
	PresentationID string `json:"presentation_id" jsonschema:"The ID of the Google Slides presentation"`
	SlideIndex     int    `json:"slide_index"      jsonschema:"Zero-based index of the slide to read"`
	IncludeStyles  bool   `json:"include_styles"   jsonschema:"If true return font/color/size metadata for each text run. Default false"`
}

// TextRunContent represents a single text run extracted from a slide element.
type TextRunContent struct {
	Text       string        `json:"text"`
	Style      *TextRunStyle `json:"style,omitempty"`
}

// TextRunStyle contains the formatting metadata for a text run.
type TextRunStyle struct {
	FontFamily     string  `json:"font_family,omitempty"`
	FontSizePt     float64 `json:"font_size_pt,omitempty"`
	Bold           bool    `json:"bold,omitempty"`
	Italic         bool    `json:"italic,omitempty"`
	ForegroundColor string `json:"foreground_color,omitempty"`
}

// ElementContent holds all text runs extracted from a single page element.
type ElementContent struct {
	ElementID   string           `json:"element_id"`
	ElementType string           `json:"element_type"`
	TextRuns    []TextRunContent `json:"text_runs,omitempty"`
}

// SlideContent is the top-level result returned by slides_get_content.
type SlideContent struct {
	SlideIndex int              `json:"slide_index"`
	ObjectID   string           `json:"object_id"`
	Elements   []ElementContent `json:"elements"`
}

func handleGetContent(clients *workspace.Clients) mcp.ToolHandlerFor[GetContentArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args GetContentArgs) (*mcp.CallToolResult, any, error) {
		start := time.Now()

		svc, err := clients.Slides(ctx)
		if err != nil {
			middleware.LogErrorWithCode("slides_get_content", "auth failed", "AUTH_FAILED")
			return agentresult.ErrorResult("Failed to initialize Slides client: "+err.Error(), "AUTH_FAILED")
		}

		pres, err := svc.Presentations.Get(args.PresentationID).Do()
		if err != nil {
			middleware.LogErrorWithCode("slides_get_content", "API call failed: "+err.Error(), "API_ERROR")
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
		elements := extractElements(slide.PageElements, args.IncludeStyles)

		result := SlideContent{
			SlideIndex: args.SlideIndex,
			ObjectID:   slide.ObjectId,
			Elements:   elements,
		}

		middleware.LogWithDuration("slides_get_content",
			fmt.Sprintf("read slide %d with %d elements", args.SlideIndex, len(elements)),
			time.Since(start))

		return agentresult.SuccessResult("Retrieved slide content", result)
	}
}

// extractElements walks a slice of PageElements and pulls out text run content
// (and optionally style information).
func extractElements(pageElements []*slidesapi.PageElement, includeStyles bool) []ElementContent {
	var elements []ElementContent

	for _, pe := range pageElements {
		ec := ElementContent{
			ElementID:   pe.ObjectId,
			ElementType: elementType(pe),
		}

		// Groups contain nested elements — recurse.
		if pe.ElementGroup != nil {
			nested := extractElements(pe.ElementGroup.Children, includeStyles)
			elements = append(elements, nested...)
			continue
		}

		// Extract text body from shapes, tables cells are handled separately.
		var textBody *slidesapi.TextContent
		if pe.Shape != nil && pe.Shape.Text != nil {
			textBody = pe.Shape.Text
		}

		if textBody != nil {
			ec.TextRuns = extractTextRuns(textBody, includeStyles)
		}

		elements = append(elements, ec)
	}

	return elements
}

// extractTextRuns converts Slides TextElements into our TextRunContent model.
func extractTextRuns(tc *slidesapi.TextContent, includeStyles bool) []TextRunContent {
	var runs []TextRunContent

	for _, te := range tc.TextElements {
		if te.TextRun == nil {
			continue
		}
		content := te.TextRun.Content
		if strings.TrimSpace(content) == "" && content != "\n" {
			continue
		}

		run := TextRunContent{Text: content}

		if includeStyles && te.TextRun.Style != nil {
			s := te.TextRun.Style
			style := &TextRunStyle{
				Bold:   s.Bold,
				Italic: s.Italic,
			}
			if s.FontFamily != "" {
				style.FontFamily = s.FontFamily
			}
			if s.FontSize != nil {
				style.FontSizePt = s.FontSize.Magnitude
			}
			if s.ForegroundColor != nil &&
				s.ForegroundColor.OpaqueColor != nil &&
				s.ForegroundColor.OpaqueColor.RgbColor != nil {
				rgb := s.ForegroundColor.OpaqueColor.RgbColor
				style.ForegroundColor = fmt.Sprintf("#%02x%02x%02x",
					int(rgb.Red*255), int(rgb.Green*255), int(rgb.Blue*255))
			}
			run.Style = style
		}

		runs = append(runs, run)
	}

	return runs
}

// elementType returns a human-readable type for a PageElement.
func elementType(pe *slidesapi.PageElement) string {
	switch {
	case pe.Shape != nil:
		return "SHAPE"
	case pe.Image != nil:
		return "IMAGE"
	case pe.Table != nil:
		return "TABLE"
	case pe.Video != nil:
		return "VIDEO"
	case pe.ElementGroup != nil:
		return "GROUP"
	case pe.Line != nil:
		return "LINE"
	case pe.SheetsChart != nil:
		return "SHEETS_CHART"
	case pe.WordArt != nil:
		return "WORD_ART"
	default:
		return "UNKNOWN"
	}
}

// ---------------------------------------------------------------------------
// slides_get_thumbnail
// ---------------------------------------------------------------------------

// GetThumbnailArgs defines the input for the slides_get_thumbnail tool.
type GetThumbnailArgs struct {
	PresentationID string `json:"presentation_id" jsonschema:"The ID of the Google Slides presentation"`
	SlideIndex     int    `json:"slide_index"      jsonschema:"Zero-based index of the slide to get a thumbnail for"`
}

// ThumbnailResult holds the thumbnail URL returned by the API.
type ThumbnailResult struct {
	SlideIndex   int    `json:"slide_index"`
	ObjectID     string `json:"object_id"`
	ThumbnailURL string `json:"thumbnail_url"`
	ContentURL   string `json:"content_url"`
	Width        int64  `json:"width_px"`
	Height       int64  `json:"height_px"`
}

func handleGetThumbnail(clients *workspace.Clients) mcp.ToolHandlerFor[GetThumbnailArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args GetThumbnailArgs) (*mcp.CallToolResult, any, error) {
		start := time.Now()

		svc, err := clients.Slides(ctx)
		if err != nil {
			middleware.LogErrorWithCode("slides_get_thumbnail", "auth failed", "AUTH_FAILED")
			return agentresult.ErrorResult("Failed to initialize Slides client: "+err.Error(), "AUTH_FAILED")
		}

		pres, err := svc.Presentations.Get(args.PresentationID).Do()
		if err != nil {
			middleware.LogErrorWithCode("slides_get_thumbnail", "API call failed: "+err.Error(), "API_ERROR")
			return agentresult.ErrorResult("Failed to get presentation: "+err.Error(), "API_ERROR")
		}

		if args.SlideIndex < 0 || args.SlideIndex >= len(pres.Slides) {
			return agentresult.ErrorResult(
				fmt.Sprintf("slide_index %d is out of range — presentation has %d slides (0-%d)",
					args.SlideIndex, len(pres.Slides), len(pres.Slides)-1),
				"INVALID_ARGS",
			)
		}

		slideObjectID := pres.Slides[args.SlideIndex].ObjectId

		thumb, err := svc.Presentations.Pages.GetThumbnail(args.PresentationID, slideObjectID).Do()
		if err != nil {
			middleware.LogErrorWithCode("slides_get_thumbnail", "thumbnail API failed: "+err.Error(), "API_ERROR")
			return agentresult.ErrorResult("Failed to get thumbnail: "+err.Error(), "API_ERROR")
		}

		result := ThumbnailResult{
			SlideIndex:   args.SlideIndex,
			ObjectID:     slideObjectID,
			ThumbnailURL: thumb.ContentUrl,
			ContentURL:   thumb.ContentUrl,
			Width:        thumb.Width,
			Height:       thumb.Height,
		}

		middleware.LogWithDuration("slides_get_thumbnail",
			fmt.Sprintf("thumbnail for slide %d (%s)", args.SlideIndex, slideObjectID),
			time.Since(start))

		return agentresult.SuccessResult("Retrieved slide thumbnail", result)
	}
}
