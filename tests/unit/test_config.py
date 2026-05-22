import os
from pathlib import Path

import pytest

from mr_guardian.config import load_env_file


def test_load_env_file_sets_missing_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        """
MR_GUARDIAN_POLICY_DIR=custom/policies
MR_GUARDIAN_HISTORY_DB_PATH=".custom/history.sqlite"
""",
        encoding="utf-8",
    )
    monkeypatch.delenv("MR_GUARDIAN_POLICY_DIR", raising=False)
    monkeypatch.delenv("MR_GUARDIAN_HISTORY_DB_PATH", raising=False)

    load_env_file(env_path)

    assert os.environ["MR_GUARDIAN_POLICY_DIR"] == "custom/policies"
    assert os.environ["MR_GUARDIAN_HISTORY_DB_PATH"] == ".custom/history.sqlite"


def test_load_env_file_does_not_override_existing_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("MR_GUARDIAN_POLICY_DIR=custom/policies\n", encoding="utf-8")
    monkeypatch.setenv("MR_GUARDIAN_POLICY_DIR", "from-shell")

    load_env_file(env_path)

    assert os.environ["MR_GUARDIAN_POLICY_DIR"] == "from-shell"
