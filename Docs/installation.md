# Installation

Use Python 3.10 or newer.

## Install

From the repository root, install with the extras you need. Extras are additive — combine
them with commas (e.g. `".[dashboard,ai]"`).

| Extra | Command | Adds |
|---|---|---|
| _(none)_ | `python -m pip install -e .` | CLI runtime only |
| `dashboard` | `python -m pip install -e ".[dashboard]"` | Streamlit dashboard |
| `server` | `python -m pip install -e ".[server]"` | FastAPI / Uvicorn webhook + manual-review service |
| `gitlab` | `python -m pip install -e ".[gitlab]"` | GitLab API client for posting MR review comments |
| `ai` | `python -m pip install -e ".[ai]"` | OpenAI-backed LLM rules |
| `dev` | `python -m pip install -e ".[dev]"` | Test, lint, and type-check tools |
| `all` | `python -m pip install -e ".[all]"` | Everything except `dev` tools |

**Recommended for local development** (everything):

```bash
python -m pip install -e ".[dev,dashboard,server,ai]"
```

The minimal install also exposes the `mr-guardian` console script:

```bash
python -m pip install -e .
mr-guardian review --base main
```

Installed packages include default YAML policies. When `sources/yaml` exists in the
current project MR Guardian uses those repo-local policies; when it is missing or empty it
falls back to packaged defaults. Set `MR_GUARDIAN_POLICY_DIR` or pass `--policy-dir` to use
team-specific policies.

On Windows, if `mr-guardian` is not found after installation, add the Python Scripts
directory shown by pip to your user `PATH`:

```powershell
[Environment]::SetEnvironmentVariable(
  "Path",
  [Environment]::GetEnvironmentVariable("Path", "User") + ";C:\Users\Jack\AppData\Roaming\Python\Python314\Scripts",
  "User"
)
```

Then close and reopen PowerShell.

## Requirements Files

Editable extras are preferred while developing. For environments that use
`pip install -r`, each extra has a matching requirements file:

| Requirements file | Matches |
|---|---|
| `requirements.txt` | base CLI |
| `requirements-dev.txt` | `dev` |
| `requirements-dashboard.txt` | `dashboard` |
| `requirements-server.txt` | `server` |
| `requirements-ai.txt` | `ai` |
| `requirements-all.txt` | `dev` + `dashboard` + `server` + `ai` |

```bash
python -m pip install -r requirements-all.txt
```

## Environment Setup

Copy the template:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

For deterministic-only review, no API key is required.

For OpenAI-backed LLM rules:

```env
MR_GUARDIAN_LLM_PROVIDER=openai
MR_GUARDIAN_OPENAI_API_KEY=your_openai_api_key_here
MR_GUARDIAN_OPENAI_MODEL=gpt-4.1-mini
MR_GUARDIAN_LLM_SUMMARY_ENABLED=false
MR_GUARDIAN_LLM_SUMMARY_MAX_CHARS=700
```

If the OpenAI package is missing, LLM findings will show:

```text
LLM rule skipped: OpenAI support requires installing mr-guardian[ai].
```

Fix it with:

```bash
python -m pip install -e ".[ai]"
```

## Run Commands

CLI review:

```bash
python -m mr_guardian.cli.main review --base main --no-store
```

Stored review history:

```bash
python -m mr_guardian.cli.main logs
python -m mr_guardian.cli.main log-report 1
python -m mr_guardian.cli.main clear-logs --yes
```

Manual review import:

```bash
python -m mr_guardian.cli.main submit-manual-review --file personal-notes/review.json
```

Dashboard:

```bash
python -m streamlit run app/streamlit_app.py
```

When running from an installed wheel outside the source checkout:

```powershell
$dashboard = python -c "from pathlib import Path; import app.streamlit_app; print(Path(app.streamlit_app.__file__))"
python -m streamlit run $dashboard
```

FastAPI webhook service:

```bash
python -m uvicorn app.api:app --host 0.0.0.0 --port 8000
```

Docker:

```bash
docker build -t mr-guardian .
docker run --rm -p 8000:8000 mr-guardian
```

Wheel packaging:

```bash
python -m pip wheel . --no-deps -w dist
```

See [packaging.md](packaging.md) for package contents and smoke checks.

## Verification

Run the project checks:

```bash
python -m pytest
python -m ruff check .
python -m mypy mr_guardian
```
