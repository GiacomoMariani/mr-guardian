# Docker and Render Deployment

MR Guardian has initial Docker support for the FastAPI webhook service. The
Docker image installs the server and AI dependencies, so OpenAI-backed LLM rules
can run when `MR_GUARDIAN_LLM_PROVIDER=openai` and
`MR_GUARDIAN_OPENAI_API_KEY` are configured.

## Build

```bash
docker build -t mr-guardian .
```

The Dockerfile installs the package with:

```bash
python -m pip install -e ".[server,ai]"
```

## Run Locally

```bash
docker run --rm -p 8000:8000 \
  -e GITLAB_WEBHOOK_SECRET=local-secret \
  -e GITLAB_POST_REVIEW_COMMENTS=false \
  mr-guardian
```

Check the service:

```bash
curl http://localhost:8000/healthz
```

Expected response:

```json
{"status":"ok"}
```

## Server Entrypoint

The container starts the FastAPI app with Uvicorn:

```bash
python -m uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-8000}
```

This is compatible with Render because Render provides the `PORT` environment
variable.

## Runtime Requirements

A deployed MR Guardian instance needs:

- Git installed in the container. The provided Dockerfile includes it.
- YAML policies available at `MR_GUARDIAN_POLICY_DIR`.
- Access to a Git repository checkout at `MR_GUARDIAN_REPO_PATH`.
- Git credentials capable of fetching source and target branches.
- A writable directory for temporary worktrees at `GITLAB_WORKTREE_DIR`.
- A persistence decision for `MR_GUARDIAN_HISTORY_DB_PATH`.

The Docker image includes MR Guardian's own policy files under `/app/sources/yaml`.
It does not include a `.git` directory. For webhook reviews, point
`MR_GUARDIAN_REPO_PATH` at a mounted or cloned Git repository that has the
expected GitLab remote.

## Environment Variables

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

## Repository Access

Webhook reviews use local Git commands against `MR_GUARDIAN_REPO_PATH`. In a
container this path must be a real Git checkout. Common options are:

- Mount a prepared repository into the container.
- Clone the repository as part of platform setup before starting the service.
- Extend the Docker image later with an entrypoint script that clones the
  repository from a configured URL.

Git fetch authentication should be configured through the remote URL or Git
credential setup available inside the container.

## SQLite Persistence

SQLite history is stored at `MR_GUARDIAN_HISTORY_DB_PATH`. In Docker, mount a
volume if review history must survive container recreation:

```bash
docker run --rm -p 8000:8000 \
  -v mr-guardian-data:/data \
  mr-guardian
```

On Render, attach a persistent disk and place `MR_GUARDIAN_HISTORY_DB_PATH` on
that disk. Without a persistent disk, history is ephemeral.

The current app is safest as a single-instance service because review jobs use
local filesystem worktrees and an in-process background job store.

## Render Setup Outline

1. Create a Render Web Service from the repository.
2. Select Docker deployment.
3. Set required environment variables in Render.
4. Add a persistent disk if review history must survive deploys and restarts.
5. Configure GitLab webhook URL:

```text
https://your-render-service.onrender.com/webhooks/gitlab
```

6. Set GitLab's webhook secret to match `GITLAB_WEBHOOK_SECRET`.
7. Configure repository access for `MR_GUARDIAN_REPO_PATH`.
8. Open or reopen a Merge Request and confirm:
   - webhook returns `202`
   - `/webhook-jobs/{job_id}` reaches `succeeded`
   - review history is stored
   - MR comment is posted when `GITLAB_POST_REVIEW_COMMENTS=true`

## Smoke Checks

After deployment:

```bash
curl https://your-service.example.com/healthz
curl https://your-service.example.com/webhook-jobs/not-found
```

The first command should return `{"status":"ok"}`. The second should return a
404 JSON response, proving the FastAPI app is reachable.
