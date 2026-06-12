---
name: GWS CLI Reference
description: Syntax reference for the Google Workspace CLI (gws) — covers Gmail, Calendar, Tasks, Forms, People, and other services NOT available as granular tools. Use this when workspace-tools doesn't have a dedicated tool.
---

# GWS CLI Reference Skill

## Role

You are using the `workspace-cli` MCP server which wraps the [Google Workspace CLI](https://github.com/googleworkspace/cli). This skill teaches you the correct syntax for services that do **NOT** have dedicated granular tools.

## When to Use

Use the CLI wrapper (`gws_read`, `gws_write`, `gws_destructive`) **only** when `workspace-tools` does not have a dedicated tool. Check `workspace-tools` first for:
- **Slides** — use `slides_*` tools instead
- **Docs** — use `docs_*` tools instead
- **Sheets** — use `sheets_*` tools instead
- **Drive** — use `drive_*` tools instead
- **Branded content** — use `create_vopak_presentation` / `create_vopak_document`

 **Use the CLI for**: Gmail, Calendar, Tasks, Forms, People, Admin, Groups, Chat

## Command Structure

```
<service> <resource> <verb> [--params JSON]
```

Output format is always JSON (auto-appended by the server).

---

## Gmail

```bash
# Search messages
gmail messages list --params '{"maxResults": 10, "q": "is:unread"}'

# Get a specific message
gmail messages get --params '{"id": "MESSAGE_ID"}'

# Get full thread
gmail threads get --params '{"id": "THREAD_ID"}'

# Search with advanced query
gmail messages list --params '{"q": "from:boss@vopak.com after:2026/06/01 has:attachment"}'

# Send a message (gws_write — requires reason)
gmail messages send --params '{"to": "colleague@vopak.com", "subject": "Weekly Report", "body": "<p>Hi,</p><p>Please find the report attached.</p>", "cc": "team@vopak.com"}'

# Reply to a message (gws_write)
gmail messages send --params '{"to": "colleague@vopak.com", "subject": "Re: Weekly Report", "body": "Thanks!", "threadId": "THREAD_ID", "inReplyTo": "MESSAGE_ID"}'

# Create a draft (gws_write)
gmail drafts create --params '{"to": "user@vopak.com", "subject": "Draft", "body": "Draft content"}'

# List drafts
gmail drafts list

# List labels
gmail labels list

# Create label (gws_write)
gmail labels create --params '{"name": "Projects/Q3"}'

# Trash a message (gws_destructive — triggers HITL)
gmail messages trash --params '{"id": "MESSAGE_ID"}'

# Delete a label (gws_destructive)
gmail labels delete --params '{"id": "LABEL_ID"}'
```

---

## Calendar

```bash
# List upcoming events
calendar events list --params '{"calendarId": "primary", "maxResults": 10, "timeMin": "2026-06-12T00:00:00Z", "orderBy": "startTime", "singleEvents": true}'

# Get a specific event
calendar events get --params '{"calendarId": "primary", "eventId": "EVENT_ID"}'

# List all calendars
calendar calendars list

# Create an event (gws_write)
calendar events create --params '{"calendarId": "primary", "summary": "Team Standup", "description": "Daily sync", "start": {"dateTime": "2026-06-15T09:00:00+02:00"}, "end": {"dateTime": "2026-06-15T09:30:00+02:00"}, "attendees": [{"email": "colleague@vopak.com"}]}'

# Create all-day event (gws_write)
calendar events create --params '{"calendarId": "primary", "summary": "Company Holiday", "start": {"date": "2026-07-04"}, "end": {"date": "2026-07-05"}}'

# Update an event (gws_write)
calendar events update --params '{"calendarId": "primary", "eventId": "EVENT_ID", "summary": "Updated Title", "start": {"dateTime": "2026-06-15T10:00:00+02:00"}, "end": {"dateTime": "2026-06-15T11:00:00+02:00"}}'

# Delete an event (gws_destructive — triggers HITL)
calendar events delete --params '{"calendarId": "primary", "eventId": "EVENT_ID"}'
```

---

## Tasks

```bash
# List all task lists
tasks tasklists list

# Get tasks from a list
tasks tasks list --params '{"tasklist": "TASKLIST_ID"}'

# Get a specific task
tasks tasks get --params '{"tasklist": "TASKLIST_ID", "task": "TASK_ID"}'

# Create a task (gws_write)
tasks tasks create --params '{"tasklist": "TASKLIST_ID", "title": "Review Q3 budget", "notes": "Check variance report", "due": "2026-06-20T00:00:00Z"}'

# Create a task list (gws_write)
tasks tasklists create --params '{"title": "Sprint 42"}'

# Update task status (gws_write)
tasks tasks update --params '{"tasklist": "TASKLIST_ID", "task": "TASK_ID", "status": "completed"}'

# Delete a task (gws_destructive)
tasks tasks delete --params '{"tasklist": "TASKLIST_ID", "task": "TASK_ID"}'
```

---

## Forms

```bash
# Get form structure
forms forms get --params '{"formId": "FORM_ID"}'

# List form responses
forms responses list --params '{"formId": "FORM_ID"}'

# Get a specific response
forms responses get --params '{"formId": "FORM_ID", "responseId": "RESPONSE_ID"}'
```

> **Note**: Forms API is read-only for responses. Form creation/editing requires the Forms API v1 which has limited CLI support.

---

## People / Contacts

```bash
# Search directory (company contacts)
people people searchDirectoryPeople --params '{"query": "john", "readMask": "names,emailAddresses,phoneNumbers", "sources": ["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"]}'

# List personal contacts
people people connections list --params '{"resourceName": "people/me", "personFields": "names,emailAddresses"}'

# Get a person's profile
people people get --params '{"resourceName": "people/PERSON_ID", "personFields": "names,emailAddresses,organizations"}'

# Create a contact (gws_write)
people people createContact --params '{"names": [{"givenName": "Jane", "familyName": "Doe"}], "emailAddresses": [{"value": "jane@example.com"}]}'
```

---

## Drive Permissions (not in granular tools)

```bash
# List permissions on a file
drive permissions list --params '{"fileId": "FILE_ID"}'

# Share a file (gws_write)
drive permissions create --params '{"fileId": "FILE_ID", "type": "user", "role": "reader", "emailAddress": "colleague@vopak.com"}'

# Share with domain (gws_write)
drive permissions create --params '{"fileId": "FILE_ID", "type": "domain", "role": "reader", "domain": "vopak.com"}'

# Remove sharing (gws_destructive)
drive permissions delete --params '{"fileId": "FILE_ID", "permissionId": "PERMISSION_ID"}'
```

---

## Safety Rules

| Tool | Allowed Verbs | Enforcement |
|:-----|:-------------|:-----------|
| `gws_read` | `get`, `list`, `query`, `export`, `download`, `schema` | Server-side verb gate — rejects write/delete verbs |
| `gws_write` | `create`, `update`, `send`, `insert`, `patch`, `copy`, `move` | Verb gate + `reason` parameter required |
| `gws_destructive` | `delete`, `trash` | Verb gate + `reason` required + ️ HITL confirmation |

## Tips for Accuracy

1. **Always use `--params`** with valid JSON (single quotes around the JSON object)
2. **Check workspace-tools first** — granular tools are always more accurate than CLI
3. **Start with read** — use `gws_read` to list/get before modifying
4. **Provide context in `reason`** — helps audit trail and HITL reviewers
5. **Use exact service/resource/verb** naming from the examples above
