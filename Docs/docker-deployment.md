# Docker and Render Deployment Notes

MR Guardian is not yet fully packaged for Docker deployment. This document
defines the deployment target and the work required to support Docker and Render
cleanly.

## Current Web Entrypoint

The server entrypoint is the FastAPI app:

```bash
python -m uvicorn app.api:app --host 0.0.0.0 --port 8000
```

For Render, the process must bind to Render's `PORT` environment variable:

```bash
python -m uvicorn app.api:app --host 0.0.0.0 --port "$PORT"
```

## Required Runtime Capabilities

A deployed MR Guardian instance needs:

- Python 3.10 or newer.
- Git installed in the container.
- The MR Guardian package installed with server dependencies.
- Access to a Git repository checkout at `MR_GUARDIAN_REPO_PATH`.
- Git credentials capable of fetching source and target branches.
- YAML policies available at `MR_GUARDIAN_POLICY_DIR`.
- A writable directory for worktrees at `GITLAB_WORKTREE_DIR`.
- A persistence decision for `MR_GUARDIAN_HISTORY_DB_PATH`.

## Render Persistence Consideration

SQLite history is stored at `MR_GUARDIAN_HISTORY_DB_PATH`. On Render, the normal
container filesystem is ephemeral. For durable review history, use one of these
options:

- Attach a Render persistent disk and place `MR_GUARDIAN_HISTORY_DB_PATH` on it.
- Use ephemeral SQLite only for smoke testing.
- Later replace SQLite with a managed database if multi-instance deployment is
  required.

The current app is safest as a single-instance service because review jobs use
local filesystem worktrees and an in-process background job store.

## Required Environment Variables

```env
MR_GUARDIAN_REPO_PATH=/app/repository
MR_GUARDIAN_POLICY_DIR=/app/sources/yaml
MR_GUARDIAN_HISTORY_DB_PATH=/data/history.sqlite
GITLAB_WORKTREE_DIR=/tmp/mr-guardian-worktrees

GITLAB_BASE_URL=https://gitlab.com
GITLAB_REMOTE_NAME=origin
GITLAB_WEBHOOK_SECRET=replace_with_gitlab_webhook_secret
GITLAB_TOKEN=replace_with_token_that_can_post_mr_notes
GITLAB_POST_REVIEW_COMMENTS=true
GITLAB_API_TIMEOUT_SECONDS=10

MR_GUARDIAN_LLM_PROVIDER=disabled
MR_GUARDIAN_OPENAI_API_KEY=
MR_GUARDIAN_OPENAI_MODEL=gpt-4.1-mini
MR_GUARDIAN_OPENAI_TIMEOUT_SECONDS=30
MR_GUARDIAN_OPENAI_MAX_RETRIES=2
```

## Docker Support Work Required

Before calling Docker support ready, add:

- `Dockerfile` for the FastAPI service.
- `.dockerignore`.
- Render-compatible start command using `$PORT`.
- Container build check in documentation or CI.
- Clear instructions for mounting or cloning the reviewed Git repository.
- Clear instructions for Git credentials inside the container.
- A deployment smoke test for:
  - `GET /webhook-jobs/not-found`
  - `POST /webhooks/gitlab`
  - background review job completion
  - optional GitLab MR comment delivery

## Draft Dockerfile Shape

This is the intended direction, not yet committed as runtime support:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY mr_guardian ./mr_guardian
COPY app ./app
COPY sources ./sources

RUN python -m pip install --no-cache-dir -e ".[server]"

ENV MR_GUARDIAN_REPO_PATH=/app
ENV MR_GUARDIAN_POLICY_DIR=/app/sources/yaml
ENV GITLAB_WORKTREE_DIR=/tmp/mr-guardian-worktrees

CMD ["sh", "-c", "python -m uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

## Render Setup Outline

1. Create a Render Web Service from the repository.
2. Use Docker deployment once the `Dockerfile` is added.
3. Set all required environment variables in Render.
4. Add a persistent disk if review history must survive deploys and restarts.
5. Configure GitLab webhook URL:

```text
https://your-render-service.onrender.com/webhooks/gitlab
```

6. Set GitLab's webhook secret to match `GITLAB_WEBHOOK_SECRET`.
7. Open or reopen a Merge Request and confirm:
   - webhook returns `202`
   - `/webhook-jobs/{job_id}` reaches `succeeded`
   - review history is stored
   - MR comment is posted when `GITLAB_POST_REVIEW_COMMENTS=true`
