# MR Guardian

Python-based Unity Merge Request review assistant.

MR Guardian reviews local Git diffs or GitLab merge requests against Unity best-practice policies.

YAML files in `sources/yaml/` are the runtime source of truth. Markdown files in
`sources/markdown/` are human guidance only and are not loaded or validated by the tool.

## YAML Policy Format

YAML policy files are a set of executable rules. The only top-level policy fields
are:

- `version`
- `rules`

Every item under `rules` is a rule. All runtime rules come from YAML, and each
rule must declare its execution type:

- `deterministic`: implemented in Python and registered in MR Guardian.
- `llm`: prompt-driven advisory checks that will be sent to an LLM with review context.

Each rule has stable metadata plus optional parameters:

```yaml
version: 1

rules:
  - id: PYTHON-PRINT-001
    type: deterministic
    implementation: python_print
    enabled: true
    severity: warning
    source: python-policy.yml#PYTHON-PRINT-001
    description: Python code should use logging instead of newly introduced print calls.
    parameters:
      match:
        changed_files:
          - "**/*.py"
        added_lines_contain:
          - "print("
```

Rule-specific settings belong under `parameters`. Deterministic rules require an
`implementation`. LLM rules require a `prompt` and cannot use `severity: blocking`.

## Development

Use Python 3.10 or newer.

Install dependencies:

```bash
python -m pip install -e ".[dev,dashboard]"
```

Equivalent requirements files are available when editable extras are not
convenient:

```bash
python -m pip install -r requirements-dev.txt
python -m pip install -r requirements-dashboard.txt
python -m pip install -r requirements-server.txt
python -m pip install -r requirements-ai.txt
```

Configure local paths:

```bash
cp .env.example .env
```

MR Guardian reads `.env` automatically. Use it to set the default repository,
YAML policy directory, default YAML policy file, human guidance directory,
SQLite history database, and reports directory. Shell environment variables
override values from `.env`.

Reports include the developer identity from the reviewed Git repository. MR
Guardian reads `git config user.name` first and falls back to `git config
user.email` when no name is configured.

Run the CLI:

```bash
python -m mr_guardian.cli.main review --base main
```

By default, MR Guardian evaluates every YAML policy file in the configured policy
directory, `sources/yaml`.

Run a local review without storing it in history:

```bash
python -m mr_guardian.cli.main review --base main --no-store
```

Override the policy directory when needed:

```bash
python -m mr_guardian.cli.main review --base main --policy-dir sources/yaml
```

LLM rules are skipped by default unless an LLM provider is configured. To enable
OpenAI-backed advisory LLM rules, install the AI extra and set the provider and
API key:

```bash
python -m pip install -e ".[dev,dashboard,ai]"
```

```env
MR_GUARDIAN_LLM_PROVIDER=openai
MR_GUARDIAN_OPENAI_API_KEY=your_openai_api_key_here
MR_GUARDIAN_OPENAI_MODEL=gpt-4.1-mini
MR_GUARDIAN_OPENAI_TIMEOUT_SECONDS=30
MR_GUARDIAN_OPENAI_MAX_RETRIES=2
```

LLM rules are isolated from deterministic review execution. Timeouts, malformed
responses, rate limits, and provider failures are reported as advisory `info`
findings for the affected LLM rule; deterministic findings still complete.

Run the CLI with local MR metadata:

```bash
python -m mr_guardian.cli.main review --base main --title "Add player movement" --description-file mr-description.md
```

The MR metadata options are useful for local reviews because local Git does not
provide a merge request title or description. Use `--description` for short text
or `--description-file` for a Markdown file.

Show stored review logs in a readable table:

```bash
python -m mr_guardian.cli.main logs
```

Limit how many recent review logs are shown:

```bash
python -m mr_guardian.cli.main logs --limit 10
```

Show the generated report for a stored review ID:

```bash
python -m mr_guardian.cli.main log-report 1
```

Run the Streamlit review-history dashboard:

```bash
python -m streamlit run app/streamlit_app.py
```

Run the GitLab webhook FastAPI service:

```bash
python -m pip install -e ".[server]"
python -m uvicorn app.api:app --host 0.0.0.0 --port 8000
```

Docker and Render deployment notes are tracked in
[docs/docker-deployment.md](docs/docker-deployment.md). Docker packaging is not
implemented yet.

Configure GitLab to send Merge Request webhooks to:

```text
POST /webhooks/gitlab
```

If `GITLAB_WEBHOOK_SECRET` is set, MR Guardian validates GitLab's
`X-Gitlab-Token` header. Opened and reopened Merge Request events trigger the
same local review flow as `review --base main`. The HTTP request returns after
queueing a background job; use the returned `job_id` with
`GET /webhook-jobs/{job_id}` to check status. Successful jobs are stored in
SQLite with review scope `gitlab-webhook`.

To post completed webhook review reports back to GitLab as Merge Request notes,
configure a token with permission to create MR notes and enable comment
delivery:

```env
GITLAB_TOKEN=your_gitlab_token_with_note_permission_here
GITLAB_POST_REVIEW_COMMENTS=true
GITLAB_API_TIMEOUT_SECONDS=10
```

Before reviewing, the service fetches the GitLab source and target branches from
`GITLAB_REMOTE_NAME` and creates a temporary detached worktree under
`GITLAB_WORKTREE_DIR`. It reviews the source branch worktree against the fetched
target branch ref, stores the result, and removes the temporary worktree. The
service can post GitLab comments when `GITLAB_POST_REVIEW_COMMENTS=true`.

Reports start with a short reviewer-focus section and a compact triggered-rule
overview before the full details. Findings are grouped by severity and displayed
non-blocking findings are capped per severity so large reviews stay readable.
Blocking findings are never hidden.

Configure authentication for private repository fetches through the Git remote
or Git credential manager used by `MR_GUARDIAN_REPO_PATH`.

Remove all stored review logs:

```bash
python -m mr_guardian.cli.main clear-logs --yes
```

Run checks:

```bash
pytest
ruff check .
mypy mr_guardian
```
