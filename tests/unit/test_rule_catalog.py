"""Tests for the dashboard rule catalog (ticket 059)."""

from pathlib import Path

from mr_guardian.policies.catalog import load_rule_catalog, summarize_catalog

_POLICY_A = """\
version: 1
rules:
  - id: DET-001
    type: deterministic
    implementation: size_changed_files
    evaluation: mr_structure
    enabled: true
    severity: blocking
    source: a.yml#DET-001
    description: Det rule.
  - id: LLM-001
    type: llm
    evaluation: coding
    enabled: true
    severity: warning
    source: a.yml#LLM-001
    description: LLM rule.
    prompt: Review the diff.
"""

_POLICY_B = """\
version: 1
rules:
  - id: DET-001
    type: deterministic
    implementation: size_changed_lines
    evaluation: coding
    enabled: false
    severity: info
    source: b.yml#DET-001
    description: Overrides DET-001.
"""


def _write(directory: Path, name: str, text: str) -> None:
    (directory / name).write_text(text, encoding="utf-8")


def test_catalog_maps_rule_ids(tmp_path: Path) -> None:
    _write(tmp_path, "a.yml", _POLICY_A)

    catalog = load_rule_catalog(tmp_path)

    assert set(catalog) == {"DET-001", "LLM-001"}
    assert catalog["LLM-001"].prompt == "Review the diff."
    assert catalog.get("UNKNOWN") is None


def test_later_file_wins_on_duplicate_id(tmp_path: Path) -> None:
    _write(tmp_path, "a.yml", _POLICY_A)
    _write(tmp_path, "b.yml", _POLICY_B)

    catalog = load_rule_catalog(tmp_path)

    assert catalog["DET-001"].source == "b.yml#DET-001"
    assert catalog["DET-001"].enabled is False


def test_summary_counts(tmp_path: Path) -> None:
    _write(tmp_path, "a.yml", _POLICY_A)

    summary = summarize_catalog(load_rule_catalog(tmp_path))

    assert summary.total == 2
    assert summary.by_type == {"deterministic": 1, "llm": 1}
    assert summary.by_dimension == {"mr_structure": 1, "coding": 1}
    assert summary.blocking == 1


def test_loads_real_policy_directory() -> None:
    catalog = load_rule_catalog("sources/yaml")

    assert "UNITY-INPUT-001" in catalog
    assert "UNITY-ASSET-MEMORY-001" in catalog
    assert catalog["UNITY-ASYNC-LLM-001"].type == "llm"

    summary = summarize_catalog(catalog)
    assert summary.by_type.get("llm", 0) >= 20
    assert summary.by_type.get("deterministic", 0) >= 20
