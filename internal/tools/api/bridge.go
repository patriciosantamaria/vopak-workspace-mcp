package api

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/internal/workspace"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
	"golang.org/x/oauth2/google"
	oauth2http "golang.org/x/oauth2"
)

// Wide scopes for the API bridge — covers Gmail, Calendar, Drive, Slides, Docs, Sheets.
var bridgeScopes = []string{
	"https://mail.google.com/",
	"https://www.googleapis.com/auth/calendar",
	"https://www.googleapis.com/auth/drive",
	"https://www.googleapis.com/auth/presentations",
	"https://www.googleapis.com/auth/documents",
	"https://www.googleapis.com/auth/spreadsheets",
}

// getAuthenticatedClient returns an HTTP client with ADC credentials.
func getAuthenticatedClient(ctx context.Context) (*http.Client, error) {
	cred, err := google.FindDefaultCredentials(ctx, bridgeScopes...)
	if err != nil {
		return nil, fmt.Errorf("ADC credentials not found: %w", err)
	}
	return oauth2http.NewClient(ctx, cred.TokenSource), nil
}

const apiBase = "https://www.googleapis.com/"

// --- Arg structs ---

type ReadArgs struct {
	Endpoint    string            `json:"endpoint" jsonschema:"description=API path (e.g. gmail/v1/users/me/messages)"`
	QueryParams map[string]string `json:"query_params,omitempty" jsonschema:"description=Optional query parameters"`
}

type WriteArgs struct {
	Endpoint string `json:"endpoint" jsonschema:"description=API path"`
	Method   string `json:"method,omitempty" jsonschema:"description=HTTP method (POST PUT PATCH). Default: POST"`
	Body     string `json:"body,omitempty" jsonschema:"description=JSON request body"`
}

type DeleteArgs struct {
	Endpoint string `json:"endpoint" jsonschema:"description=API path for DELETE request"`
}

// --- Handlers ---

func handleRead(_ *workspace.Clients) mcp.ToolHandlerFor[ReadArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args ReadArgs) (*mcp.CallToolResult, any, error) {
		client, err := getAuthenticatedClient(ctx)
		if err != nil {
			return agentresult.ErrorResult(err.Error(), "AUTH_FAILED")
		}

		url := apiBase + args.Endpoint
		if len(args.QueryParams) > 0 {
			params := []string{}
			for k, v := range args.QueryParams {
				params = append(params, fmt.Sprintf("%s=%s", k, v))
			}
			url += "?" + strings.Join(params, "&")
		}

		resp, err := client.Get(url)
		if err != nil {
			return agentresult.ErrorResult("GET request failed: "+err.Error(), "API_ERROR")
		}
		defer resp.Body.Close()

		body, err := io.ReadAll(resp.Body)
		if err != nil {
			return agentresult.ErrorResult("Failed to read response: "+err.Error(), "API_ERROR")
		}

		if resp.StatusCode >= 400 {
			return agentresult.ErrorResult(fmt.Sprintf("API returned %d: %s", resp.StatusCode, string(body)), "API_ERROR")
		}

		return agentresult.SuccessResult(fmt.Sprintf("GET %s → %d", args.Endpoint, resp.StatusCode), map[string]any{
			"status_code": resp.StatusCode, "body": string(body),
		})
	}
}

func handleWrite(_ *workspace.Clients) mcp.ToolHandlerFor[WriteArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args WriteArgs) (*mcp.CallToolResult, any, error) {
		client, err := getAuthenticatedClient(ctx)
		if err != nil {
			return agentresult.ErrorResult(err.Error(), "AUTH_FAILED")
		}

		method := args.Method
		if method == "" {
			method = "POST"
		}
		method = strings.ToUpper(method)
		if method != "POST" && method != "PUT" && method != "PATCH" {
			return agentresult.ErrorResult(fmt.Sprintf("Unsupported method %q — use POST, PUT, or PATCH", method), "INVALID_ARGS")
		}

		url := apiBase + args.Endpoint
		httpReq, err := http.NewRequestWithContext(ctx, method, url, strings.NewReader(args.Body))
		if err != nil {
			return agentresult.ErrorResult("Failed to create request: "+err.Error(), "API_ERROR")
		}
		httpReq.Header.Set("Content-Type", "application/json")

		resp, err := client.Do(httpReq)
		if err != nil {
			return agentresult.ErrorResult(fmt.Sprintf("%s request failed: %v", method, err), "API_ERROR")
		}
		defer resp.Body.Close()

		body, err := io.ReadAll(resp.Body)
		if err != nil {
			return agentresult.ErrorResult("Failed to read response: "+err.Error(), "API_ERROR")
		}

		if resp.StatusCode >= 400 {
			return agentresult.ErrorResult(fmt.Sprintf("API returned %d: %s", resp.StatusCode, string(body)), "API_ERROR")
		}

		return agentresult.SuccessResult(fmt.Sprintf("%s %s → %d", method, args.Endpoint, resp.StatusCode), map[string]any{
			"status_code": resp.StatusCode, "body": string(body),
		})
	}
}

func handleDelete(_ *workspace.Clients) mcp.ToolHandlerFor[DeleteArgs, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args DeleteArgs) (*mcp.CallToolResult, any, error) {
		client, err := getAuthenticatedClient(ctx)
		if err != nil {
			return agentresult.ErrorResult(err.Error(), "AUTH_FAILED")
		}

		url := apiBase + args.Endpoint
		httpReq, err := http.NewRequestWithContext(ctx, "DELETE", url, nil)
		if err != nil {
			return agentresult.ErrorResult("Failed to create request: "+err.Error(), "API_ERROR")
		}

		resp, err := client.Do(httpReq)
		if err != nil {
			return agentresult.ErrorResult("DELETE request failed: "+err.Error(), "API_ERROR")
		}
		defer resp.Body.Close()

		body, err := io.ReadAll(resp.Body)
		if err != nil {
			return agentresult.ErrorResult("Failed to read response: "+err.Error(), "API_ERROR")
		}

		if resp.StatusCode >= 400 {
			return agentresult.ErrorResult(fmt.Sprintf("API returned %d: %s", resp.StatusCode, string(body)), "API_ERROR")
		}

		return agentresult.SuccessResult(fmt.Sprintf("DELETE %s → %d", args.Endpoint, resp.StatusCode), map[string]any{
			"status_code": resp.StatusCode,
		})
	}
}
