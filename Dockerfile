FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PORT=8000
ENV MR_GUARDIAN_REPO_PATH=/app/repository
ENV MR_GUARDIAN_POLICY_DIR=/app/sources/yaml
ENV MR_GUARDIAN_HISTORY_DB_PATH=/data/history.sqlite
ENV GITLAB_WORKTREE_DIR=/tmp/mr-guardian-worktrees

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /data /tmp/mr-guardian-worktrees /app/repository \
    && chown -R appuser:appuser /app /data /tmp/mr-guardian-worktrees

COPY pyproject.toml README.md ./
COPY mr_guardian ./mr_guardian
COPY app ./app
COPY sources ./sources

RUN python -m pip install --upgrade pip \
    && python -m pip install -e ".[server,ai]"

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
