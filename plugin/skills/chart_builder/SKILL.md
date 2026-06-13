---
name: Chart Builder
description: "Create data-driven charts for Slides and Sheets using QuickChart.io URLs or native Sheets charts. Enforces Vopak brand colors and prevents hallucinated data. Activate when the user asks to visualize data, create charts, or add data slides."
---

# Chart Builder — Data-Driven Charts with Brand Compliance

> **Purpose**: Generate charts that use **real data only**, enforce Vopak brand colors, and integrate seamlessly into Google Slides and Sheets.

## When to Activate

- User says "chart this", "visualize", "graph", "plot"
- Creating data slides in a presentation
- Adding charts to a Google Sheets spreadsheet
- Any request involving bar charts, line charts, pie charts, or similar visualizations

---

## Chart Generation Methods

### Method 1: QuickChart.io → Google Slides (Preferred for Slides)

Use `slides_insert_chart` to generate a chart image via QuickChart.io and insert it directly into a slide.

```json
slides_insert_chart({
  "presentationId": "PRES_ID",
  "slideObjectId": "SLIDE_ID",
  "chartConfig": {
    "type": "bar",
    "data": {
      "labels": ["Q1", "Q2", "Q3", "Q4"],
      "datasets": [{
        "label": "Revenue (M€)",
        "data": [120, 135, 142, 158],
        "backgroundColor": "#0a2373"
      }]
    },
    "options": {
      "plugins": {
        "title": { "display": true, "text": "Quarterly Revenue 2026" }
      }
    }
  }
})
```

### Method 2: Native Sheets Chart (Preferred for Sheets)

Use `sheets_create_chart` for charts embedded in a spreadsheet.

```json
sheets_create_chart({
  "spreadsheetId": "SHEET_ID",
  "sheetId": 0,
  "chartType": "BAR",
  "title": "Quarterly Revenue",
  "sourceRange": "Sheet1!A1:B5"
})
```

### Method 3: Sheets Chart → Slides (For Live Data)

1. Create chart in Sheets with `sheets_create_chart`
2. Link it to a slide via `slides_batch_update` with `createSheetsChart`
3. Chart stays linked and updates when the spreadsheet changes

---

## Vopak Brand Colors for Charts

### Primary Palette (use first)

| Color | Hex | Use For |
|:------|:----|:--------|
| Deep Blue | `#0a2373` | Primary data series, axis labels |
| Cyan | `#00cfe1` | Secondary data series, highlights |
| Light Blue | `#009ef5` | Third data series |

### Extended Palette (for 4+ series)

| Color | Hex | Use For |
|:------|:----|:--------|
| Orange | `#fc7000` | Fourth series, warnings |
| Green | `#52d400` | Fifth series, sustainability |
| Cobalt | `#283ce1` | Sixth series, technology |
| Steel | `#46555a` | Neutral/gray series |

### Color Assignment Order

For multi-series charts, assign colors in this order:
1. `#0a2373` (Deep Blue)
2. `#00cfe1` (Cyan)
3. `#009ef5` (Light Blue)
4. `#fc7000` (Orange)
5. `#52d400` (Green)
6. `#283ce1` (Cobalt)
7. `#46555a` (Steel)

### Tints (for stacked/area charts)

Use 10% increments: `rgba(10, 35, 115, 0.6)` for 60% Deep Blue, etc.

---

## Chart Type Selection Guide

| Data Shape | Chart Type | When |
|:-----------|:-----------|:-----|
| Categories + values | **Bar** (vertical) | Comparing discrete items |
| Categories + values (long labels) | **Horizontal Bar** | Labels don't fit vertically |
| Time series | **Line** | Trends over time |
| Parts of a whole | **Doughnut** | Percentage breakdowns (prefer over pie) |
| Multiple metrics over time | **Multi-line** | Comparing trends |
| Target vs actual | **Bar + Line combo** | Budget vs spend, plan vs actual |
| Two variables | **Scatter** | Correlation analysis |
| Progress toward goal | **Gauge** | KPI dashboards |
| Distribution | **Histogram** | Statistical analysis |

### ❌ Avoid These Chart Types
- **Pie charts** — use doughnut instead (cleaner, more modern)
- **3D charts** — never use; they distort data perception
- **Radar/spider charts** — hard to read; use grouped bars instead

---

## Chart Configuration Templates

### Bar Chart (Most Common)

```json
{
  "type": "bar",
  "data": {
    "labels": ["Label1", "Label2", "Label3"],
    "datasets": [{
      "label": "Series Name",
      "data": [100, 200, 300],
      "backgroundColor": ["#0a2373", "#00cfe1", "#009ef5"]
    }]
  },
  "options": {
    "plugins": {
      "title": { "display": true, "text": "Chart Title", "color": "#0a2373", "font": { "family": "Inter", "size": 16, "weight": "normal" } },
      "legend": { "labels": { "color": "#46555a", "font": { "family": "Inter" } } }
    },
    "scales": {
      "y": { "ticks": { "color": "#46555a" }, "grid": { "color": "#e1e1e1" } },
      "x": { "ticks": { "color": "#46555a" }, "grid": { "display": false } }
    }
  }
}
```

### Line Chart (Trends)

```json
{
  "type": "line",
  "data": {
    "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
    "datasets": [{
      "label": "Metric A",
      "data": [10, 15, 13, 17, 20, 25],
      "borderColor": "#0a2373",
      "backgroundColor": "rgba(10, 35, 115, 0.1)",
      "fill": true,
      "tension": 0.3
    }]
  },
  "options": {
    "plugins": {
      "title": { "display": true, "text": "Monthly Trend", "color": "#0a2373" }
    }
  }
}
```

### Doughnut Chart (Composition)

```json
{
  "type": "doughnut",
  "data": {
    "labels": ["Segment A", "Segment B", "Segment C"],
    "datasets": [{
      "data": [45, 30, 25],
      "backgroundColor": ["#0a2373", "#00cfe1", "#009ef5"]
    }]
  },
  "options": {
    "plugins": {
      "title": { "display": true, "text": "Market Share", "color": "#0a2373" },
      "datalabels": { "color": "#ffffff", "font": { "weight": "bold" } }
    }
  }
}
```

---

## Data Integrity Rules

### RULE 1: Never Hallucinate Data

If the user does not provide specific numbers, you MUST:

1. **Ask for the data** — "I need the actual values to create this chart. Can you share the data?"
2. **Read from a source** — Use `sheets_read_range` or `docs_read_text` to extract real data
3. **Use placeholder labels** — If creating a template, use `[VALUE]` placeholders, never fake numbers

### RULE 2: Always Cite Data Source

When inserting a chart, add a source footnote:
- "Source: Q2 2026 Financial Report"
- "Source: Sheets — Monthly KPI Tracker"
- "Data as of June 2026"

### RULE 3: Verify Data After Chart Creation

```
1. Create chart via slides_insert_chart or sheets_create_chart
2. Get thumbnail: slides_get_thumbnail (for slides)
3. View thumbnail to verify chart rendered correctly
4. Check: Are labels readable? Are colors from brand palette? Is data accurate?
```

---

## Positioning Charts in Slides

### Recommended Sizes (in EMU)

| Layout | Chart Width | Chart Height | X Offset | Y Offset |
|:-------|:-----------|:-------------|:---------|:---------|
| Full-width | 7,800,000 | 4,200,000 | 672,000 | 800,000 |
| Half-width (left) | 3,800,000 | 3,600,000 | 400,000 | 1,000,000 |
| Half-width (right) | 3,800,000 | 3,600,000 | 4,800,000 | 1,000,000 |
| Quarter (top-left) | 3,500,000 | 2,200,000 | 400,000 | 800,000 |

---

## Anti-Patterns

- ❌ **Fake data** — Never invent numbers for a chart
- ❌ **Non-brand colors** — Never use default Chart.js blue/red/green
- ❌ **Pie charts** — Use doughnut instead
- ❌ **3D effects** — Never use 3D chart variants
- ❌ **Bold titles** — Chart titles follow Vopak rule: `font-weight: normal`
- ❌ **Missing source** — Always add a data source citation
- ❌ **Unlabeled axes** — All axes must have clear labels
