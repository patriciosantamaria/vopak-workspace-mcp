package middleware

import (
	"encoding/json"
	"fmt"
	"os"
	"time"
)

// logEntry is the structured JSON format written to stderr.
// Never includes PII — only tool names, resource IDs, and durations.
type logEntry struct {
	Timestamp  string `json:"timestamp"`
	Level      string `json:"level"`
	Tool       string `json:"tool"`
	Message    string `json:"message"`
	DurationMs int64  `json:"duration_ms,omitempty"`
	ErrorCode  string `json:"error_code,omitempty"`
}

// logJSON writes a structured JSON log line to stderr.
func logJSON(level, tool, message string) {
	entry := logEntry{
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Level:     level,
		Tool:      tool,
		Message:   message,
	}
	b, err := json.Marshal(entry)
	if err != nil {
		fmt.Fprintf(os.Stderr, `{"level":"error","message":"failed to marshal log entry: %v"}`+"\n", err)
		return
	}
	fmt.Fprintln(os.Stderr, string(b))
}

// LogInfo writes an info-level structured log.
func LogInfo(tool, message string) {
	logJSON("info", tool, message)
}

// LogWarn writes a warn-level structured log.
func LogWarn(tool, message string) {
	logJSON("warn", tool, message)
}

// LogError writes an error-level structured log.
func LogError(tool, message string) {
	logJSON("error", tool, message)
}

// LogWithDuration writes an info-level log with API call duration.
func LogWithDuration(tool, message string, duration time.Duration) {
	entry := logEntry{
		Timestamp:  time.Now().UTC().Format(time.RFC3339),
		Level:      "info",
		Tool:       tool,
		Message:    message,
		DurationMs: duration.Milliseconds(),
	}
	b, _ := json.Marshal(entry)
	fmt.Fprintln(os.Stderr, string(b))
}

// LogErrorWithCode writes an error-level log with an error code from the taxonomy.
func LogErrorWithCode(tool, message, errorCode string) {
	entry := logEntry{
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Level:     "error",
		Tool:      tool,
		Message:   message,
		ErrorCode: errorCode,
	}
	b, _ := json.Marshal(entry)
	fmt.Fprintln(os.Stderr, string(b))
}
