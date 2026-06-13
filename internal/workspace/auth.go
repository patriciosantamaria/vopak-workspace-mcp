// Package workspace provides Google Workspace API clients and authentication.
// All tools share a single ADC-based credential factory with per-service scope narrowing.
package workspace

import (
	"context"
	"fmt"
	"sync"

	"golang.org/x/oauth2/google"
	"google.golang.org/api/option"
	"google.golang.org/api/slides/v1"
	"google.golang.org/api/docs/v1"
	"google.golang.org/api/sheets/v4"
	"google.golang.org/api/drive/v3"
)

// Scopes used by each server group. Only the required scopes are requested.
var (
	SlidesScopes = []string{
		slides.PresentationsScope,
		sheets.SpreadsheetsReadonlyScope, // For linked chart data
		drive.DriveFileScope,             // For template copy
	}
	DocsScopes = []string{
		docs.DocumentsScope,
		drive.DriveFileScope,
	}
	SheetsScopes = []string{
		sheets.SpreadsheetsScope,
		drive.DriveFileScope,
	}
	DriveScopes = []string{
		drive.DriveScope,
	}
	// BrandedScopes combines all content scopes needed for template copy + fill.
	BrandedScopes = []string{
		slides.PresentationsScope,
		docs.DocumentsScope,
		drive.DriveScope,
	}
)

// credCache caches credentials by scope set to avoid repeated ADC lookups.
var (
	credCache   = make(map[string]*google.Credentials)
	credCacheMu sync.RWMutex
)

// scopeKey creates a cache key from a slice of scopes.
func scopeKey(scopes []string) string {
	key := ""
	for _, s := range scopes {
		key += s + "|"
	}
	return key
}

// GetCredentials returns ADC-based credentials scoped to the given OAuth scopes.
// Results are cached per unique scope set.
func GetCredentials(ctx context.Context, scopes []string) (*google.Credentials, error) {
	key := scopeKey(scopes)

	credCacheMu.RLock()
	if cred, ok := credCache[key]; ok {
		credCacheMu.RUnlock()
		return cred, nil
	}
	credCacheMu.RUnlock()

	cred, err := google.FindDefaultCredentials(ctx, scopes...)
	if err != nil {
		return nil, fmt.Errorf("ADC credentials not found: %w (run 'gcloud auth application-default login')", err)
	}

	credCacheMu.Lock()
	credCache[key] = cred
	credCacheMu.Unlock()

	return cred, nil
}

// ClientOption returns a google.api/option for the given scopes, suitable for
// passing to any Google API client constructor.
func ClientOption(ctx context.Context, scopes []string) (option.ClientOption, error) {
	cred, err := GetCredentials(ctx, scopes)
	if err != nil {
		return nil, err
	}
	return option.WithCredentials(cred), nil
}
