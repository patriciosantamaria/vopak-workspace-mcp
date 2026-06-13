package slides

import (
	"context"
	"fmt"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
	"google.golang.org/api/slides/v1"
)

// InsertImageArgs are the arguments for the slides_insert_image tool.
type InsertImageArgs struct {
	PresentationID   string `json:"presentation_id" jsonschema:"description=The ID of the presentation"`
	SlideObjectID    string `json:"slide_object_id" jsonschema:"description=The object ID of the slide to insert the image into"`
	ImageURL         string `json:"image_url" jsonschema:"description=Publicly accessible URL of the image to insert"`
	Width            int64  `json:"width,omitempty" jsonschema:"description=Width in EMU (1 px = 9525 EMU). Optional"`
	Height           int64  `json:"height,omitempty" jsonschema:"description=Height in EMU (1 px = 9525 EMU). Optional"`
	TranslateX       int64  `json:"translate_x,omitempty" jsonschema:"description=Horizontal position offset in EMU. Optional"`
	TranslateY       int64  `json:"translate_y,omitempty" jsonschema:"description=Vertical position offset in EMU. Optional"`
	ReplaceElementID string `json:"replace_element_id,omitempty" jsonschema:"description=If set, delete this element and insert the image in its place"`
}

func handleInsertImage(clients *workspace.Clients) mcp.ToolHandlerFor[InsertImageArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args InsertImageArgs) (*mcp.CallToolResult, any, error) {
		if args.PresentationID == "" {
			return agentresult.ErrorResult("presentation_id is required", "INVALID_ARGS")
		}
		if args.SlideObjectID == "" {
			return agentresult.ErrorResult("slide_object_id is required", "INVALID_ARGS")
		}
		if args.ImageURL == "" {
			return agentresult.ErrorResult("image_url is required", "INVALID_ARGS")
		}

		svc, err := clients.Slides(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Slides client: "+err.Error(), "AUTH_FAILED")
		}

		imageID, err := insertImageIntoSlide(ctx, svc, args)
		if err != nil {
			return agentresult.ErrorResult(fmt.Sprintf("Failed to insert image: %v", err), "API_ERROR")
		}

		return agentresult.SuccessResult("Image inserted", map[string]any{
			"image_element_id": imageID,
		})
	}
}

// insertImageIntoSlide is the shared implementation for inserting an image.
// It handles both direct insertion and element-replacement modes.
// Returns the new image element's object ID.
func insertImageIntoSlide(ctx context.Context, svc *slides.Service, args InsertImageArgs) (string, error) {
	var requests []*slides.Request

	// If replacing an existing element, first retrieve its transform, then delete it.
	if args.ReplaceElementID != "" {
		// Fetch the presentation to find the element's current transform and size.
		pres, err := svc.Presentations.Get(args.PresentationID).Context(ctx).Do()
		if err != nil {
			return "", fmt.Errorf("failed to fetch presentation for element lookup: %w", err)
		}

		found := false
		for _, page := range pres.Slides {
			for _, elem := range page.PageElements {
				if elem.ObjectId == args.ReplaceElementID {
					found = true
					// Inherit the element's transform and size if not explicitly provided.
					if elem.Transform != nil {
						if args.TranslateX == 0 {
							args.TranslateX = int64(elem.Transform.TranslateX)
						}
						if args.TranslateY == 0 {
							args.TranslateY = int64(elem.Transform.TranslateY)
						}
					}
					if elem.Size != nil {
						if args.Width == 0 && elem.Size.Width != nil {
							args.Width = int64(elem.Size.Width.Magnitude)
						}
						if args.Height == 0 && elem.Size.Height != nil {
							args.Height = int64(elem.Size.Height.Magnitude)
						}
					}
					break
				}
			}
			if found {
				break
			}
		}

		if !found {
			return "", fmt.Errorf("element %q not found in presentation", args.ReplaceElementID)
		}

		// Delete the existing element first.
		requests = append(requests, &slides.Request{
			DeleteObject: &slides.DeleteObjectRequest{
				ObjectId: args.ReplaceElementID,
			},
		})
	}

	// Build the CreateImage request.
	createImageReq := &slides.CreateImageRequest{
		Url: args.ImageURL,
		ElementProperties: &slides.PageElementProperties{
			PageObjectId: args.SlideObjectID,
		},
	}

	// Set size if provided.
	if args.Width > 0 || args.Height > 0 {
		size := &slides.Size{}
		if args.Width > 0 {
			size.Width = &slides.Dimension{
				Magnitude: float64(args.Width),
				Unit:      "EMU",
			}
		}
		if args.Height > 0 {
			size.Height = &slides.Dimension{
				Magnitude: float64(args.Height),
				Unit:      "EMU",
			}
		}
		createImageReq.ElementProperties.Size = size
	}

	// Set transform (position) if provided.
	if args.TranslateX != 0 || args.TranslateY != 0 {
		createImageReq.ElementProperties.Transform = &slides.AffineTransform{
			ScaleX:     1.0,
			ScaleY:     1.0,
			TranslateX: float64(args.TranslateX),
			TranslateY: float64(args.TranslateY),
			Unit:       "EMU",
		}
	}

	requests = append(requests, &slides.Request{
		CreateImage: createImageReq,
	})

	batchReq := &slides.BatchUpdatePresentationRequest{
		Requests: requests,
	}

	resp, err := svc.Presentations.BatchUpdate(args.PresentationID, batchReq).Context(ctx).Do()
	if err != nil {
		return "", fmt.Errorf("BatchUpdate failed: %w", err)
	}

	// Extract the new image's object ID from the response.
	for _, reply := range resp.Replies {
		if reply.CreateImage != nil {
			return reply.CreateImage.ObjectId, nil
		}
	}

	return "", fmt.Errorf("no CreateImage reply in BatchUpdate response")
}
