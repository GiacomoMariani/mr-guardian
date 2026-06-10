"""Tests for RuleEvaluationContext changed-file access (ticket 058)."""

from pathlib import Path

from mr_guardian.core.engine import run_review
from mr_guardian.models.policy import Policy, PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.models.review_input import ReviewInput
from mr_guardian.rules.base import RuleEvaluationContext
from mr_guardian.rules.registry import RuleRegistry


def _context(repo_root: Path | None = None) -> RuleEvaluationContext:
    return RuleEvaluationContext(
        policy=Policy(version=1, rules=[]),
        review_input=ReviewInput(base_ref="main", changed_files=[]),
        repo_root=repo_root,
    )


def test_read_changed_bytes_returns_file_contents(tmp_path: Path) -> None:
    payload = b"v 0 0 0\nf 1 2 3\n"
    asset = tmp_path / "Assets" / "Models" / "tree.obj"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(payload)

    context = _context(tmp_path)

    assert context.read_changed_bytes(Path("Assets/Models/tree.obj")) == payload


def test_read_changed_bytes_none_without_repo_root() -> None:
    assert _context(None).read_changed_bytes(Path("Assets/Models/tree.obj")) is None


def test_read_changed_bytes_none_when_missing(tmp_path: Path) -> None:
    assert _context(tmp_path).read_changed_bytes(Path("Assets/Missing.obj")) is None


def test_read_changed_bytes_none_for_absolute_path(tmp_path: Path) -> None:
    asset = tmp_path / "outside.obj"
    asset.write_bytes(b"data")

    assert _context(tmp_path).read_changed_bytes(asset) is None


def test_run_review_forwards_repo_root_to_context(tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    class _Probe:
        @property
        def rule_id(self) -> str:
            return "PROBE-001"

        def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
            seen["repo_root"] = context.repo_root
            seen["rule_id"] = rule.id
            return []

    rule = PolicyRule(
        id="PROBE-001",
        type="deterministic",
        implementation="probe",
        enabled=True,
        severity="warning",
        source="unity-policy.yml#PROBE-001",
        description="Probe rule.",
    )

    run_review(
        policy=Policy(version=1, rules=[rule]),
        review_input=ReviewInput(base_ref="main", changed_files=[]),
        rule_registry=RuleRegistry([_Probe()]),
        repo_root=tmp_path,
    )

    assert seen["repo_root"] == tmp_path
