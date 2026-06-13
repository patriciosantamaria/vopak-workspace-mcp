package branded

import (
	_ "embed"
	"encoding/json"
	"fmt"
)

//go:embed templates.json
var templatesJSON []byte

// Template describes a single Vopak corporate template.
type Template struct {
	ID           string   `json:"id"`
	Type         string   `json:"type"`          // "presentation" or "document"
	Category     string   `json:"category"`      // "formal", "operational", "correspondence"
	Placeholders []string `json:"placeholders"`  // e.g. ["{{DECK_TITLE}}", "{{DATE}}"]
	Version      string   `json:"version"`
}

// Registry holds all templates indexed by key.
type Registry struct {
	FolderID  string              `json:"folder_id"`
	Templates map[string]Template `json:"templates"`
}

// LoadRegistry deserializes the embedded templates.json.
func LoadRegistry() (*Registry, error) {
	var reg Registry
	if err := json.Unmarshal(templatesJSON, &reg); err != nil {
		return nil, fmt.Errorf("failed to parse embedded template registry: %w", err)
	}
	return &reg, nil
}

// GetTemplate looks up a template by key (e.g. "slides_corporate", "doc_add").
func GetTemplate(key string) (*Template, error) {
	reg, err := LoadRegistry()
	if err != nil {
		return nil, err
	}
	tmpl, ok := reg.Templates[key]
	if !ok {
		return nil, fmt.Errorf("template %q not found in registry", key)
	}
	return &tmpl, nil
}

// ListTemplates returns all template keys grouped by type.
func ListTemplates() (map[string][]string, error) {
	reg, err := LoadRegistry()
	if err != nil {
		return nil, err
	}
	result := map[string][]string{}
	for key, tmpl := range reg.Templates {
		result[tmpl.Type] = append(result[tmpl.Type], key)
	}
	return result, nil
}
