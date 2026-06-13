package workspace

import (
	"context"
	"fmt"
	"sync"

	"google.golang.org/api/docs/v1"
	"google.golang.org/api/drive/v3"
	"google.golang.org/api/option"
	"google.golang.org/api/sheets/v4"
	"google.golang.org/api/slides/v1"
)

// Clients holds lazily-initialized Google API service clients.
// Thread-safe — each client is created once on first access.
type Clients struct {
	mu     sync.Mutex
	slides *slides.Service
	docs   *docs.Service
	sheets *sheets.Service
	drive  *drive.Service
}

// NewClients creates an empty Clients struct. Services are initialized lazily.
func NewClients() *Clients {
	return &Clients{}
}

// Slides returns a cached Slides API service, creating it on first call.
func (c *Clients) Slides(ctx context.Context) (*slides.Service, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.slides != nil {
		return c.slides, nil
	}
	opt, err := ClientOption(ctx, SlidesScopes)
	if err != nil {
		return nil, fmt.Errorf("slides auth: %w", err)
	}
	svc, err := slides.NewService(ctx, opt, option.WithScopes(SlidesScopes...))
	if err != nil {
		return nil, fmt.Errorf("slides service: %w", err)
	}
	c.slides = svc
	return svc, nil
}

// Docs returns a cached Docs API service, creating it on first call.
func (c *Clients) Docs(ctx context.Context) (*docs.Service, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.docs != nil {
		return c.docs, nil
	}
	opt, err := ClientOption(ctx, DocsScopes)
	if err != nil {
		return nil, fmt.Errorf("docs auth: %w", err)
	}
	svc, err := docs.NewService(ctx, opt, option.WithScopes(DocsScopes...))
	if err != nil {
		return nil, fmt.Errorf("docs service: %w", err)
	}
	c.docs = svc
	return svc, nil
}

// Sheets returns a cached Sheets API service, creating it on first call.
func (c *Clients) Sheets(ctx context.Context) (*sheets.Service, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.sheets != nil {
		return c.sheets, nil
	}
	opt, err := ClientOption(ctx, SheetsScopes)
	if err != nil {
		return nil, fmt.Errorf("sheets auth: %w", err)
	}
	svc, err := sheets.NewService(ctx, opt, option.WithScopes(SheetsScopes...))
	if err != nil {
		return nil, fmt.Errorf("sheets service: %w", err)
	}
	c.sheets = svc
	return svc, nil
}

// Drive returns a cached Drive API service, creating it on first call.
func (c *Clients) Drive(ctx context.Context) (*drive.Service, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.drive != nil {
		return c.drive, nil
	}
	opt, err := ClientOption(ctx, DriveScopes)
	if err != nil {
		return nil, fmt.Errorf("drive auth: %w", err)
	}
	svc, err := drive.NewService(ctx, opt, option.WithScopes(DriveScopes...))
	if err != nil {
		return nil, fmt.Errorf("drive service: %w", err)
	}
	c.drive = svc
	return svc, nil
}
