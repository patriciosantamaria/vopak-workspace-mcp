---
name: Template Picker
description: "Select the correct Vopak template from the embedded registry for branded content creation. Activate when the user requests creating a new document or presentation."
---

# Template Picker — Select the Right Vopak Template

> **Purpose**: Guide the agent to pick the correct branded template from the 17 registered templates before calling `branded_create_presentation` or `branded_create_document`.

## When to Activate

- User says "create a document", "create a presentation", "write a report", "make an ADD", "draft a TDD"
- Any request that results in creating a new Google Slides or Google Docs file
- When `branded_health_check` is called to verify template availability

---

## Template Registry (17 Templates)

### Presentations (1)

| Template | Use When |
|:---------|:---------|
| **Vopak Global Slide Deck** | Any new presentation — this is the ONLY slide template |

### Documents (16)

| Template | Acronym | Use When |
|:---------|:--------|:---------|
| **Architecture Design Document** | ADD | System architecture, technical design decisions, component diagrams |
| **Technical Design Document** | TDD | Detailed implementation specs, API designs, data models |
| **User Manual** | — | End-user guides, how-to documentation |
| **Project Charter** | — | Project kickoff, scope, objectives, stakeholders |
| **Business Requirements** | BRD | Business needs, functional requirements |
| **Release Notes** | — | Version changes, bug fixes, new features |
| **Meeting Minutes** | — | Meeting records, decisions, action items |
| **Status Report** | — | Weekly/monthly progress updates |
| **Risk Assessment** | — | Risk identification, mitigation strategies |
| **Test Plan** | — | Test strategy, test cases, acceptance criteria |
| **Runbook** | — | Operational procedures, incident response |
| **Change Request** | CR | Scope changes, impact analysis |
| **Training Material** | — | Course content, learning objectives |
| **Proposal** | — | Client proposals, solution briefs |
| **Audit Report** | — | Compliance audits, security reviews |
| **Generic Document** | — | Anything that doesn't fit the above categories |

---

## Selection Strategy

### Step 1: Identify Content Type

```
User request → Classify:
├── Is it a presentation? → Use "Vopak Global Slide Deck"
├── Is it a technical document? → ADD, TDD, Test Plan, or Runbook
├── Is it a project document? → Project Charter, BRD, or Change Request
├── Is it a report? → Status Report, Audit Report, or Risk Assessment
├── Is it for training? → Training Material or User Manual
├── Is it a proposal? → Proposal
├── Is it meeting-related? → Meeting Minutes
├── Is it a release? → Release Notes
└── None of the above? → Generic Document
```

### Step 2: Confirm with User (if ambiguous)

If the request could match multiple templates, ask:

> "I can create this as a **[Template A]** or **[Template B]**. Which format works best?"

### Step 3: Create via Branded Tool

```
branded_create_presentation({
  templateType: "presentation",
  title: "Q2 Strategy Review",
  placeholders: { "{{TITLE}}": "Q2 Strategy Review", "{{DATE}}": "June 2026" }
})

branded_create_document({
  templateType: "add",
  title: "Workspace MCP Architecture",
  placeholders: { "{{PROJECT_NAME}}": "vopak-workspace-mcp" }
})
```

---

## Keyword → Template Mapping

| User Keywords | Template |
|:-------------|:---------|
| "architecture", "ADD", "system design", "component diagram" | Architecture Design Document |
| "technical design", "TDD", "implementation spec", "API design" | Technical Design Document |
| "user manual", "user guide", "how-to", "instructions" | User Manual |
| "project charter", "kickoff", "project plan" | Project Charter |
| "requirements", "BRD", "business needs" | Business Requirements |
| "release notes", "changelog", "what's new" | Release Notes |
| "meeting", "minutes", "MoM", "action items" | Meeting Minutes |
| "status", "progress", "weekly update" | Status Report |
| "risk", "risk assessment", "mitigation" | Risk Assessment |
| "test plan", "test cases", "QA", "acceptance criteria" | Test Plan |
| "runbook", "operations", "incident", "SOP" | Runbook |
| "change request", "CR", "scope change" | Change Request |
| "training", "course", "learning", "workshop" | Training Material |
| "proposal", "solution brief", "pitch" | Proposal |
| "audit", "compliance", "security review" | Audit Report |
| "presentation", "deck", "slides", "pitch deck" | Vopak Global Slide Deck |

---

## Placeholder Format

Templates use **mustache-style placeholders** `{{PLACEHOLDER}}` that get replaced during creation:

### Common Placeholders (all templates)

| Placeholder | Description | Example |
|:-----------|:-----------|:--------|
| `{{TITLE}}` | Document or presentation title | "Q2 Strategy Review" |
| `{{DATE}}` | Creation date | "June 2026" |
| `{{AUTHOR}}` | Author name | "Patricio Santamaria" |
| `{{VERSION}}` | Document version | "1.0" |

### Document-Specific Placeholders

| Placeholder | Templates | Description |
|:-----------|:---------|:-----------|
| `{{PROJECT_NAME}}` | ADD, TDD, Test Plan, Runbook | Project identifier |
| `{{DEPARTMENT}}` | All | Business unit |
| `{{CLASSIFICATION}}` | All | Confidentiality level |
| `{{APPROVER}}` | ADD, TDD, CR | Approval authority |

---

## Anti-Patterns

- ❌ **NEVER** create a blank document from scratch — always use a branded template
- ❌ **NEVER** guess the template ID — use `branded_health_check` to verify availability
- ❌ **NEVER** copy a template manually via `api_write` — use `branded_create_*`
- ❌ **NEVER** hardcode Drive file IDs — the template registry is embedded in the server binary
