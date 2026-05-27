from pathlib import Path

import pytest

from mr_guardian.policies import (
    PolicyValidationError,
    PolicyYamlError,
    load_policies_from_directory,
    load_policy,
)


def write_policy(tmp_path: Path, content: str) -> Path:
    policy_path = tmp_path / "policy.yml"
    policy_path.write_text(content, encoding="utf-8")
    return policy_path


def valid_policy_yaml(*, enabled: bool = True, severity: str = "blocking") -> str:
    enabled_value = "true" if enabled else "false"
    return f"""
version: 1

rules:
  - id: MR-META-001
    type: deterministic
    implementation: mr_required_section
    enabled: {enabled_value}
    severity: {severity}
    source: unity-policy.yml#MR-META-001
    description: MR must include a test plan.
    parameters:
      require:
        mr_sections:
          - Test Plan
"""


def test_loads_valid_policy(tmp_path: Path) -> None:
    policy_path = write_policy(tmp_path, valid_policy_yaml())

    policy = load_policy(policy_path)

    assert policy.version == 1
    assert policy.rules[0].id == "MR-META-001"
    assert policy.rules[0].type == "deterministic"
    assert policy.rules[0].implementation == "mr_required_section"
    assert policy.rules[0].enabled is True
    assert policy.rules[0].severity == "blocking"
    assert policy.rules[0].source == "unity-policy.yml#MR-META-001"
    assert policy.rules[0].description == "MR must include a test plan."
    assert policy.rules[0].parameters == {"require": {"mr_sections": ["Test Plan"]}}


def test_fails_on_missing_version(tmp_path: Path) -> None:
    policy_path = write_policy(tmp_path, valid_policy_yaml().replace("version: 1\n\n", ""))

    with pytest.raises(PolicyValidationError, match="version"):
        load_policy(policy_path)


def test_loads_policy_without_external_metadata(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path,
        """
version: 1

rules:
  - id: MR-META-001
    type: deterministic
    implementation: mr_required_section
    enabled: true
    severity: blocking
    source: unity-policy.yml#MR-META-001
    description: MR must include a test plan.
""",
    )

    policy = load_policy(policy_path)

    assert policy.version == 1
    assert policy.rules[0].id == "MR-META-001"


def test_fails_on_unexpected_top_level_config(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path,
        """
version: 1

history:
  enabled: true

rules:
  - id: MR-META-001
    type: deterministic
    implementation: mr_required_section
    enabled: true
    severity: blocking
    source: unity-policy.yml#MR-META-001
    description: MR must include a test plan.
""",
    )

    with pytest.raises(PolicyValidationError, match="history"):
        load_policy(policy_path)


def test_fails_on_missing_rule_id(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path,
        """
version: 1

rules:
  - type: deterministic
    implementation: mr_required_section
    enabled: true
    severity: blocking
    source: unity-policy.yml#MR-META-001
    description: MR must include a test plan.
""",
    )

    with pytest.raises(PolicyValidationError, match="id"):
        load_policy(policy_path)


def test_fails_on_missing_rule_type(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path,
        """
version: 1

rules:
  - id: MR-META-001
    enabled: true
    severity: blocking
    source: unity-policy.yml#MR-META-001
    description: MR must include a test plan.
""",
    )

    with pytest.raises(PolicyValidationError, match="type"):
        load_policy(policy_path)


def test_fails_on_invalid_rule_type(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path,
        valid_policy_yaml().replace("type: deterministic", "type: manual"),
    )

    with pytest.raises(PolicyValidationError, match="type"):
        load_policy(policy_path)


def test_fails_on_missing_deterministic_implementation(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path,
        valid_policy_yaml().replace("    implementation: mr_required_section\n", ""),
    )

    with pytest.raises(PolicyValidationError, match="implementation"):
        load_policy(policy_path)


def test_fails_on_blocking_llm_rule(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path,
        """
version: 1

rules:
  - id: PYTHON-DESIGN-LLM-001
    type: llm
    enabled: true
    severity: blocking
    source: python-policy.yml#PYTHON-DESIGN-LLM-001
    description: Check design concerns.
    prompt: Review the diff.
""",
    )

    with pytest.raises(PolicyValidationError, match="blocking"):
        load_policy(policy_path)


def test_fails_on_llm_rule_missing_prompt(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path,
        """
version: 1

rules:
  - id: PYTHON-DESIGN-LLM-001
    type: llm
    enabled: true
    severity: info
    source: python-policy.yml#PYTHON-DESIGN-LLM-001
    description: Check design concerns.
""",
    )

    with pytest.raises(PolicyValidationError, match="prompt"):
        load_policy(policy_path)


def test_fails_on_unexpected_rule_level_parameters(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path,
        """
version: 1

rules:
  - id: PYTHON-PRINT-001
    type: deterministic
    implementation: python_print
    enabled: true
    severity: warning
    source: python-policy.yml#PYTHON-PRINT-001
    description: Python code should use logging instead of print calls.
    match:
      added_lines_contain:
        - "print("
""",
    )

    with pytest.raises(PolicyValidationError, match="match"):
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
rules:
  - id: MR-META-001
    type: deterministic
    implementation: mr_required_section
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


def test_loads_all_yaml_policies_from_directory(tmp_path: Path) -> None:
    write_policy(tmp_path, valid_policy_yaml())
    second_policy_path = tmp_path / "python-policy.yaml"
    second_policy_path.write_text(
        valid_policy_yaml().replace("MR-META-001", "PYTHON-PRINT-001"),
        encoding="utf-8",
    )

    policies = load_policies_from_directory(tmp_path)

    assert len(policies) == 2
    assert {policy.rules[0].id for policy in policies} == {"MR-META-001", "PYTHON-PRINT-001"}


def test_unity_policy_loads_lifecycle_llm_rule() -> None:
    policy = load_policy(Path("sources/yaml/unity-policy.yml"))

    rule = next(rule for rule in policy.rules if rule.id == "UNITY-LIFECYCLE-LLM-001")

    assert rule.type == "llm"
    assert rule.enabled is True
    assert rule.severity == "info"
    assert rule.source == "unity-policy.yml#UNITY-LIFECYCLE-LLM-001"
    assert rule.prompt is not None
    assert "Awake" in rule.prompt
    assert "OnEnable" in rule.prompt
    assert "Only report issues grounded in the diff." in rule.prompt
    assert rule.parameters["inputs"] == {
        "include_diff": True,
        "include_changed_files": True,
    }
    assert rule.parameters["output_contract"] == {
        "max_findings": 3,
        "allow_blocking": False,
    }


def test_unity_policy_loads_ui_performance_llm_rule() -> None:
    policy = load_policy(Path("sources/yaml/unity-policy.yml"))

    rule = next(rule for rule in policy.rules if rule.id == "UNITY-UI-PERF-LLM-001")

    assert rule.type == "llm"
    assert rule.enabled is True
    assert rule.severity == "info"
    assert rule.source == "unity-policy.yml#UNITY-UI-PERF-LLM-001"
    assert rule.prompt is not None
    assert "Canvas rebuilds" in rule.prompt
    assert "raycast targets" in rule.prompt
    assert "return no findings" in rule.prompt
    assert rule.parameters["inputs"] == {
        "include_diff": True,
        "include_changed_files": True,
    }
    assert rule.parameters["output_contract"] == {
        "max_findings": 3,
        "allow_blocking": False,
    }


def test_unity_policy_loads_asset_loading_llm_rule() -> None:
    policy = load_policy(Path("sources/yaml/unity-policy.yml"))

    rule = next(rule for rule in policy.rules if rule.id == "UNITY-ASSET-LOADING-LLM-001")

    assert rule.type == "llm"
    assert rule.enabled is True
    assert rule.severity == "info"
    assert rule.source == "unity-policy.yml#UNITY-ASSET-LOADING-LLM-001"
    assert rule.prompt is not None
    assert "Addressables" in rule.prompt
    assert "AssetBundle" in rule.prompt
    assert "memory lifecycle" in rule.prompt
    assert "platform-specific content" in rule.prompt
    assert "UNITY-RESOURCES-001" in rule.prompt
    assert rule.parameters["inputs"] == {
        "include_diff": True,
        "include_changed_files": True,
    }
    assert rule.parameters["output_contract"] == {
        "max_findings": 3,
        "allow_blocking": False,
    }


def test_unity_policy_loads_physics_llm_rule() -> None:
    policy = load_policy(Path("sources/yaml/unity-policy.yml"))

    rule = next(rule for rule in policy.rules if rule.id == "UNITY-PHYSICS-LLM-001")

    assert rule.type == "llm"
    assert rule.enabled is True
    assert rule.severity == "info"
    assert rule.source == "unity-policy.yml#UNITY-PHYSICS-LLM-001"
    assert rule.prompt is not None
    assert "Update versus FixedUpdate" in rule.prompt
    assert "layer masks" in rule.prompt
    assert "raycasts or casts" in rule.prompt
    assert "Rigidbody movement" in rule.prompt
    assert "collision or trigger" in rule.prompt
    assert rule.parameters["inputs"] == {
        "include_diff": True,
        "include_changed_files": True,
    }
    assert rule.parameters["output_contract"] == {
        "max_findings": 3,
        "allow_blocking": False,
    }


def test_unity_policy_loads_scriptableobject_llm_rule() -> None:
    policy = load_policy(Path("sources/yaml/unity-policy.yml"))

    rule = next(rule for rule in policy.rules if rule.id == "UNITY-SCRIPTABLEOBJECT-LLM-001")

    assert rule.type == "llm"
    assert rule.enabled is True
    assert rule.severity == "info"
    assert rule.source == "unity-policy.yml#UNITY-SCRIPTABLEOBJECT-LLM-001"
    assert rule.prompt is not None
    assert "ScriptableObject" in rule.prompt
    assert "hidden global state" in rule.prompt
    assert "mutable runtime state" in rule.prompt
    assert "non-stateless" in rule.prompt
    assert "editor/runtime state leakage" in rule.prompt
    assert rule.parameters["inputs"] == {
        "include_diff": True,
        "include_changed_files": True,
    }
    assert rule.parameters["output_contract"] == {
        "max_findings": 3,
        "allow_blocking": False,
    }
