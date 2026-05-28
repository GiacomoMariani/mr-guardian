import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mr_guardian.cli.main import app
from mr_guardian.core.review import PolicyReviewResult, ReviewRequest, ReviewResult
from mr_guardian.models.history import ReviewRunCreate
from mr_guardian.models.review import EngineReviewResult, Finding, FindingCounts
from mr_guardian.models.review_input import ChangedFile, DiffHunk, DiffLine, ReviewInput
from mr_guardian.storage import ReviewHistoryStore


def valid_manual_review_payload() -> dict[str, object]:
    return {
        "review_scope": "manual-review",
        "branch_name": "feature/manual-review",
        "title": "TK-777 Manual review",
        "developer_id": "Test Reviewer",
        "policy_version": 1,
        "risk": "none",
        "findings": [],
        "evaluations": [
            {
                "evaluation": "coding",
                "risk": "none",
                "counts": {"blocking": 0, "high": 0, "warning": 0, "info": 0},
                "triggered_rule_ids": [],
            },
            {
                "evaluation": "mr_structure",
                "risk": "none",
                "counts": {"blocking": 0, "high": 0, "warning": 0, "info": 0},
                "triggered_rule_ids": [],
            },
        ],
        "changed_file_count": 0,
        "changed_line_count": 0,
        "generated_review_report": "## Manual Review\n\nLooks good.",
    }


def make_empty_review_result(base: str, policy_directory: Path) -> ReviewResult:
    return ReviewResult(
        base_ref=base,
        policy_directory=policy_directory,
        policy_results=[
            PolicyReviewResult(
                policy_path=policy_directory / "python-policy.yml",
                policy_version=1,
                enabled_rule_count=1,
                disabled_rule_count=0,
                engine_result=EngineReviewResult(
                    risk="none",
                    findings=[],
                    counts=FindingCounts(),
                ),
            )
        ],
        review_input=ReviewInput(base_ref=base, changed_files=[]),
        engine_result=EngineReviewResult(
            risk="none",
            findings=[],
            counts=FindingCounts(),
        ),
    )


def test_review_command_exits_successfully(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_review_merge_request(request: ReviewRequest, **_: object) -> ReviewResult:
        return make_empty_review_result(request.base, request.policy_directory)

    monkeypatch.setattr("mr_guardian.cli.main.review_merge_request", fake_review_merge_request)
    monkeypatch.setattr("mr_guardian.cli.main.store_review_result", lambda *_, **__: None)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["review", "--base", "main", "--title", "TK-234 Add CLI review"],
    )

    assert result.exit_code == 0


def test_review_command_outputs_real_report(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_review_merge_request(request: ReviewRequest, **_: object) -> ReviewResult:
        return make_empty_review_result(request.base, request.policy_directory)

    monkeypatch.setattr("mr_guardian.cli.main.review_merge_request", fake_review_merge_request)
    monkeypatch.setattr("mr_guardian.cli.main.store_review_result", lambda *_, **__: None)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["review", "--base", "main"],
    )

    assert "MR Guardian Review" in result.output
    assert "Verdict: `PASSED`" in result.output
    assert "No findings were triggered." in result.output


def test_review_command_accepts_base_and_policy_dir_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_request: ReviewRequest | None = None

    def fake_review_merge_request(request: ReviewRequest, **_: object) -> ReviewResult:
        nonlocal captured_request
        captured_request = request
        return make_empty_review_result(request.base, request.policy_directory)

    monkeypatch.setattr("mr_guardian.cli.main.review_merge_request", fake_review_merge_request)
    monkeypatch.setattr("mr_guardian.cli.main.store_review_result", lambda *_, **__: None)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["review", "--base", "develop", "--policy-dir", "custom-policies"],
    )

    assert result.exit_code == 0
    assert captured_request == ReviewRequest(
        base="develop",
        policy_directory=Path("custom-policies"),
    )


def test_review_command_accepts_mr_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_request: ReviewRequest | None = None

    def fake_review_merge_request(request: ReviewRequest, **_: object) -> ReviewResult:
        nonlocal captured_request
        captured_request = request
        return make_empty_review_result(request.base, request.policy_directory)

    monkeypatch.setattr("mr_guardian.cli.main.review_merge_request", fake_review_merge_request)
    monkeypatch.setattr("mr_guardian.cli.main.store_review_result", lambda *_, **__: None)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "review",
            "--base",
            "main",
            "--title",
            "Add player movement",
            "--description",
            "## Test Plan\n- Ran",
        ],
    )

    assert result.exit_code == 0
    assert captured_request is not None
    assert captured_request.title == "Add player movement"
    assert captured_request.description == "## Test Plan\n- Ran"


def test_review_command_accepts_description_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    description_path = tmp_path / "mr.md"
    description_path.write_text("## Summary\nUpdated movement", encoding="utf-8")
    captured_request: ReviewRequest | None = None

    def fake_review_merge_request(request: ReviewRequest, **_: object) -> ReviewResult:
        nonlocal captured_request
        captured_request = request
        return make_empty_review_result(request.base, request.policy_directory)

    monkeypatch.setattr("mr_guardian.cli.main.review_merge_request", fake_review_merge_request)
    monkeypatch.setattr("mr_guardian.cli.main.store_review_result", lambda *_, **__: None)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "review",
            "--base",
            "main",
            "--description-file",
            str(description_path),
        ],
    )

    assert result.exit_code == 0
    assert captured_request is not None
    assert captured_request.description == "## Summary\nUpdated movement"


def test_review_command_rejects_description_and_description_file(
    tmp_path: Path,
) -> None:
    description_path = tmp_path / "mr.md"
    description_path.write_text("## Summary\nUpdated movement", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "review",
            "--base",
            "main",
            "--description",
            "inline",
            "--description-file",
            str(description_path),
        ],
    )

    assert result.exit_code != 0
    assert "Use either --description or --description-file" in result.output


def test_review_command_stores_review_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "history.sqlite"

    def fake_review_merge_request(request: ReviewRequest, **_: object) -> ReviewResult:
        return ReviewResult(
            base_ref=request.base,
            policy_directory=request.policy_directory,
            policy_results=[
                PolicyReviewResult(
                    policy_path=request.policy_directory / "python-policy.yml",
                    policy_version=3,
                    enabled_rule_count=1,
                    disabled_rule_count=0,
                    engine_result=EngineReviewResult(
                        risk="warning",
                        findings=[
                            Finding(
                                rule_id="PYTHON-PRINT-001",
                                severity="warning",
                                message="print calls should not be introduced.",
                                source="python-policy.yml#PYTHON-PRINT-001",
                                rule_type="deterministic",
                                file_path=Path("mr_guardian/example.py"),
                                line_number=1,
                            )
                        ],
                        counts=FindingCounts(warning=1),
                    ),
                )
            ],
            developer_id="Test User",
            review_input=ReviewInput(
                base_ref=request.base,
                title=request.title,
                changed_files=[
                    ChangedFile(
                        path=Path("mr_guardian/example.py"),
                        status="modified",
                        hunks=[
                            DiffHunk(
                                old_start=1,
                                old_count=1,
                                new_start=1,
                                new_count=1,
                                lines=[
                                    DiffLine(
                                        kind="addition",
                                        content="print('ready')",
                                        old_line_number=None,
                                        new_line_number=1,
                                    )
                                ],
                            )
                        ],
                    )
                ],
            ),
            engine_result=EngineReviewResult(
                risk="warning",
                findings=[
                    Finding(
                        rule_id="PYTHON-PRINT-001",
                        severity="warning",
                        message="print calls should not be introduced.",
                        source="python-policy.yml#PYTHON-PRINT-001",
                        rule_type="deterministic",
                        file_path=Path("mr_guardian/example.py"),
                        line_number=1,
                    )
                ],
                counts=FindingCounts(warning=1),
            ),
        )

    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.setattr("mr_guardian.cli.main.review_merge_request", fake_review_merge_request)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["review", "--base", "main", "--title", "TK-234 Add CLI review"],
    )

    store = ReviewHistoryStore(database_path)
    recent_runs = store.recent_review_runs()
    store.close()

    assert result.exit_code == 0
    assert len(recent_runs) == 1
    assert recent_runs[0].review_scope == "local-all-policies"
    assert recent_runs[0].branch_name == "main"
    assert recent_runs[0].developer_id == "Test User"
    assert recent_runs[0].ticket_key == "TK-234"
    assert recent_runs[0].review_score == 95
    assert recent_runs[0].policy_version == 3
    assert recent_runs[0].changed_file_count == 1
    assert recent_runs[0].changed_line_count == 1
    assert recent_runs[0].triggered_rule_ids == ["PYTHON-PRINT-001"]
    assert "MR Guardian Review" in recent_runs[0].generated_review_report


def test_review_command_no_store_skips_review_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "history.sqlite"

    def fake_review_merge_request(request: ReviewRequest, **_: object) -> ReviewResult:
        return make_empty_review_result(request.base, request.policy_directory)

    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    monkeypatch.setattr("mr_guardian.cli.main.review_merge_request", fake_review_merge_request)
    runner = CliRunner()

    result = runner.invoke(app, ["review", "--base", "main", "--no-store"])

    assert result.exit_code == 0
    assert not database_path.exists()


def test_submit_manual_review_command_stores_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "history.sqlite"
    payload_path = tmp_path / "manual-review.json"
    payload_path.write_text(json.dumps(valid_manual_review_payload()), encoding="utf-8")
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["submit-manual-review", "--file", str(payload_path)],
    )

    store = ReviewHistoryStore(database_path)
    recent_runs = store.recent_review_runs()
    store.close()

    assert result.exit_code == 0
    assert "Manual review stored successfully." in result.output
    assert "Review ID: 1" in result.output
    assert len(recent_runs) == 1
    assert recent_runs[0].review_scope == "manual-review"
    assert recent_runs[0].ticket_key == "TK-777"
    assert recent_runs[0].generated_review_report == "## Manual Review\n\nLooks good."


def test_submit_manual_review_command_reports_validation_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "history.sqlite"
    payload = valid_manual_review_payload()
    payload["risk"] = "high"
    payload_path = tmp_path / "manual-review.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("MR_GUARDIAN_HISTORY_DB_PATH", str(database_path))
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["submit-manual-review", "--file", str(payload_path)],
    )

    assert result.exit_code != 0
    assert "Manual review submission failed" in result.output
    assert "does not match findings risk" in result.output
    assert not database_path.exists()


def test_inspect_commands_are_removed() -> None:
    runner = CliRunner()

    inspect_result = runner.invoke(app, ["inspect", "--base", "main"])
    inspect_all_result = runner.invoke(app, ["inspect-all", "--base", "main"])

    assert inspect_result.exit_code != 0
    assert inspect_all_result.exit_code != 0
    assert "No such command" in inspect_result.output
    assert "No such command" in inspect_all_result.output


def test_logs_command_outputs_review_history(tmp_path: Path) -> None:
    database_path = tmp_path / "history.sqlite"
    store = ReviewHistoryStore(database_path)
    store.store_review_run(
        ReviewRunCreate(
            review_scope="local-all-policies",
            branch_name="feature/history",
            policy_version=1,
            risk="warning",
            blocking_count=0,
            high_count=0,
            warning_count=1,
            info_count=0,
            changed_file_count=2,
            changed_line_count=5,
            triggered_rule_ids=["PYTHON-PRINT-001"],
            generated_review_report="## MR Guardian Review\n",
        )
    )
    store.close()
    runner = CliRunner()

    result = runner.invoke(app, ["logs", "--db", str(database_path)])

    assert result.exit_code == 0
    assert "MR Guardian Review History" in result.output
    assert "feature/history" in result.output
    assert "PYTHON-PRINT-001" in result.output


def test_log_report_command_outputs_stored_report(tmp_path: Path) -> None:
    database_path = tmp_path / "history.sqlite"
    store = ReviewHistoryStore(database_path)
    record = store.store_review_run(
        ReviewRunCreate(
            review_scope="local-all-policies",
            branch_name="feature/history",
            policy_version=1,
            risk="warning",
            blocking_count=0,
            high_count=0,
            warning_count=1,
            info_count=0,
            changed_file_count=2,
            changed_line_count=5,
            triggered_rule_ids=["PYTHON-PRINT-001"],
            generated_review_report="## MR Guardian Review\n\nStored report body.",
        )
    )
    store.close()
    runner = CliRunner()

    result = runner.invoke(app, ["log-report", str(record.review_id), "--db", str(database_path)])

    assert result.exit_code == 0
    assert "## MR Guardian Review" in result.output
    assert "Stored report body." in result.output


def test_log_report_command_reports_missing_review_id(tmp_path: Path) -> None:
    database_path = tmp_path / "history.sqlite"
    runner = CliRunner()

    result = runner.invoke(app, ["log-report", "999", "--db", str(database_path)])

    assert result.exit_code != 0
    assert "No review run found with ID 999" in result.output


def test_clear_logs_command_requires_confirmation(tmp_path: Path) -> None:
    database_path = tmp_path / "history.sqlite"
    runner = CliRunner()

    result = runner.invoke(app, ["clear-logs", "--db", str(database_path)])

    assert result.exit_code != 0
    assert "Pass --yes" in result.output


def test_clear_logs_command_removes_review_history(tmp_path: Path) -> None:
    database_path = tmp_path / "history.sqlite"
    store = ReviewHistoryStore(database_path)
    store.store_review_run(
        ReviewRunCreate(
            review_scope="local-all-policies",
            branch_name="feature/history",
            policy_version=1,
            risk="warning",
            blocking_count=0,
            high_count=0,
            warning_count=1,
            info_count=0,
            changed_file_count=2,
            changed_line_count=5,
            triggered_rule_ids=["PYTHON-PRINT-001"],
            generated_review_report="## MR Guardian Review\n",
        )
    )
    store.close()
    runner = CliRunner()

    result = runner.invoke(app, ["clear-logs", "--db", str(database_path), "--yes"])

    assert result.exit_code == 0
    assert "Removed 1 review run(s)." in result.output
