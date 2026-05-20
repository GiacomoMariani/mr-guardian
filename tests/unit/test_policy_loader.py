from pathlib import Path

import pytest

from mr_guardian.policies import PolicyValidationError, PolicyYamlError, load_policy


def write_policy(tmp_path: Path, content: str) -> Path:
    policy_path = tmp_path / "policy.yml"
    policy_path.write_text(content, encoding="utf-8")
    return policy_path


def valid_policy_yaml(*, enabled: bool = True, severity: str = "blocking") -> str:
    enabled_value = "true" if enabled else "false"
    return f"""
version: 1

best_practices:
  local_markdown_path: "sources/markdown/UnityBestPractices.md"
  require_rule_id_links: true

rules:
  - id: MR-META-001
    enabled: {enabled_value}
    severity: {severity}
    source: UnityBestPractices.md#MR-META-001
    description: MR must include a test plan.
"""


def test_loads_valid_policy(tmp_path: Path) -> None:
    policy_path = write_policy(tmp_path, valid_policy_yaml())

    policy = load_policy(policy_path)

    assert policy.version == 1
    assert policy.best_practices.local_markdown_path == Path(
        "sources/markdown/UnityBestPractices.md"
    )
    assert policy.best_practices.require_rule_id_links is True
    assert policy.rules[0].id == "MR-META-001"
    assert policy.rules[0].enabled is True
    assert policy.rules[0].severity == "blocking"
    assert policy.rules[0].source == "UnityBestPractices.md#MR-META-001"
    assert policy.rules[0].description == "MR must include a test plan."


def test_fails_on_missing_version(tmp_path: Path) -> None:
    policy_path = write_policy(tmp_path, valid_policy_yaml().replace("version: 1\n\n", ""))

    with pytest.raises(PolicyValidationError, match="version"):
        load_policy(policy_path)


def test_fails_on_missing_best_practices(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path,
        """
version: 1

rules:
  - id: MR-META-001
    enabled: true
    severity: blocking
    source: UnityBestPractices.md#MR-META-001
    description: MR must include a test plan.
""",
    )

    with pytest.raises(PolicyValidationError, match="best_practices"):
        load_policy(policy_path)


def test_fails_on_missing_rule_id(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path,
        """
version: 1

best_practices:
  local_markdown_path: "sources/markdown/UnityBestPractices.md"
  require_rule_id_links: true

rules:
  - enabled: true
    severity: blocking
    source: UnityBestPractices.md#MR-META-001
    description: MR must include a test plan.
""",
    )

    with pytest.raises(PolicyValidationError, match="id"):
        load_policy(policy_path)


def test_fails_on_invalid_severity(tmp_path: Path) -> None:
    policy_path = write_policy(tmp_path, valid_policy_yaml(severity="critical"))

    with pytest.raises(PolicyValidationError, match="severity"):
        load_policy(policy_path)


def test_fails_on_invalid_yaml_syntax(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path,
        """
version: 1
best_practices:
  local_markdown_path: "sources/markdown/UnityBestPractices.md"
  require_rule_id_links: true
rules:
  - id: MR-META-001
    enabled: true
    severity: blocking
    source: [unterminated
""",
    )

    with pytest.raises(PolicyYamlError, match="Invalid YAML"):
        load_policy(policy_path)


def test_preserves_disabled_rules(tmp_path: Path) -> None:
    policy_path = write_policy(tmp_path, valid_policy_yaml(enabled=False, severity="info"))

    policy = load_policy(policy_path)

    assert len(policy.rules) == 1
    assert policy.rules[0].id == "MR-META-001"
    assert policy.rules[0].enabled is False
    assert policy.rules[0].severity == "info"
