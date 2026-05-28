# Agent Setup Prompt

Copy this prompt into a coding agent when you want help setting up MR Guardian
inside a project.

```text
You are helping me set up MR Guardian for a repository.

Work from tracked project files and documentation only. Do not rely on ignored
local agent notes such as AGENTS.md, personal-notes/, tickets/, .codex/, or
.agents/.

Goal:
- Install MR Guardian.
- Configure it for the target repository.
- Verify that local review, dashboard, and optional GitLab webhook setup are
  understood and runnable.
- Explain any environment-specific issue clearly.

Start by inspecting:
- README.md
- Docs/installation.md
- Docs/architecture.md
- Docs/llm-rule-authoring.md
- Docs/docker-deployment.md if deployment is relevant
- .env.example
- pyproject.toml

Setup steps:
1. Confirm the Python version is 3.10 or newer.
2. Install the appropriate dependencies:
   - development setup:
     python -m pip install -e ".[dev,dashboard,server,ai]"
   - minimal CLI setup:
     python -m pip install -e .
   - dashboard only:
     python -m pip install -e ".[dashboard]"
   - server/webhook support:
     python -m pip install -e ".[server]"
   - OpenAI-backed LLM rules:
     python -m pip install -e ".[ai]"
3. Copy .env.example to .env.
4. Configure the important paths:
   - MR_GUARDIAN_REPO_PATH: repository to review
   - MR_GUARDIAN_POLICY_DIR: directory containing YAML policy rules
   - MR_GUARDIAN_HISTORY_DB_PATH: SQLite review history path
5. Do not hardcode real secrets in committed files.
6. If optional LLM rules are needed, set:
   - MR_GUARDIAN_LLM_PROVIDER=openai
   - MR_GUARDIAN_OPENAI_API_KEY
   - MR_GUARDIAN_OPENAI_MODEL
7. If GitLab webhook automation is needed, set:
   - GITLAB_WEBHOOK_SECRET
   - GITLAB_BASE_URL
   - GITLAB_REMOTE_NAME
   - GITLAB_WORKTREE_DIR
   - GITLAB_POST_REVIEW_COMMENTS
   - GITLAB_TOKEN if GitLab API comment posting is enabled

Verification commands:
- python -m mr_guardian.cli.main review --base main --no-store
- python -m mr_guardian.cli.main logs
- python -m streamlit run app/streamlit_app.py
- python -m uvicorn app.api:app --host 0.0.0.0 --port 8000

Development checks, if this is a source checkout:
- python -m pytest
- python -m ruff check .
- python -m mypy mr_guardian

Answer these common setup questions:
- Is MR Guardian GitLab-only?
  No. Local Git review works without GitLab. GitLab is currently the supported
  remote Merge Request webhook integration.
- Can I run it locally without GitLab?
  Yes. Use the CLI review command against a local Git branch.
- Where do YAML rules live?
  Runtime policy rules live in the directory configured by
  MR_GUARDIAN_POLICY_DIR, usually sources/yaml.
- Where is review history stored?
  SQLite history is stored at MR_GUARDIAN_HISTORY_DB_PATH.
- How do I enable optional AI rules?
  Install the ai extra, set MR_GUARDIAN_LLM_PROVIDER=openai, and provide
  MR_GUARDIAN_OPENAI_API_KEY.
- Where do I set the OpenAI API key?
  Set MR_GUARDIAN_OPENAI_API_KEY in .env or in the shell environment. Do not
  commit real keys.
- How do I run the dashboard?
  Install dashboard dependencies and run:
  python -m streamlit run app/streamlit_app.py
- How do I run the required checks?
  Run pytest, ruff, and mypy with python -m as shown above.

Keep setup changes minimal. Avoid editing README.md unless I explicitly ask for
documentation changes. If a command cannot run, report the exact command,
the failure, and the likely fix.
```
