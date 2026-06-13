package drive

import (
	"context"
	"fmt"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
	driveapi "google.golang.org/api/drive/v3"
)

type ListArgs struct {
	Query      string `json:"query" jsonschema:"description=Drive search query (e.g. name contains 'report')"`
	FolderID   string `json:"folder_id,omitempty" jsonschema:"description=Optional folder ID to scope search"`
	MaxResults int    `json:"max_results,omitempty" jsonschema:"description=Max results (default 20)"`
}

type CreateFoldersArgs struct {
	Path           string `json:"path" jsonschema:"description=Folder path to create (e.g. Projects/2025/Q1)"`
	ParentFolderID string `json:"parent_folder_id" jsonschema:"description=Parent folder ID"`
}

func handleList(clients *workspace.Clients) mcp.ToolHandlerFor[ListArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args ListArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Drive(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Drive client: "+err.Error(), "AUTH_FAILED")
		}

		query := args.Query
		if args.FolderID != "" {
			query = fmt.Sprintf("'%s' in parents and %s", args.FolderID, query)
		}
		maxResults := int64(20)
		if args.MaxResults > 0 {
			maxResults = int64(args.MaxResults)
		}

		list := svc.Files.List().Q(query).PageSize(maxResults).
			Fields("files(id,name,mimeType,webViewLink,modifiedTime)")
		resp, err := list.Do()
		if err != nil {
			return agentresult.ErrorResult("Drive search failed: "+err.Error(), "API_ERROR")
		}

		type fileInfo struct {
			ID           string `json:"id"`
			Name         string `json:"name"`
			MimeType     string `json:"mime_type"`
			WebViewLink  string `json:"web_view_link"`
			ModifiedTime string `json:"modified_time"`
		}
		files := make([]fileInfo, 0, len(resp.Files))
		for _, f := range resp.Files {
			files = append(files, fileInfo{
				ID: f.Id, Name: f.Name, MimeType: f.MimeType,
				WebViewLink: f.WebViewLink, ModifiedTime: f.ModifiedTime,
			})
		}
		return agentresult.SuccessResult(fmt.Sprintf("Found %d files", len(files)), files)
	}
}

func handleCreateFolders(clients *workspace.Clients) mcp.ToolHandlerFor[CreateFoldersArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args CreateFoldersArgs) (*mcp.CallToolResult, any, error) {
		svc, err := clients.Drive(ctx)
		if err != nil {
			return agentresult.ErrorResult("Failed to initialize Drive client: "+err.Error(), "AUTH_FAILED")
		}

		segments := strings.Split(args.Path, "/")
		parentID := args.ParentFolderID
		folderIDs := make([]string, 0, len(segments))

		for _, segment := range segments {
			if segment == "" {
				continue
			}
			// Search for existing folder
			query := fmt.Sprintf("name='%s' and '%s' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false", segment, parentID)
			resp, err := svc.Files.List().Q(query).Fields("files(id)").PageSize(1).Do()
			if err != nil {
				return agentresult.ErrorResult(fmt.Sprintf("Failed to search for folder %q: %v", segment, err), "API_ERROR")
			}

			if len(resp.Files) > 0 {
				parentID = resp.Files[0].Id
			} else {
				// Create folder
				folder := &driveapi.File{
					Name:     segment,
					MimeType: "application/vnd.google-apps.folder",
					Parents:  []string{parentID},
				}
				created, err := svc.Files.Create(folder).Fields("id").Do()
				if err != nil {
					return agentresult.ErrorResult(fmt.Sprintf("Failed to create folder %q: %v", segment, err), "API_ERROR")
				}
				parentID = created.Id
			}
			folderIDs = append(folderIDs, parentID)
		}

		return agentresult.SuccessResult(fmt.Sprintf("Folder path created: %s", args.Path), map[string]any{
			"leaf_folder_id": parentID, "folder_ids": folderIDs,
		})
	}
}
