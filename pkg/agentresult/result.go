// Package agentresult provides the standard response type for all MCP tool handlers.
// Every tool returns an AgentResult — no raw data or unstructured errors.
package agentresult

import (
	"encoding/json"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// AgentResult is the standard response from every Vopak MCP tool.
type AgentResult struct {
	Success   bool   `json:"success"`
	Message   string `json:"message"`
	Data      any    `json:"data,omitempty"`
	ErrorCode string `json:"error_code,omitempty"`
}

// Success creates a successful AgentResult.
func Success(msg string, data any) AgentResult {
	return AgentResult{Success: true, Message: msg, Data: data}
}

// Error creates a failed AgentResult with an error code.
func Error(msg string, code string) AgentResult {
	return AgentResult{Success: false, Message: msg, ErrorCode: code}
}

// ToToolResult serializes an AgentResult into an MCP CallToolResult.
func (r AgentResult) ToToolResult() (*mcp.CallToolResult, any, error) {
	b, err := json.Marshal(r)
	if err != nil {
		return &mcp.CallToolResult{
			Content: []mcp.Content{&mcp.TextContent{Text: `{"success":false,"message":"failed to marshal AgentResult","error_code":"MARSHAL_ERROR"}`}},
			IsError: true,
		}, nil, nil
	}

	result := &mcp.CallToolResult{
		Content: []mcp.Content{&mcp.TextContent{Text: string(b)}},
	}
	if !r.Success {
		result.IsError = true
	}
	return result, nil, nil
}

// SuccessResult is a convenience function that creates and serializes a success response.
func SuccessResult(msg string, data any) (*mcp.CallToolResult, any, error) {
	return Success(msg, data).ToToolResult()
}

// ErrorResult is a convenience function that creates and serializes an error response.
func ErrorResult(msg string, code string) (*mcp.CallToolResult, any, error) {
	return Error(msg, code).ToToolResult()
}
