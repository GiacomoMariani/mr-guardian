# Dashboard ETA Note API

MR Guardian can store a global delivery ETA note for the dashboard. The note is
manual or externally supplied; MR Guardian does not generate the forecast.

The widget's phase name and "Readiness" percentage come from the latest weekly LLM
review (see [weekly-llm-review.md](weekly-llm-review.md)); this note supplies the
message and target date shown beneath them.

The dashboard always displays the fixed disclaimer:

```text
Based on AI evaluation. Confirm dates and delivery risk with the team.
```

## Read Current Note

```http
GET /dashboard/eta-note
```

Returns the current note, or `null` when no note has been set.

## Update Note

```http
POST /dashboard/eta-note
```

Request body:

```json
{
  "message": "Milestone looks merge-ready by Friday.",
  "target_date": "2026-06-05"
}
```

`target_date` is optional. Every successful `POST` appends a new note; previous notes
are retained as history. `GET /dashboard/eta-note` returns the most recent one.

If `MR_GUARDIAN_ADMIN_TOKEN` is configured, include:

```http
X-MR-Guardian-Admin-Token: your-admin-token
```

## Note History

```http
GET /dashboard/eta-note/history
```

Returns stored notes, most recent first (default 20; pass `?limit=N` to change the
count). `GET /dashboard/eta-note` returns the latest of these. The dashboard surfaces
older notes under a collapsed "Previous notes" view.

## Schema

```http
GET /dashboard/eta-note/schema
```

Returns the JSON schema for accepted update payloads.
