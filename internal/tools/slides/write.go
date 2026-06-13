package slides

import (
	"context"
	"fmt"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
	"google.golang.org/api/slides/v1"
)

// ---------------------------------------------------------------------------
// slides_add
// ---------------------------------------------------------------------------

// AddArgs are the arguments for the slides_add tool.
type AddArgs struct {
	PresentationID string `json:"presentation_id" jsonschema:"description=The ID of the presentation to add a slide to"`
	Layout         string `json:"layout,omitempty" jsonschema:"description=Predefined layout name (e.g. BLANK, TITLE_AND_BODY). Defaults to BLANK"`
	InsertionIndex int    `json:"insertion_index,omitempty" jsonschema:"description=0-based index where the slide should be inserted. -1 or omitted to append at the end"`
}

func handleAdd(clients *workspace.Clients) mcp.ToolHandlerFor[AddArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args AddArgs) (*mcp.CallToolResult, any, error) {
		if args.PresentationID == "" {
			return agentresult.ErrorResult("presentation_id is required", "INVALID_ARGS")
		}

		svc, err := clients.Slides(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Slides client: "+err.Error(), "AUTH_FAILED")
		}

		layout := args.Layout
		if layout == "" {
			layout = "BLANK"
		}

		createReq := &slides.CreateSlideRequest{
			SlideLayoutReference: &slides.LayoutReference{
				PredefinedLayout: layout,
			},
		}

		// Set insertion index only if explicitly provided (> -1).
		// A zero value is valid (insert at position 0), so we use -1 as sentinel for "append".
		if args.InsertionIndex >= 0 {
			createReq.InsertionIndex = int64(args.InsertionIndex)
			createReq.ForceSendFields = []string{"InsertionIndex"}
		}

		batchReq := &slides.BatchUpdatePresentationRequest{
			Requests: []*slides.Request{
				{CreateSlide: createReq},
			},
		}

		resp, err := svc.Presentations.BatchUpdate(args.PresentationID, batchReq).Context(ctx).Do()
		if err != nil {
			return agentresult.ErrorResult(fmt.Sprintf("Failed to add slide: %v", err), "API_ERROR")
		}

		// Extract the new slide's object ID from the response.
		var newSlideID string
		for _, reply := range resp.Replies {
			if reply.CreateSlide != nil {
				newSlideID = reply.CreateSlide.ObjectId
				break
			}
		}

		return agentresult.SuccessResult("Slide added", map[string]any{
			"slide_object_id": newSlideID,
		})
	}
}

// ---------------------------------------------------------------------------
// slides_duplicate
// ---------------------------------------------------------------------------

// DuplicateArgs are the arguments for the slides_duplicate tool.
type DuplicateArgs struct {
	PresentationID string `json:"presentation_id" jsonschema:"description=The ID of the presentation"`
	SlideObjectID  string `json:"slide_object_id" jsonschema:"description=The object ID of the slide to duplicate"`
}

func handleDuplicate(clients *workspace.Clients) mcp.ToolHandlerFor[DuplicateArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args DuplicateArgs) (*mcp.CallToolResult, any, error) {
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
					DuplicateObject: &slides.DuplicateObjectRequest{
						ObjectId: args.SlideObjectID,
					},
				},
			},
		}

		resp, err := svc.Presentations.BatchUpdate(args.PresentationID, batchReq).Context(ctx).Do()
		if err != nil {
			return agentresult.ErrorResult(fmt.Sprintf("Failed to duplicate slide: %v", err), "API_ERROR")
		}

		var newSlideID string
		for _, reply := range resp.Replies {
			if reply.DuplicateObject != nil {
				newSlideID = reply.DuplicateObject.ObjectId
				break
			}
		}

		return agentresult.SuccessResult("Slide duplicated", map[string]any{
			"new_slide_object_id": newSlideID,
		})
	}
}

// ---------------------------------------------------------------------------
// slides_reorder
// ---------------------------------------------------------------------------

// ReorderArgs are the arguments for the slides_reorder tool.
type ReorderArgs struct {
	PresentationID string   `json:"presentation_id" jsonschema:"description=The ID of the presentation"`
	SlideObjectIDs []string `json:"slide_object_ids" jsonschema:"description=Ordered list of slide object IDs to move"`
	InsertionIndex int      `json:"insertion_index" jsonschema:"description=0-based target position for the moved slides"`
}

func handleReorder(clients *workspace.Clients) mcp.ToolHandlerFor[ReorderArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args ReorderArgs) (*mcp.CallToolResult, any, error) {
		if args.PresentationID == "" {
			return agentresult.ErrorResult("presentation_id is required", "INVALID_ARGS")
		}
		if len(args.SlideObjectIDs) == 0 {
			return agentresult.ErrorResult("slide_object_ids must contain at least one slide ID", "INVALID_ARGS")
		}

		svc, err := clients.Slides(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Slides client: "+err.Error(), "AUTH_FAILED")
		}

		batchReq := &slides.BatchUpdatePresentationRequest{
			Requests: []*slides.Request{
				{
					UpdateSlidesPosition: &slides.UpdateSlidesPositionRequest{
						SlideObjectIds:     args.SlideObjectIDs,
						InsertionIndex:     int64(args.InsertionIndex),
						ForceSendFields:    []string{"InsertionIndex"},
					},
				},
			},
		}

		_, err = svc.Presentations.BatchUpdate(args.PresentationID, batchReq).Context(ctx).Do()
		if err != nil {
			return agentresult.ErrorResult(fmt.Sprintf("Failed to reorder slides: %v", err), "API_ERROR")
		}

		return agentresult.SuccessResult("Slides reordered", map[string]any{
			"slide_object_ids": args.SlideObjectIDs,
			"insertion_index":  args.InsertionIndex,
		})
	}
}

// ---------------------------------------------------------------------------
// slides_replace_text
// ---------------------------------------------------------------------------

// Replacement defines a single find-and-replace pair.
type Replacement struct {
	Find          string `json:"find" jsonschema:"description=The text to search for"`
	Replace       string `json:"replace" jsonschema:"description=The replacement text"`
	CaseSensitive bool   `json:"case_sensitive,omitempty" jsonschema:"description=Whether the match is case-sensitive. Defaults to false"`
}

// ReplaceTextArgs are the arguments for the slides_replace_text tool.
// Supports both a single replacement (Find/Replace fields) and bulk mode (Replacements array).
type ReplaceTextArgs struct {
	PresentationID string        `json:"presentation_id" jsonschema:"description=The ID of the presentation"`
	Find           string        `json:"find,omitempty" jsonschema:"description=Text to search for (single replacement mode)"`
	Replace        string        `json:"replace,omitempty" jsonschema:"description=Replacement text (single replacement mode)"`
	CaseSensitive  bool          `json:"case_sensitive,omitempty" jsonschema:"description=Case sensitivity for single replacement mode"`
	Replacements   []Replacement `json:"replacements,omitempty" jsonschema:"description=Array of {find, replace, case_sensitive} pairs for bulk replacement"`
}

func handleReplaceText(clients *workspace.Clients) mcp.ToolHandlerFor[ReplaceTextArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args ReplaceTextArgs) (*mcp.CallToolResult, any, error) {
		if args.PresentationID == "" {
			return agentresult.ErrorResult("presentation_id is required", "INVALID_ARGS")
		}

		// Build the list of replacements: prefer the Replacements array, fall back to single mode.
		replacements := args.Replacements
		if len(replacements) == 0 {
			if args.Find == "" {
				return agentresult.ErrorResult("Either 'replacements' array or 'find'/'replace' fields are required", "INVALID_ARGS")
			}
			replacements = []Replacement{
				{Find: args.Find, Replace: args.Replace, CaseSensitive: args.CaseSensitive},
			}
		}

		svc, err := clients.Slides(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Slides client: "+err.Error(), "AUTH_FAILED")
		}

		// Build one ReplaceAllText request per replacement pair.
		var requests []*slides.Request
		for _, r := range replacements {
			if r.Find == "" {
				return agentresult.ErrorResult("Each replacement must have a non-empty 'find' field", "INVALID_ARGS")
			}
			requests = append(requests, &slides.Request{
				ReplaceAllText: &slides.ReplaceAllTextRequest{
					ContainsText: &slides.SubstringMatchCriteria{
						Text:      r.Find,
						MatchCase: r.CaseSensitive,
					},
					ReplaceText: r.Replace,
				},
			})
		}

		batchReq := &slides.BatchUpdatePresentationRequest{
			Requests: requests,
		}

		resp, err := svc.Presentations.BatchUpdate(args.PresentationID, batchReq).Context(ctx).Do()
		if err != nil {
			return agentresult.ErrorResult(fmt.Sprintf("Failed to replace text: %v", err), "API_ERROR")
		}

		// Count total replacements across all pairs.
		totalReplacements := int64(0)
		details := make([]map[string]any, 0, len(resp.Replies))
		for i, reply := range resp.Replies {
			count := int64(0)
			if reply.ReplaceAllText != nil {
				count = reply.ReplaceAllText.OccurrencesChanged
			}
			totalReplacements += count
			details = append(details, map[string]any{
				"find":                replacements[i].Find,
				"replace":             replacements[i].Replace,
				"occurrences_changed": count,
			})
		}

		return agentresult.SuccessResult(
			fmt.Sprintf("Replaced %d occurrence(s) across %d replacement(s)", totalReplacements, len(replacements)),
			map[string]any{
				"total_occurrences_changed": totalReplacements,
				"details":                  details,
			},
		)
	}
}
