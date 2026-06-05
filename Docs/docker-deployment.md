# Docker and Render Deployment

MR Guardian ships as one Docker image that runs three ways, selected by the
entrypoint argument:

| Mode | What runs | Port |
| --- | --- | --- |
| `combined` (default) | Caddy reverse proxy → FastAPI + Streamlit | `$PORT` |
| `api` | FastAPI webhook / manual-review service | `${PORT:-8000}` |
| `dashboard` | Streamlit dashboard | `${PORT:-8501}` |

In `combined` mode (the Render target) one public port serves both apps:

- `/api/*` → FastAPI (the `/api` prefix is stripped, so `/api/healthz` → `/healthz`)
- `/*` → Streamlit dashboard (websockets included)

Both apps share one SQLite database, so data submitted to the API is immediately
visible on the dashboard.

## Build

```bash
docker build -t mr-guardian .
```

The image installs `.[server,ai,dashboard]` and copies a static Caddy binary. It
starts as root only long enough to fix the data-directory owner, then drops to
the non-root `appuser` via `setpriv`.

## Run locally

The default Compose stack runs the API and dashboard as two services (fast
iteration). The `combined` profile mirrors the exact Render artifact.

```bash
# API on :8000, dashboard on :8501 (two services, shared demo DB)
docker compose up --build

# Single combined service, exactly like Render, on :9000
docker compose --profile combined up combined --build
#   dashboard: http://localhost:9000/
#   API:       http://localhost:9000/api/healthz
```

Both mount `./.mr-guardian` so the dashboard shows the local demo history.

## Deploy to Render (combined service)

Render does not run `docker-compose.yml`. The repo includes `render.yaml`, a
Blueprint defining one Docker web service with a persistent disk.

### Why one combined service

A Render web service exposes a single port, and persistent disks are not shared
between services. Two services would put their SQLite databases on separate
disks, so data POSTed to the API would never appear on the dashboard. The
combined service keeps both on one disk behind one port.

### Steps

1. Push this repository to a Git provider connected to Render.
2. In Render: **New → Blueprint**, select the repo. Render reads `render.yaml`.
3. Set the secret env vars (marked `sync: false`) in the Render dashboard:
   - `MR_GUARDIAN_ADMIN_TOKEN` — a strong token; protects the weekly-review,
     ETA-note, and review-deletion endpoints.
   - `MR_GUARDIAN_OPENAI_API_KEY` — only if you set `MR_GUARDIAN_LLM_PROVIDER=openai`.
   - `GITLAB_WEBHOOK_SECRET`, `GITLAB_TOKEN` — only for live GitLab reviews.
4. Confirm region and plan. The persistent disk requires a paid instance type
   (the Blueprint uses `starter`). To trial without persistence, remove the
   `disk:` block and set `plan: free` — data is then lost on each restart.
5. Deploy. Render health-checks `/api/healthz`; FastAPI needs ~2 s to import,
   after which the check passes.

### Endpoints after deploy

- Dashboard: `https://<service>.onrender.com/`
- Health: `https://<service>.onrender.com/api/healthz`
- Manual review submit: `POST https://<service>.onrender.com/api/reviews/manual`
- Weekly review / ETA note: `POST .../api/weekly-llm-reviews/manual` and
  `POST .../api/dashboard/eta-note` — both require the
  `X-MR-Guardian-Admin-Token` header.
- GitLab webhook: `https://<service>.onrender.com/api/webhooks/gitlab`

### Populating data

The dashboard renders whatever is in the database. Submit reviews through the
API (see [`manual-review-submission.md`](manual-review-submission.md) for the
payload shape). On a persistent disk this data survives restarts and deploys.

## Environment variables

| Variable | Purpose | Combined default |
| --- | --- | --- |
| `MR_GUARDIAN_HISTORY_DB_PATH` | SQLite history DB | `/data/history.sqlite` |
| `MR_GUARDIAN_POLICY_DIR` | YAML policies | `/app/sources/yaml` |
| `MR_GUARDIAN_ADMIN_TOKEN` | Protects admin endpoints | _(set in Render)_ |
| `MR_GUARDIAN_LLM_PROVIDER` | `disabled` or `openai` | `disabled` |
| `MR_GUARDIAN_OPENAI_API_KEY` | OpenAI key when enabled | _(set in Render)_ |
| `GITLAB_WEBHOOK_SECRET` / `GITLAB_TOKEN` | GitLab integration | _(set in Render)_ |

Never bake secrets into the image. The dashboard and manual-review submission do
not need an OpenAI key.

## Runtime notes

- **Persistence:** SQLite lives on the Render disk at `/data`. Without a disk,
  history is ephemeral.
- **Single instance:** review jobs use local worktrees and an in-process job
  store, so run one instance (a disk-backed service cannot scale past one).
- **GitLab reviews:** webhook reviews run Git against `MR_GUARDIAN_REPO_PATH`,
  which must be a real checkout. The image has no `.git`; mount or clone a repo
  if you use live reviews. Manual submission and the dashboard do not need this.

## Smoke checks

```bash
curl https://<service>.onrender.com/api/healthz      # {"status":"ok"}
curl https://<service>.onrender.com/_stcore/health   # ok  (dashboard)
```
