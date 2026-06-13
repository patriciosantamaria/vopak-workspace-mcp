package middleware

import (
	"context"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// Wrap applies the full middleware chain to a tool handler:
// SafeExecute (panic recovery) → RateLimit → duration logging.
// This is the standard wrapper for all production tool handlers.
func Wrap[In any](toolName string, handler mcp.ToolHandlerFor[In, any]) mcp.ToolHandlerFor[In, any] {
	// Build the chain inside-out: handler → ratelimit → safeexec → timing
	wrapped := SafeExecute(toolName, RateLimit(toolName, handler))

	return func(ctx context.Context, req *mcp.CallToolRequest, args In) (*mcp.CallToolResult, any, error) {
		start := time.Now()
		LogInfo(toolName, "tool invoked")

		result, annotations, err := wrapped(ctx, req, args)

		LogWithDuration(toolName, "tool completed", time.Since(start))
		return result, annotations, err
	}
}
