"""Tests for review rule involvement + rule source links (tickets 059/060)."""

from mr_guardian.core.review_rules import rules_that_ran
from mr_guardian.models.review import Finding


def _finding(rule_id: str, severity: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        message="m",
        source=f"unity-policy.yml#{rule_id}",
        evaluation="coding",
    )


def test_rules_that_ran_dedups_and_orders_by_severity() -> None:
    findings = [
        _finding("R-INFO", "info"),
        _finding("R-BLOCK", "blocking"),
        _finding("R-WARN", "warning"),
        _finding("R-BLOCK", "blocking"),
    ]
    triggered = ["R-ONLY-TRIGGERED", "R-BLOCK"]

    assert rules_that_ran(findings, triggered) == [
        "R-BLOCK",
        "R-WARN",
        "R-INFO",
        "R-ONLY-TRIGGERED",
    ]


def test_rules_that_ran_empty() -> None:
    assert rules_that_ran([], []) == []


def test_rule_source_url_maps_to_repo_file() -> None:
    from app.streamlit_app import _rule_source_url

    assert _rule_source_url("unity-policy.yml#UNITY-INPUT-001") == (
        "https://github.com/GiacomoMariani/mr-guardian"
        "/blob/main/sources/yaml/unity-policy.yml"
    )
    assert _rule_source_url("local-all-policies") is None
