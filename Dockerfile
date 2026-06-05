# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PORT=8000
ENV HOME=/home/appuser
ENV MR_GUARDIAN_REPO_PATH=/app/repository
ENV MR_GUARDIAN_POLICY_DIR=/app/sources/yaml
ENV MR_GUARDIAN_HISTORY_DB_PATH=/data/history.sqlite
ENV GITLAB_WORKTREE_DIR=/tmp/mr-guardian-worktrees

WORKDIR /app

# Caddy reverse proxy (static binary) for the combined single-port deployment.
COPY --from=caddy:2 /usr/bin/caddy /usr/bin/caddy

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /data /tmp/mr-guardian-worktrees /app/repository \
    && chown -R appuser:appuser /app /data /tmp/mr-guardian-worktrees /home/appuser

COPY pyproject.toml README.md ./
COPY mr_guardian ./mr_guardian
COPY app ./app
COPY sources ./sources
COPY Caddyfile /etc/caddy/Caddyfile
COPY scripts ./scripts

RUN python -m pip install --upgrade pip \
    && python -m pip install -e ".[server,ai,dashboard]" \
    && chmod +x scripts/docker-entrypoint.sh

# Public port for the combined deployment (Render overrides via $PORT).
EXPOSE 8000

# The entrypoint starts as root to fix the data-dir owner, then drops to appuser.
# Default mode "combined" serves the API and dashboard behind one port.
ENTRYPOINT ["bash", "/app/scripts/docker-entrypoint.sh"]
CMD ["combined"]
