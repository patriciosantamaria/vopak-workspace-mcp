package middleware

import (
	"context"
	"fmt"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/patriciosantamaria/vopak-workspace-mcp/pkg/agentresult"
	"golang.org/x/time/rate"
)

// Default rate limiter: 5 requests/second with burst of 10.
// This protects against accidental API quota exhaustion.
var defaultLimiter = rate.NewLimiter(5, 10)

// RateLimit wraps a tool handler with a token-bucket rate limiter.
// If the rate limit is exceeded, it returns a QUOTA_EXCEEDED AgentResult
// instead of calling the Google API.
func RateLimit[In any](toolName string, handler mcp.ToolHandlerFor[In, any]) mcp.ToolHandlerFor[In, any] {
	return func(ctx context.Context, req *mcp.CallToolRequest, args In) (*mcp.CallToolResult, any, error) {
		if !defaultLimiter.Allow() {
			LogWarn(toolName, "rate limit exceeded, request throttled")
			return agentresult.ErrorResult(
				fmt.Sprintf("Rate limit exceeded for %s — try again shortly", toolName),
				"QUOTA_EXCEEDED",
			)
		}
		return handler(ctx, req, args)
	}
}

// SetRateLimit reconfigures the global rate limiter.
// Useful for testing or environment-specific tuning.
func SetRateLimit(rps float64, burst int) {
	defaultLimiter = rate.NewLimiter(rate.Limit(rps), burst)
}
