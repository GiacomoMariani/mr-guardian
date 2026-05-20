from pathlib import Path

import pytest
from typer.testing import CliRunner

from mr_guardian.cli.main import app
from mr_guardian.core.inspection import InspectionResult, InspectionSuiteResult
from mr_guardian.models.review import EngineReviewResult, FindingCounts
from mr_guardian.models.review_input import ReviewInput


def test_review_command_exits_successfully() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["review", "--base", "main", "--policy", "sources/yaml/unity-policy.yml"],
    )

    assert result.exit_code == 0


def test_review_command_outputs_placeholder_report() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["review", "--base", "main", "--policy", "sources/yaml/unity-policy.yml"],
    )

    assert "MR Guardian Review" in result.output
    assert "**Risk:** Unknown" in result.output
    assert "No rules have been implemented yet." in result.output


def test_review_command_accepts_base_and_policy_options() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["review", "--base", "develop", "--policy", "custom-policy.yml"],
    )

    assert result.exit_code == 0


def test_inspect_command_outputs_pipeline_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_inspect_review(
        *,
        base_ref: str,
        policy_path: Path,
    ) -> InspectionResult:
        return InspectionResult(
            policy_path=policy_path,
            policy_version=1,
            enabled_rule_count=8,
            disabled_rule_count=0,
            base_ref=base_ref,
            review_input=ReviewInput(base_ref=base_ref, changed_files=[]),
            engine_result=EngineReviewResult(
                risk="none",
                findings=[],
                counts=FindingCounts(),
            ),
        )

    monkeypatch.setattr("mr_guardian.cli.main.inspect_review", fake_inspect_review)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["inspect", "--base", "main", "--policy", "sources/yaml/unity-policy.yml"],
    )

    assert result.exit_code == 0
    assert "MR Guardian Inspect" in result.output
    assert "Rules: 8 enabled, 0 disabled" in result.output
    assert "Risk: none" in result.output


def test_inspect_all_command_outputs_all_policy_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_inspect_all_reviews(
        *,
        base_ref: str,
        policy_directory: Path,
    ) -> InspectionSuiteResult:
        return InspectionSuiteResult(
            policy_directory=policy_directory,
            policy_results=[
                InspectionResult(
                    policy_path=policy_directory / "python-policy.yml",
                    policy_version=1,
                    enabled_rule_count=1,
                    disabled_rule_count=0,
                    base_ref=base_ref,
                    review_input=ReviewInput(base_ref=base_ref, changed_files=[]),
                    engine_result=EngineReviewResult(
                        risk="none",
                        findings=[],
                        counts=FindingCounts(),
                    ),
                )
            ],
        )

    monkeypatch.setattr("mr_guardian.cli.main.inspect_all_reviews", fake_inspect_all_reviews)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["inspect-all", "--base", "main"],
    )

    assert result.exit_code == 0
    assert "MR Guardian Inspect All" in result.output
    assert "Policy files: 1" in result.output
    assert "python-policy.yml" in result.output
