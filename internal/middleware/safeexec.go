// Package middleware provides cross-cutting middleware for all MCP tool handlers:
// panic recovery, structured error wrapping, and rate limiting.
package middleware

import (
	"context"
	"fmt"
	"runtime/debug"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
)

// SafeExecute wraps a tool handler with panic recovery and error normalization.
// Any panic is caught and returned as a structured AgentResult with error code API_ERROR.
// Any error returned by the handler is also wrapped into AgentResult.
func SafeExecute[In any](toolName string, handler mcp.ToolHandlerFor[In, any]) mcp.ToolHandlerFor[In, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args In) (result *mcp.CallToolResult, annotations any, err error) {
		// Panic recovery
		defer func() {
			if r := recover(); r != nil {
				stack := string(debug.Stack())
				LogError(toolName, fmt.Sprintf("panic recovered: %v\n%s", r, stack))
				result, annotations, err = agentresult.ErrorResult(
					fmt.Sprintf("Internal server error in %s: %v", toolName, r),
					"API_ERROR",
				)
			}
		}()

		// Execute the actual handler
		result, annotations, err = handler(ctx, req, args)

		// If the handler returned a Go error (not an AgentResult error), wrap it
		if err != nil {
			LogError(toolName, err.Error())
			result, annotations, err = agentresult.ErrorResult(
				fmt.Sprintf("Error in %s: %v", toolName, err),
				"API_ERROR",
			)
		}

		return result, annotations, err
	}
}
