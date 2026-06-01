import os
from pathlib import Path

import pytest

from mr_guardian.config import Settings, load_env_file


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


def test_settings_load_llm_summary_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MR_GUARDIAN_LLM_SUMMARY_ENABLED", "true")
    monkeypatch.setenv("MR_GUARDIAN_LLM_SUMMARY_MAX_CHARS", "512")

    settings = Settings()

    assert settings.llm_summary_enabled is True
    assert settings.llm_summary_max_chars == 512


def test_settings_load_developer_profile_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MR_GUARDIAN_DEVELOPER_PROFILE_ENABLED", "true")
    monkeypatch.setenv("MR_GUARDIAN_DEVELOPER_PROFILE_LOOKBACK_DAYS", "45")
    monkeypatch.setenv("MR_GUARDIAN_DEVELOPER_PROFILE_MAX_CHARS", "600")

    settings = Settings()

    assert settings.developer_profile_enabled is True
    assert settings.developer_profile_lookback_days == 45
    assert settings.developer_profile_max_chars == 600


def test_settings_load_admin_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MR_GUARDIAN_ADMIN_TOKEN", "private-token")

    settings = Settings()

    assert settings.admin_token == "private-token"
