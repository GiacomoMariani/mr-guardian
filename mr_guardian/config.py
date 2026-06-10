"""Runtime configuration loaded from environment variables."""

import os
from pathlib import Path

ENV_FILE = Path(".env")


class Settings:
    """Resolved MR Guardian runtime settings."""

    def __init__(self) -> None:
        load_env_file()
        self.repo_path = Path(os.getenv("MR_GUARDIAN_REPO_PATH", "."))
        self.policy_dir = Path(os.getenv("MR_GUARDIAN_POLICY_DIR", "sources/yaml"))
        self.markdown_dir = Path(os.getenv("MR_GUARDIAN_MARKDOWN_DIR", "sources/markdown"))
        self.history_db_path = Path(
            os.getenv("MR_GUARDIAN_HISTORY_DB_PATH", ".mr-guardian/history.sqlite")
        )
        self.reports_dir = Path(os.getenv("MR_GUARDIAN_REPORTS_DIR", "examples/reports"))
        self.admin_token = os.getenv("MR_GUARDIAN_ADMIN_TOKEN", "")
        self.llm_provider = os.getenv("MR_GUARDIAN_LLM_PROVIDER", "disabled")
        self.openai_api_key = os.getenv("MR_GUARDIAN_OPENAI_API_KEY", "")
        self.openai_model = os.getenv("MR_GUARDIAN_OPENAI_MODEL", "gpt-4.1-mini")
        self.openai_timeout_seconds = _float_env("MR_GUARDIAN_OPENAI_TIMEOUT_SECONDS", 30.0)
        self.openai_max_retries = _int_env("MR_GUARDIAN_OPENAI_MAX_RETRIES", 2)
        self.llm_summary_enabled = _bool_env("MR_GUARDIAN_LLM_SUMMARY_ENABLED", False)
        self.llm_summary_max_chars = _int_env("MR_GUARDIAN_LLM_SUMMARY_MAX_CHARS", 700)
        self.gitlab_webhook_secret = os.getenv("GITLAB_WEBHOOK_SECRET", "")
        self.gitlab_token = os.getenv("GITLAB_TOKEN", "")
        self.gitlab_base_url = os.getenv("GITLAB_BASE_URL", "https://gitlab.com")
        self.gitlab_remote_name = os.getenv("GITLAB_REMOTE_NAME", "origin")
        self.gitlab_worktree_dir = Path(os.getenv("GITLAB_WORKTREE_DIR", ".mr-guardian/worktrees"))
        self.gitlab_post_review_comments = _bool_env("GITLAB_POST_REVIEW_COMMENTS", False)
        self.gitlab_api_timeout_seconds = _float_env("GITLAB_API_TIMEOUT_SECONDS", 10.0)


def load_env_file(path: Path = ENV_FILE) -> None:
    """Load simple KEY=VALUE pairs from a local .env file without overriding env vars."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_quotes(value.strip())
        if key:
            os.environ.setdefault(key, value)


def get_settings() -> Settings:
    """Return current runtime settings."""
    return Settings()


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _float_env(key: str, default: float) -> float:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    if parsed <= 0:
        return default
    return parsed


def _int_env(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    if parsed < 0:
        return default
    return parsed


def _bool_env(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
