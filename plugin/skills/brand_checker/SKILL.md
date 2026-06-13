---
name: Brand Checker
description: "Post-generation brand compliance verification for Vopak Slides and Docs. Run after creating or modifying any content to check colors, fonts, density, layout rhythm, and logo integrity. Auto-fixes violations where possible."
---

# Brand Checker — Post-Generation Compliance Verification

> **Purpose**: After creating any presentation or document, verify it matches Vopak brand rules. Auto-fix violations where possible, flag manual-intervention items.

## When to Activate

- **After** any content creation via `branded_create_*` tools
- **After** any content modification via `slides_*` or `docs_*` tools
- User explicitly asks to "check brand compliance" or "verify branding"
- As the final step in the `slide_designer` workflow

---

## Verification Checklist

### 1. Color Validation

**Approved Palette:**

| Color | Hex | Allowed Usage |
|:------|:----|:-------------|
| Deep Blue | `#0a2373` | Headings, primary text, dark backgrounds |
| Cyan | `#00cfe1` | Accents, highlights, forward arrow |
| Light Blue | `#009ef5` | Secondary accent |
| Orange | `#fc7000` | Secondary accent, warnings |
| Green | `#52d400` | Secondary accent, sustainability |
| Cobalt | `#283ce1` | Icon details, gradients |
| Steel | `#46555a` | Body text, captions |
| Grey | `#e1e1e1` | Backgrounds, dividers |
| White | `#ffffff` | Text on dark backgrounds |
| Black | `#000000` | **ONLY** for monochrome logos/icons |

**Tints**: All colors can be used at 10% increments (10%–100%).

**Auto-Fix Rules:**

| Violation | Action |
|:----------|:-------|
| `#FF0000` (red) text | → Replace with `#fc7000` (Orange) |
| `#0000FF` (blue) text | → Replace with `#0a2373` (Deep Blue) |
| `#008000` (green) text | → Replace with `#52d400` (Green) |
| Any unlisted hex color | → Flag for manual review |

### 2. Font Validation

**Slides:**

| Element | Required Font | Required Weight |
|:--------|:-------------|:---------------|
| All text | Inter | — |
| Headings/titles | Inter | Regular (400) — **NEVER bold** |
| Body text | Inter | Regular (400) |
| Bold emphasis | Inter | Bold (700) — only for specific words |

**Docs:**

| Element | Required Font | Required Weight |
|:--------|:-------------|:---------------|
| Body text | Arial | Regular |
| Headings | Arial or Inter | Regular — **NEVER bold** |
| Bold emphasis | Arial | Bold — only for specific words |

**Auto-Fix Rules:**

| Violation | Action |
|:----------|:-------|
| Roboto, Calibri, Times New Roman | → Replace with Inter (slides) or Arial (docs) |
| Bold heading/title | → Set to `font-weight: 400` |
| Custom/decorative font | → Flag for manual review |

### 3. Slide Density (Slides Only)

| Metric | Limit | Severity |
|:-------|:------|:---------|
| Bullet points per slide | Max 6 | ⚠️ Warning |
| Words per bullet | Max 40 | ⚠️ Warning |
| Total words per text-heavy slide | Max 150 | ⚠️ Warning |
| Empty slides (no content) | 0 | 🔴 Error |

**Cannot auto-fix** — flag for user with suggestion: "Slide N has 200 words — consider splitting into two slides."

### 4. Visual Rhythm (Slides Only)

| Pattern | Rule | Severity |
|:--------|:-----|:---------|
| 3+ consecutive text-heavy slides | ❌ Break with image/section | ⚠️ Warning |
| 3+ consecutive white-background slides | ❌ Insert section header | ⚠️ Warning |
| 3+ consecutive dark-background slides | ❌ Insert split/white slide | ⚠️ Warning |
| Missing section headers between topics | ❌ Add section header | ⚠️ Warning |

### 5. Logo Integrity

| Check | Expected | Severity |
|:------|:---------|:---------|
| Logo present on cover | Top-right corner | 🔴 Error if missing |
| Logo color on dark bg | White | 🔴 Error if wrong |
| Logo color on light bg | Deep Blue | 🔴 Error if wrong |
| Logo horizontal orientation | Icon left, wordmark right | 🔴 Error if rotated |
| Logo not resized | Original proportions | ⚠️ Warning |

**Cannot auto-fix** — flag for manual review: "Cover logo appears to be [missing/wrong color/resized]."

### 6. Cover Slide Integrity (Slides Only)

| Element | Rule | Auto-Fix? |
|:--------|:-----|:----------|
| Title | Present, Cyan (#00cfe1), 20pt | ✅ Fix color/size |
| Date | Present, White, 12pt | ✅ Fix color/size |
| Tagline | READ-ONLY — never modify | 🔴 Flag if changed |
| Slogan | READ-ONLY — never modify | 🔴 Flag if changed |
| Flow forward arrows | READ-ONLY — never modify | 🔴 Flag if changed |
| Background photo | READ-ONLY — never modify | 🔴 Flag if changed |

### 7. Document Formatting (Docs Only)

| Check | Expected | Severity |
|:------|:---------|:---------|
| Heading 1 font size | 20pt | ⚠️ Warning |
| Heading 2 font size | 16pt | ⚠️ Warning |
| Body font size | 11pt | ⚠️ Warning |
| Heading color | Deep Blue (#0a2373) | ✅ Auto-fix |
| Line spacing | 1.15 | ⚠️ Warning |
| Table header row | Deep Blue background, White text | ✅ Auto-fix |

---

## Verification Workflow

### For Slides

```
1. slides_list({ presentationId }) → get all slide IDs
2. FOR each slide:
   a. slides_get_content({ slideIndex, includeStyles: true })
      → Check fonts, colors, text density
   b. slides_get_thumbnail({ slideObjectId, size: "LARGE" })
      → Download and visually inspect
   c. Record violations
3. Check rhythm: analyze background sequence across all slides
4. Generate report
5. Auto-fix what's possible
6. Re-verify fixed slides
7. Present remaining issues to user
```

### For Docs

```
1. docs_get_structure({ documentId }) → get headings, tables
2. docs_read_text({ documentId }) → get full text
3. Check font/color/size via structure metadata
4. Generate report
5. Auto-fix via docs_set_style
6. Present remaining issues to user
```

---

## Report Format

After running all checks, produce a compliance report:

```markdown
## Brand Compliance Report

**Document**: [Title] (ID: ...)
**Checked**: June 13, 2026
**Overall**: ✅ PASS / ⚠️ WARNINGS / 🔴 FAIL

### Auto-Fixed (N items)
- ✅ Slide 3: Changed font from Roboto → Inter
- ✅ Slide 5: Changed text color from #0000FF → #0a2373

### Warnings (N items)
- ⚠️ Slide 4: 180 words — consider splitting (max: 150)
- ⚠️ Slides 6-8: Three consecutive white backgrounds

### Errors (N items)
- 🔴 Cover: Logo appears to be missing
- 🔴 Slide 2: Tagline text has been modified

### Summary
| Category | Pass | Warn | Fail |
|:---------|:-----|:-----|:-----|
| Colors | 12 | 0 | 0 |
| Fonts | 10 | 2 | 0 |
| Density | 8 | 1 | 0 |
| Rhythm | 1 | 1 | 0 |
| Logo | 0 | 0 | 1 |
```

---

## Anti-Patterns

- ❌ **Skipping verification** — this step is mandatory after every content creation
- ❌ **Auto-fixing logos** — never programmatically modify logo elements
- ❌ **Ignoring density warnings** — text-heavy slides hurt presentation quality
- ❌ **Fixing cover static elements** — tagline, slogan, arrows are READ-ONLY
- ❌ **Using bold for headings** — Vopak brand explicitly prohibits bold headings
