package branded

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
	docsapi "google.golang.org/api/docs/v1"
	driveapi "google.golang.org/api/drive/v3"
	slidesapi "google.golang.org/api/slides/v1"
)

// --- Arg structs ---

type CreatePresentationArgs struct {
	TemplateKey string `json:"template_key,omitempty" jsonschema:"description=Template key (default: slides_corporate)"`
	Title       string `json:"title" jsonschema:"description=Presentation title"`
	Subtitle    string `json:"subtitle,omitempty" jsonschema:"description=Subtitle text"`
	Date        string `json:"date,omitempty" jsonschema:"description=Date string (default: today)"`
	FolderID    string `json:"folder_id,omitempty" jsonschema:"description=Target Drive folder ID"`
}

type CreateDocumentArgs struct {
	TemplateKey  string `json:"template_key" jsonschema:"description=Template key (e.g. doc_add doc_guideline doc_policy)"`
	Title        string `json:"title" jsonschema:"description=Document title"`
	DocumentName string `json:"document_name,omitempty" jsonschema:"description=MyDocs document name"`
	MyDocsNumber string `json:"mydocs_number,omitempty" jsonschema:"description=MyDocs reference number"`
	Author       string `json:"author,omitempty" jsonschema:"description=Author name"`
	FolderID     string `json:"folder_id,omitempty" jsonschema:"description=Target Drive folder ID"`
}

type HealthCheckArgs struct{}

// --- Handlers ---

func handleCreatePresentation(clients *workspace.Clients) mcp.ToolHandlerFor[CreatePresentationArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args CreatePresentationArgs) (*mcp.CallToolResult, any, error) {
		templateKey := args.TemplateKey
		if templateKey == "" {
			templateKey = "slides_corporate"
		}

		tmpl, err := GetTemplate(templateKey)
		if err != nil {
			return agentresult.ErrorResult("Template not found: "+err.Error(), "NOT_FOUND")
		}
		if tmpl.Type != "presentation" {
			return agentresult.ErrorResult(fmt.Sprintf("Template %q is type %q, not presentation", templateKey, tmpl.Type), "INVALID_ARGS")
		}

		driveSvc, err := clients.Drive(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Drive client: "+err.Error(), "AUTH_FAILED")
		}

		// Copy template
		copyFile := &driveapi.File{Name: args.Title}
		if args.FolderID != "" {
			copyFile.Parents = []string{args.FolderID}
		}
		copied, err := driveSvc.Files.Copy(tmpl.ID, copyFile).Fields("id,webViewLink").Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to copy template: "+err.Error(), "API_ERROR")
		}

		// Fill placeholders
		slidesSvc, err := clients.Slides(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Slides client: "+err.Error(), "AUTH_FAILED")
		}

		date := args.Date
		if date == "" {
			date = time.Now().Format("January 2, 2006")
		}

		replacements := map[string]string{
			"{{DECK_TITLE}}":    args.Title,
			"{{DECK_SUBTITLE}}": args.Subtitle,
			"{{DATE}}":          date,
		}

		var requests []*slidesapi.Request
		for find, replace := range replacements {
			if replace == "" {
				continue
			}
			requests = append(requests, &slidesapi.Request{
				ReplaceAllText: &slidesapi.ReplaceAllTextRequest{
					ContainsText: &slidesapi.SubstringMatchCriteria{
						Text:      find,
						MatchCase: true,
					},
					ReplaceText: replace,
				},
			})
		}

		if len(requests) > 0 {
			_, err = slidesSvc.Presentations.BatchUpdate(copied.Id, &slidesapi.BatchUpdatePresentationRequest{
				Requests: requests,
			}).Do()
			if err != nil {
				return agentresult.ErrorResult("Failed to fill placeholders: "+err.Error(), "API_ERROR")
			}
		}

		return agentresult.SuccessResult("Branded presentation created", map[string]any{
			"presentation_id": copied.Id,
			"url":             copied.WebViewLink,
			"template_used":   templateKey,
		})
	}
}

func handleCreateDocument(clients *workspace.Clients) mcp.ToolHandlerFor[CreateDocumentArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args CreateDocumentArgs) (*mcp.CallToolResult, any, error) {
		tmpl, err := GetTemplate(args.TemplateKey)
		if err != nil {
			return agentresult.ErrorResult("Template not found: "+err.Error(), "NOT_FOUND")
		}
		if tmpl.Type != "document" {
			return agentresult.ErrorResult(fmt.Sprintf("Template %q is type %q, not document", args.TemplateKey, tmpl.Type), "INVALID_ARGS")
		}

		driveSvc, err := clients.Drive(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Drive client: "+err.Error(), "AUTH_FAILED")
		}

		copyFile := &driveapi.File{Name: args.Title}
		if args.FolderID != "" {
			copyFile.Parents = []string{args.FolderID}
		}
		copied, err := driveSvc.Files.Copy(tmpl.ID, copyFile).Fields("id,webViewLink").Do()
		if err != nil {
			return agentresult.ErrorResult("Failed to copy template: "+err.Error(), "API_ERROR")
		}

		// Fill placeholders via Docs API
		docsSvc, err := clients.Docs(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Docs client: "+err.Error(), "AUTH_FAILED")
		}

		// Build placeholder map from template placeholders + args
		placeholderValues := map[string]string{}
		for _, ph := range tmpl.Placeholders {
			lower := strings.ToLower(ph)
			switch {
			case strings.Contains(lower, "topic") || strings.Contains(lower, "name") && !strings.Contains(lower, "document") && !strings.Contains(lower, "mydocs"):
				placeholderValues[ph] = args.Title
			case strings.Contains(lower, "document name"):
				if args.DocumentName != "" {
					placeholderValues[ph] = args.DocumentName
				} else {
					placeholderValues[ph] = args.Title
				}
			case strings.Contains(lower, "mydocs"):
				if args.MyDocsNumber != "" {
					placeholderValues[ph] = args.MyDocsNumber
				}
			case strings.Contains(lower, "ticket"):
				placeholderValues[ph] = args.Title
			}
		}

		var requests []*docsapi.Request
		for find, replace := range placeholderValues {
			if replace == "" {
				continue
			}
			requests = append(requests, &docsapi.Request{
				ReplaceAllText: &docsapi.ReplaceAllTextRequest{
					ContainsText: &docsapi.SubstringMatchCriteria{
						Text:      find,
						MatchCase: true,
					},
					ReplaceText: replace,
				},
			})
		}

		if len(requests) > 0 {
			_, err = docsSvc.Documents.BatchUpdate(copied.Id, &docsapi.BatchUpdateDocumentRequest{
				Requests: requests,
			}).Do()
			if err != nil {
				return agentresult.ErrorResult("Failed to fill placeholders: "+err.Error(), "API_ERROR")
			}
		}

		return agentresult.SuccessResult("Branded document created", map[string]any{
			"document_id":   copied.Id,
			"url":           copied.WebViewLink,
			"template_used": args.TemplateKey,
		})
	}
}

func handleHealthCheck(clients *workspace.Clients) mcp.ToolHandlerFor[HealthCheckArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args HealthCheckArgs) (*mcp.CallToolResult, any, error) {
		checks := map[string]string{}

		// Check Drive
		driveSvc, err := clients.Drive(ctx)
		if err != nil {
			checks["drive"] = "FAIL: " + err.Error()
		} else {
			_, err = driveSvc.Files.List().PageSize(1).Do()
			if err != nil {
				checks["drive"] = "FAIL: " + err.Error()
			} else {
				checks["drive"] = "PASS"
			}
		}

		// Check template folder access
		reg, err := LoadRegistry()
		if err != nil {
			checks["template_registry"] = "FAIL: " + err.Error()
		} else {
			checks["template_registry"] = fmt.Sprintf("PASS: %d templates loaded", len(reg.Templates))
			if driveSvc != nil {
				_, err := driveSvc.Files.List().Q(fmt.Sprintf("'%s' in parents", reg.FolderID)).PageSize(1).Do()
				if err != nil {
					checks["template_folder"] = "FAIL: " + err.Error()
				} else {
					checks["template_folder"] = "PASS"
				}
			}
		}

		// Check Slides
		_, err = clients.Slides(ctx)
		if err != nil {
			checks["slides"] = "FAIL: " + err.Error()
		} else {
			checks["slides"] = "PASS"
		}

		// Check Docs
		_, err = clients.Docs(ctx)
		if err != nil {
			checks["docs"] = "FAIL: " + err.Error()
		} else {
			checks["docs"] = "PASS"
		}

		// Check Sheets
		_, err = clients.Sheets(ctx)
		if err != nil {
			checks["sheets"] = "FAIL: " + err.Error()
		} else {
			checks["sheets"] = "PASS"
		}

		allPass := true
		for _, v := range checks {
			if !strings.HasPrefix(v, "PASS") {
				allPass = false
				break
			}
		}

		status := "HEALTHY"
		if !allPass {
			status = "DEGRADED"
		}

		return agentresult.SuccessResult(fmt.Sprintf("Health check: %s", status), map[string]any{
			"status": status, "checks": checks,
		})
	}
}
