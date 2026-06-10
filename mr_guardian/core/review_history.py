"""Shared review-history persistence helpers."""

from pathlib import Path

from mr_guardian.core.review import ReviewResult
from mr_guardian.core.review_score import calculate_review_score_from_counts
from mr_guardian.core.ticket_keys import extract_ticket_key_from_title
from mr_guardian.models.history import (
    ReviewPolicySummary,
    ReviewRunCreate,
    ReviewRunRecord,
)
from mr_guardian.models.review import summarize_review_evaluations
from mr_guardian.storage import ReviewHistoryStore


def store_review_result(
    result: ReviewResult,
    *,
    report: str,
    database_path: Path,
    review_scope: str,
    mr_id: str | None = None,
    commit_sha: str | None = None,
    developer_id: str | None = None,
) -> ReviewRunRecord:
    """Store a completed review result and generated report."""
    counts = result.engine_result.counts
    store = ReviewHistoryStore(database_path)
    try:
        record = store.store_review_run(
            ReviewRunCreate(
                review_scope=review_scope,
                branch_name=result.base_ref,
                developer_id=developer_id or result.developer_id,
                ticket_key=extract_ticket_key_from_title(result.review_input.title),
                mr_id=mr_id,
                commit_sha=commit_sha,
                policy_version=result.policy_version,
                risk=result.engine_result.risk,
                blocking_count=counts.blocking,
                high_count=counts.high,
                warning_count=counts.warning,
                info_count=counts.info,
                changed_file_count=len(result.review_input.changed_files),
                changed_line_count=changed_line_count(result),
                review_score=calculate_review_score_from_counts(counts),
                findings=result.engine_result.findings,
                triggered_rule_ids=[finding.rule_id for finding in result.engine_result.findings],
                evaluations=result.engine_result.evaluations
                or summarize_review_evaluations(result.engine_result.findings),
                llm_metrics=result.engine_result.llm_metrics,
                llm_summary=result.llm_summary,
                policy_summaries=[
                    ReviewPolicySummary(
                        policy_path=policy_result.policy_path.as_posix(),
                        policy_version=policy_result.policy_version,
                        enabled_rule_count=policy_result.enabled_rule_count,
                        disabled_rule_count=policy_result.disabled_rule_count,
                    )
                    for policy_result in result.policy_results
                ],
                generated_review_report=report,
            )
        )
        return record
    finally:
        store.close()


def changed_line_count(result: ReviewResult) -> int:
    """Count added and deleted diff lines in a review result."""
    return sum(
        1
        for changed_file in result.review_input.changed_files
        for hunk in changed_file.hunks
        for diff_line in hunk.lines
        if diff_line.kind in {"addition", "deletion"}
    )
