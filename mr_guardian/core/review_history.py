"""Shared review-history persistence helpers."""

from pathlib import Path

from mr_guardian.core.review import ReviewResult
from mr_guardian.models.history import ReviewRunCreate, ReviewRunRecord
from mr_guardian.storage import ReviewHistoryStore


def store_review_result(
    result: ReviewResult,
    *,
    report: str,
    database_path: Path,
    review_scope: str,
    mr_id: str | None = None,
    commit_sha: str | None = None,
) -> ReviewRunRecord:
    """Store a completed review result and generated report."""
    store = ReviewHistoryStore(database_path)
    try:
        return store.store_review_run(
            ReviewRunCreate(
                review_scope=review_scope,
                branch_name=result.base_ref,
                developer_id=result.developer_id,
                mr_id=mr_id,
                commit_sha=commit_sha,
                policy_version=result.policy_version,
                risk=result.engine_result.risk,
                blocking_count=result.engine_result.counts.blocking,
                high_count=result.engine_result.counts.high,
                warning_count=result.engine_result.counts.warning,
                info_count=result.engine_result.counts.info,
                changed_file_count=len(result.review_input.changed_files),
                changed_line_count=changed_line_count(result),
                triggered_rule_ids=[
                    finding.rule_id
                    for finding in result.engine_result.findings
                ],
                llm_metrics=result.engine_result.llm_metrics,
                generated_review_report=report,
            )
        )
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
