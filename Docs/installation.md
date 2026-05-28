# Installation

Use Python 3.10 or newer. From the repository root, install the mode that
matches what you want to run.

## Recommended Local Development Install

```bash
python -m pip install -e ".[dev,dashboard,server,ai]"
```

This installs:

- CLI runtime dependencies.
- Test, lint, and type-check tools.
- Streamlit dashboard dependencies.
- FastAPI/Uvicorn server dependencies.
- OpenAI dependency for LLM rules.

## Minimal CLI Install

```bash
python -m pip install -e .
```

Use this when you only need:

```bash
python -m mr_guardian.cli.main review --base main
```

The console script is also installed:

```bash
mr-guardian review --base main
```

Installed packages include default YAML policies. When `sources/yaml` exists in
the current project, MR Guardian uses those repo-local policies. When that
directory is missing or empty, it falls back to packaged default policies.
Set `MR_GUARDIAN_POLICY_DIR` or pass `--policy-dir` to use team-specific
policies.

On Windows, if `mr-guardian` is not found after installation, add the Python
Scripts directory shown by pip to your user `PATH`. For example:

```powershell
[Environment]::SetEnvironmentVariable(
  "Path",
  [Environment]::GetEnvironmentVariable("Path", "User") + ";C:\Users\Jack\AppData\Roaming\Python\Python314\Scripts",
  "User"
)
```

Then close and reopen PowerShell.

## Feature-Specific Installs

Dashboard only:

```bash
python -m pip install -e ".[dashboard]"
```

FastAPI webhook server only:

```bash
python -m pip install -e ".[server]"
```

OpenAI-backed LLM rules:

```bash
python -m pip install -e ".[ai]"
```

Everything except development tools:

```bash
python -m pip install -e ".[all]"
```

## Requirements File Installs

Editable extras are preferred while developing this project. Requirements files
are available for environments that use `pip install -r`:

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m pip install -r requirements-dashboard.txt
python -m pip install -r requirements-server.txt
python -m pip install -r requirements-ai.txt
python -m pip install -r requirements-all.txt
```

`requirements-all.txt` includes development, dashboard, server, and AI
dependencies.

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
