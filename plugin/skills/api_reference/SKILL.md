---
name: API Reference
description: "Syntax reference for the api_read, api_write, and api_delete bridge tools. Activate when the tool_guard skill has confirmed no granular tool exists and the agent needs to call Gmail, Calendar, Forms, Tasks, Admin, Groups, People, Chat, or raw Drive endpoints."
---

# API Reference — Workspace API Bridge Syntax

> **Prerequisite**: Only use `api_*` tools after confirming no granular tool exists (see `tool_guard` skill).

## Tool Overview

| Tool | HTTP Methods | Safety | Description |
|:-----|:------------|:-------|:------------|
| `api_read` | GET | Safe | Read-only operations — list, get, search |
| `api_write` | POST, PUT, PATCH | Modifying | Create, update, send operations |
| `api_delete` | DELETE | **DESTRUCTIVE** — HITL required | Permanent deletion of resources |

---

## Common Patterns

### Gmail

```json
// List unread messages
api_read({
  "url": "https://gmail.googleapis.com/gmail/v1/users/me/messages?q=is:unread&maxResults=10"
})

// Get a specific message
api_read({
  "url": "https://gmail.googleapis.com/gmail/v1/users/me/messages/MESSAGE_ID"
})

// Send an email
api_write({
  "url": "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
  "body": {
    "raw": "BASE64_ENCODED_RFC822_MESSAGE"
  }
})

// Create a draft
api_write({
  "url": "https://gmail.googleapis.com/gmail/v1/users/me/drafts",
  "body": {
    "message": {
      "raw": "BASE64_ENCODED_RFC822_MESSAGE"
    }
  }
})

// List labels
api_read({
  "url": "https://gmail.googleapis.com/gmail/v1/users/me/labels"
})
```

### Calendar

```json
// List events
api_read({
  "url": "https://www.googleapis.com/calendar/v3/calendars/primary/events?timeMin=2026-06-01T00:00:00Z&maxResults=10&orderBy=startTime&singleEvents=true"
})

// Create an event
api_write({
  "url": "https://www.googleapis.com/calendar/v3/calendars/primary/events",
  "body": {
    "summary": "Team Standup",
    "start": { "dateTime": "2026-06-15T09:00:00+02:00" },
    "end": { "dateTime": "2026-06-15T09:30:00+02:00" },
    "attendees": [
      { "email": "colleague@vopak.com" }
    ]
  }
})

// Delete an event (DESTRUCTIVE — HITL required)
api_delete({
  "url": "https://www.googleapis.com/calendar/v3/calendars/primary/events/EVENT_ID"
})
```

### Tasks

```json
// List task lists
api_read({
  "url": "https://tasks.googleapis.com/tasks/v1/users/@me/lists"
})

// List tasks in a list
api_read({
  "url": "https://tasks.googleapis.com/tasks/v1/lists/TASKLIST_ID/tasks"
})

// Create a task
api_write({
  "url": "https://tasks.googleapis.com/tasks/v1/lists/TASKLIST_ID/tasks",
  "body": {
    "title": "Review Q2 report",
    "due": "2026-06-20T00:00:00Z"
  }
})
```

### Forms

```json
// Get form structure
api_read({
  "url": "https://forms.googleapis.com/v1/forms/FORM_ID"
})

// List form responses
api_read({
  "url": "https://forms.googleapis.com/v1/forms/FORM_ID/responses"
})
```

### Admin Directory

```json
// List users in domain
api_read({
  "url": "https://admin.googleapis.com/admin/directory/v1/users?domain=vopak.com&maxResults=50"
})

// Get a specific user
api_read({
  "url": "https://admin.googleapis.com/admin/directory/v1/users/user@vopak.com"
})

// List groups
api_read({
  "url": "https://admin.googleapis.com/admin/directory/v1/groups?domain=vopak.com"
})

// List group members
api_read({
  "url": "https://admin.googleapis.com/admin/directory/v1/groups/GROUP_KEY/members"
})
```

### People / Contacts

```json
// Search directory
api_read({
  "url": "https://people.googleapis.com/v1/people:searchDirectoryPeople?query=John&readMask=names,emailAddresses&sources=DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"
})

// Get user profile
api_read({
  "url": "https://people.googleapis.com/v1/people/me?personFields=names,emailAddresses,photos"
})
```

### Chat

```json
// List spaces
api_read({
  "url": "https://chat.googleapis.com/v1/spaces"
})

// Send a message to a space
api_write({
  "url": "https://chat.googleapis.com/v1/spaces/SPACE_ID/messages",
  "body": {
    "text": "Hello from the agent!"
  }
})
```

### Drive (Edge Cases Only)

> **Remember**: Use `drive_list` and `drive_create_folders` for standard operations. Only use `api_*` for permissions, sharing, rename, move, or delete.

```json
// List sharing permissions
api_read({
  "url": "https://www.googleapis.com/drive/v3/files/FILE_ID/permissions"
})

// Share a file
api_write({
  "url": "https://www.googleapis.com/drive/v3/files/FILE_ID/permissions",
  "body": {
    "type": "user",
    "role": "writer",
    "emailAddress": "colleague@vopak.com"
  }
})

// Rename a file
api_write({
  "url": "https://www.googleapis.com/drive/v3/files/FILE_ID",
  "body": {
    "name": "New File Name"
  }
})

// Delete a file (DESTRUCTIVE — HITL required)
api_delete({
  "url": "https://www.googleapis.com/drive/v3/files/FILE_ID"
})
```

### Slides — Speaker Notes (via API Bridge)

> Speaker notes don't have a dedicated granular tool. Use the API bridge.

```json
// Read speaker notes for a slide
api_read({
  "url": "https://slides.googleapis.com/v1/presentations/PRESENTATION_ID/pages/SLIDE_OBJECT_ID?fields=slideProperties.notesPage.notesProperties,slideProperties.notesPage.pageElements"
})

// Update speaker notes — use slides_batch_update with updateTextStyle/insertText
// on the notes page shape (more reliable than raw API)
```

---

## Safety Rules

| Tool | Allowed | Blocked | Enforcement |
|:-----|:--------|:--------|:------------|
| `api_read` | GET requests | POST, PUT, PATCH, DELETE | Server-side rejection |
| `api_write` | POST, PUT, PATCH | GET, DELETE | Server-side rejection |
| `api_delete` | DELETE | GET, POST, PUT, PATCH | Server-side + **HITL confirmation** |

## URL Construction Tips

1. **Always use full URLs** — include the base domain (e.g., `https://gmail.googleapis.com/...`)
2. **Query parameters** — append to URL for GET requests (e.g., `?q=is:unread&maxResults=10`)
3. **Path parameters** — substitute directly in URL (e.g., `/messages/MESSAGE_ID`)
4. **Request body** — JSON object in `body` parameter for POST/PUT/PATCH
5. **Fields mask** — use `?fields=...` to limit response size and reduce token usage
