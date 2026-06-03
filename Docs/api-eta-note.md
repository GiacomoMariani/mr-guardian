# Dashboard ETA Note API

MR Guardian can store one global delivery ETA note for the dashboard. The note is
manual or externally supplied; MR Guardian does not generate the forecast.

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

`target_date` is optional. Every successful `POST` overwrites the previous note.
Previous values are not retained.

If `MR_GUARDIAN_ADMIN_TOKEN` is configured, include:

```http
X-MR-Guardian-Admin-Token: your-admin-token
```

## Schema

```http
GET /dashboard/eta-note/schema
```

Returns the JSON schema for accepted update payloads.
