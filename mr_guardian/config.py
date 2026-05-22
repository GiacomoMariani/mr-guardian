"""Runtime configuration loaded from environment variables."""

import os
from pathlib import Path

ENV_FILE = Path(".env")


class Settings:
    """Resolved MR Guardian runtime settings."""

    def __init__(self) -> None:
        load_env_file()
        self.repo_path = Path(os.getenv("MR_GUARDIAN_REPO_PATH", "."))
        self.policy_path = Path(
            os.getenv("MR_GUARDIAN_POLICY_PATH", "sources/yaml/unity-policy.yml")
        )
        self.policy_dir = Path(os.getenv("MR_GUARDIAN_POLICY_DIR", "sources/yaml"))
        self.markdown_dir = Path(os.getenv("MR_GUARDIAN_MARKDOWN_DIR", "sources/markdown"))
        self.history_db_path = Path(
            os.getenv("MR_GUARDIAN_HISTORY_DB_PATH", ".mr-guardian/history.sqlite")
        )
        self.reports_dir = Path(os.getenv("MR_GUARDIAN_REPORTS_DIR", "examples/reports"))


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
