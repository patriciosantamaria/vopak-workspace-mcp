---
name: Layout Planner
description: "Plan visual variety for multi-slide Vopak presentations. Ensures alternating backgrounds, diverse layout types, and correct section structure. Activate when creating presentations with 3+ slides."
---

# Layout Planner — Visual Variety for Slide Decks

> **Purpose**: Prevent monotonous decks by enforcing layout diversity, background alternation, and proper section structure when creating multi-slide presentations.

## When to Activate

- Creating a presentation with **3 or more content slides**
- Reorganizing or restructuring an existing deck
- User asks to "improve the flow" or "make it more visual"

---

## Layout Types (19 Available)

### Dark Background (Deep Blue #0a2373)

| # | Layout | Best For |
|:--|:-------|:---------|
| 1 | Cover Slide | Opening — always first |
| 2 | Table of Contents | Agenda/overview after cover |
| 3 | Section Header | Topic transitions — use before every new section |
| 5 | Strategy Section Cover | Mid-deck section dividers for strategy pillars |
| 8 | 3-Column Deep Blue | Comparing 3 concepts/topics |
| 9 | World Map + Data | Geographic data, footprint visualization |
| 13 | 3-Photo Highlights | Strategy summaries, quarterly highlights |
| 19 | Closing Slide | "Thank you" — always last |

### Light Background (White)

| # | Layout | Best For |
|:--|:-------|:---------|
| 7 | White / Standard Content | Dense text, bullet points |
| 10 | Steps / Process Flow | Workflows, timelines, procedures |
| 12 | KPI At-a-Glance | Dashboard, key metrics |
| 14 | People / Team Photo | Team introductions |
| 15 | Financial Charts | Revenue, cost, financial data |
| 18 | History Timeline | Company/project history |

### Split / Hybrid

| # | Layout | Best For |
|:--|:-------|:---------|
| 4 | Split with Photo (Sidebar) | Content + supporting imagery |
| 6 | Photo Mosaic + Bullets | Visual highlights with text overlay |
| 11 | Full-Bleed Video | Video embed, dramatic visual |
| 16 | Split Photo (Case Study) | Project/terminal showcases |
| 17 | Sustainability Roadmap | ESG, People/Planet/Profit |

---

## Deck Structure Rules

### Rule 1: Background Alternation
**Never place two consecutive slides with the same background type.**

```
✅ Correct: Dark → Light → Dark → Split → Light → Dark
❌ Wrong:  White → White → White → Dark → Dark
```

### Rule 2: Section Headers Before Topic Changes
Every new topic MUST be preceded by a **Section Header** (Layout #3).

```
✅ Correct:
  Cover → ToC → Section Header → Content → Content → Section Header → Content → Closing

❌ Wrong:
  Cover → Content → Content → Content → Content → Closing
```

### Rule 3: Maximum 2 Consecutive Same-Type Slides
No more than 2 slides of the same layout type in a row.

### Rule 4: Minimum Layout Diversity
For decks with 5+ content slides, use **at least 4 different layout types**.

### Rule 5: Preferred Deck Structure

| Position | Layout | Required? |
|:---------|:-------|:----------|
| First | Cover (Layout #1) | **Mandatory** |
| Second | Table of Contents (Layout #2) | Recommended for 6+ slides |
| Before each section | Section Header (Layout #3) | **Mandatory** |
| Content | Mix of Layouts #4-#18 | Variety required |
| Last | Closing (Layout #19) | **Mandatory** |

---

## Planning Workflow

### Step 1: Content Outline

List all topics/sections the user wants to cover:

```
1. Introduction / Context
2. Current State Analysis
3. Proposed Solution
4. Implementation Timeline
5. Budget & Resources
6. Next Steps
```

### Step 2: Assign Layout Types

Map each topic to the most appropriate layout, ensuring variety:

```
Slide 1:  Cover (#1) ............................ DARK
Slide 2:  Table of Contents (#2) ................ DARK
Slide 3:  Section Header — "Context" (#3) ....... DARK
Slide 4:  Split with Photo (#4) ................. SPLIT ← content
Slide 5:  White / Standard (#7) ................. LIGHT ← content
Slide 6:  Section Header — "Solution" (#3) ...... DARK
Slide 7:  3-Column Deep Blue (#8) ............... DARK ← content
Slide 8:  Split Photo - Case Study (#16) ........ SPLIT ← content
Slide 9:  Section Header — "Timeline" (#3) ...... DARK
Slide 10: Steps / Process Flow (#10) ............ LIGHT ← content
Slide 11: Section Header — "Budget" (#3) ........ DARK
Slide 12: KPI At-a-Glance (#12) ................. LIGHT ← content
Slide 13: Financial Charts (#15) ................. LIGHT ← content (OK: different layout)
Slide 14: Section Header — "Next Steps" (#3) .... DARK
Slide 15: White / Standard (#7) ................. LIGHT ← content
Slide 16: Closing (#19) ......................... DARK
```

### Step 3: Verify Variety Checklist

Before generating, verify:

- [ ] Cover is slide 1
- [ ] Closing is last slide
- [ ] Section headers precede every new topic
- [ ] No 2+ consecutive same-background slides (excluding section headers)
- [ ] At least 4 different content layout types used
- [ ] No more than 2 consecutive same-layout-type slides
- [ ] Split/image slides outnumber plain white slides

### Step 4: Present to User

Show the outline to the user for approval before generating slides:

```markdown
## Proposed Deck Structure (16 slides)

| # | Layout | Background | Content |
|:--|:-------|:-----------|:--------|
| 1 | Cover | Dark | Title + Date |
| 2 | Table of Contents | Dark | 5 sections |
| 3 | Section Header | Dark | "Context" |
| ... | ... | ... | ... |

**Layout variety**: 8 different types used ✅
**Background alternation**: Verified ✅
```

---

## Layout Selection by Content Type

| Content Type | Recommended Layout | Avoid |
|:------------|:-------------------|:------|
| Bullet points (3-5 items) | Split with Photo (#4) | White (#7) |
| Bullet points (6+ items) | White (#7) or 3-Column (#8) | — |
| Key metrics / KPIs | KPI At-a-Glance (#12) | White (#7) |
| Comparison (3 items) | 3-Column Deep Blue (#8) | White (#7) |
| Process / workflow | Steps / Process Flow (#10) | White (#7) |
| Financial data | Financial Charts (#15) | — |
| Case study | Split Photo (#16) | White (#7) |
| Team / people | People / Team Photo (#14) | — |
| Geographic data | World Map + Data (#9) | — |
| Strategy pillars | 3-Photo Highlights (#13) | White (#7) |
| ESG / sustainability | Sustainability Roadmap (#17) | — |
| History / timeline | History Timeline (#18) | — |
| Video embed | Full-Bleed Video (#11) | — |
| Dense text (unavoidable) | White / Standard (#7) | — |

---

## Anti-Patterns

- ❌ **"Wall of White"** — 3+ consecutive white-background slides
- ❌ **"Missing Signposts"** — content slides without preceding section headers
- ❌ **"Monotone Deck"** — using only 1-2 layout types for the entire deck
- ❌ **"Text-Heavy Default"** — defaulting to White/Standard when a visual layout exists
- ❌ **"Skipping the Outline"** — generating slides without presenting the plan to the user first
