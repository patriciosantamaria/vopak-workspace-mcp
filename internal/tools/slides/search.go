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
// slides_search_text
// ---------------------------------------------------------------------------

// SearchTextArgs defines the input for the slides_search_text tool.
type SearchTextArgs struct {
	PresentationID string `json:"presentation_id" jsonschema:"description=The ID of the Google Slides presentation"`
	Query          string `json:"query"            jsonschema:"description=The text string to search for across all slides"`
	CaseSensitive  bool   `json:"case_sensitive"   jsonschema:"description=If true the search is case-sensitive. Default false"`
}

// SearchMatch represents a single occurrence of the query text.
type SearchMatch struct {
	SlideIndex int    `json:"slide_index"`
	ElementID  string `json:"element_id"`
	MatchText  string `json:"match_text"`
	Context    string `json:"context"`
}

// SearchTextResult is the top-level response from slides_search_text.
type SearchTextResult struct {
	Query      string        `json:"query"`
	MatchCount int           `json:"match_count"`
	Matches    []SearchMatch `json:"matches"`
}

func handleSearchText(clients *workspace.Clients) mcp.ToolHandlerFor[SearchTextArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args SearchTextArgs) (*mcp.CallToolResult, any, error) {
		start := time.Now()

		if strings.TrimSpace(args.Query) == "" {
			return agentresult.ErrorResult("query must not be empty", "INVALID_ARGS")
		}

		svc, err := clients.Slides(ctx)
		if err != nil {
			middleware.LogErrorWithCode("slides_search_text", "auth failed", "AUTH_FAILED")
			return agentresult.ErrorResult("Failed to initialize Slides client: "+err.Error(), "AUTH_FAILED")
		}

		pres, err := svc.Presentations.Get(args.PresentationID).Do()
		if err != nil {
			middleware.LogErrorWithCode("slides_search_text", "API call failed: "+err.Error(), "API_ERROR")
			return agentresult.ErrorResult("Failed to get presentation: "+err.Error(), "API_ERROR")
		}

		query := args.Query
		if !args.CaseSensitive {
			query = strings.ToLower(query)
		}

		var matches []SearchMatch

		for slideIdx, slide := range pres.Slides {
			slideMatches := searchPageElements(slide.PageElements, slideIdx, query, args.CaseSensitive)
			matches = append(matches, slideMatches...)
		}

		result := SearchTextResult{
			Query:      args.Query,
			MatchCount: len(matches),
			Matches:    matches,
		}

		middleware.LogWithDuration("slides_search_text",
			fmt.Sprintf("found %d matches across %d slides", len(matches), len(pres.Slides)),
			time.Since(start))

		return agentresult.SuccessResult(
			fmt.Sprintf("Found %d matches for %q", len(matches), args.Query),
			result,
		)
	}
}

// searchPageElements recursively searches PageElements for text matching query.
func searchPageElements(elements []*slidesapi.PageElement, slideIdx int, query string, caseSensitive bool) []SearchMatch {
	var matches []SearchMatch

	for _, pe := range elements {
		// Recurse into groups.
		if pe.ElementGroup != nil {
			nested := searchPageElements(pe.ElementGroup.Children, slideIdx, query, caseSensitive)
			matches = append(matches, nested...)
			continue
		}

		var textBody *slidesapi.TextContent
		if pe.Shape != nil && pe.Shape.Text != nil {
			textBody = pe.Shape.Text
		}
		if textBody == nil {
			continue
		}

		// Concatenate all text runs into a single string for searching.
		var fullText strings.Builder
		for _, te := range textBody.TextElements {
			if te.TextRun != nil {
				fullText.WriteString(te.TextRun.Content)
			}
		}

		text := fullText.String()
		searchIn := text
		searchFor := query
		if !caseSensitive {
			searchIn = strings.ToLower(text)
			searchFor = strings.ToLower(query)
		}

		// Find all occurrences within this element.
		offset := 0
		for {
			idx := strings.Index(searchIn[offset:], searchFor)
			if idx < 0 {
				break
			}
			absIdx := offset + idx

			// Build context: up to 40 chars before and after the match.
			ctxStart := absIdx - 40
			if ctxStart < 0 {
				ctxStart = 0
			}
			ctxEnd := absIdx + len(query) + 40
			if ctxEnd > len(text) {
				ctxEnd = len(text)
			}
			contextStr := strings.TrimSpace(text[ctxStart:ctxEnd])

			matches = append(matches, SearchMatch{
				SlideIndex: slideIdx,
				ElementID:  pe.ObjectId,
				MatchText:  text[absIdx : absIdx+len(query)],
				Context:    contextStr,
			})

			offset = absIdx + len(query)
		}
	}

	return matches
}

// ---------------------------------------------------------------------------
// slides_list
// ---------------------------------------------------------------------------

// ListArgs defines the input for the slides_list tool.
type ListArgs struct {
	PresentationID string `json:"presentation_id" jsonschema:"description=The ID of the Google Slides presentation"`
}

// SlideInfo contains summary metadata for a single slide.
type SlideInfo struct {
	Index      int    `json:"index"`
	ObjectID   string `json:"object_id"`
	LayoutName string `json:"layout_name"`
}

// ListResult is the top-level response from slides_list.
type ListResult struct {
	PresentationTitle string      `json:"presentation_title"`
	SlideCount        int         `json:"slide_count"`
	Slides            []SlideInfo `json:"slides"`
}

func handleList(clients *workspace.Clients) mcp.ToolHandlerFor[ListArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args ListArgs) (*mcp.CallToolResult, any, error) {
		start := time.Now()

		svc, err := clients.Slides(ctx)
		if err != nil {
			middleware.LogErrorWithCode("slides_list", "auth failed", "AUTH_FAILED")
			return agentresult.ErrorResult("Failed to initialize Slides client: "+err.Error(), "AUTH_FAILED")
		}

		pres, err := svc.Presentations.Get(args.PresentationID).Do()
		if err != nil {
			middleware.LogErrorWithCode("slides_list", "API call failed: "+err.Error(), "API_ERROR")
			return agentresult.ErrorResult("Failed to get presentation: "+err.Error(), "API_ERROR")
		}

		slides := make([]SlideInfo, len(pres.Slides))
		for i, slide := range pres.Slides {
			layoutName := ""
			if slide.SlideProperties != nil && slide.SlideProperties.LayoutObjectId != "" {
				layoutName = resolveLayoutName(pres, slide.SlideProperties.LayoutObjectId)
			}
			slides[i] = SlideInfo{
				Index:      i,
				ObjectID:   slide.ObjectId,
				LayoutName: layoutName,
			}
		}

		result := ListResult{
			PresentationTitle: pres.Title,
			SlideCount:        len(pres.Slides),
			Slides:            slides,
		}

		middleware.LogWithDuration("slides_list",
			fmt.Sprintf("listed %d slides", len(slides)),
			time.Since(start))

		return agentresult.SuccessResult(
			fmt.Sprintf("Presentation %q has %d slides", pres.Title, len(slides)),
			result,
		)
	}
}

// resolveLayoutName finds the display name for a layout object ID by searching
// the presentation's layouts collection.
func resolveLayoutName(pres *slidesapi.Presentation, layoutObjectID string) string {
	for _, layout := range pres.Layouts {
		if layout.ObjectId == layoutObjectID {
			if layout.LayoutProperties != nil {
				return layout.LayoutProperties.DisplayName
			}
			return layout.ObjectId
		}
	}
	return layoutObjectID
}
