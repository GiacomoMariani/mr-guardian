"""Typer command wiring for MR Guardian."""

from pathlib import Path
from typing import Annotated

import typer

from mr_guardian.config import get_settings
from mr_guardian.core.inspection import inspect_all_reviews, inspect_review
from mr_guardian.core.metadata import resolve_description
from mr_guardian.core.review import ReviewRequest, ReviewResult, review_merge_request
from mr_guardian.models.history import ReviewRunCreate
from mr_guardian.reporting.history import render_clear_history_result, render_review_history
from mr_guardian.reporting.inspection import (
    render_inspection_result,
    render_inspection_suite_result,
)
from mr_guardian.reporting.report import render_review_report
from mr_guardian.storage import ReviewHistoryStore

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """MR Guardian command-line interface."""


@app.command()
def review(
    base: Annotated[str, typer.Option("--base", help="Base branch to review against.")],
    policy: Annotated[
        Path | None,
        typer.Option("--policy", help="Path to the YAML policy file."),
    ] = None,
    title: Annotated[str, typer.Option("--title", help="Merge request title.")] = "",
    description: Annotated[
        str | None,
        typer.Option("--description", help="Merge request description text."),
    ] = None,
    description_file: Annotated[
        Path | None,
        typer.Option("--description-file", help="Path to a merge request description file."),
    ] = None,
) -> None:
    """Generate a review report for the current merge request."""
    settings = get_settings()
    try:
        resolved_description = resolve_description(
            description=description,
            description_file=description_file,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    request = ReviewRequest(
        base=base,
        policy_path=policy or settings.policy_path,
        title=title,
        description=resolved_description,
    )
    result = review_merge_request(request, repo_path=settings.repo_path)
    report = render_review_report(result)
    _store_review_result(
        result,
        report=report,
        database_path=settings.history_db_path,
    )
    typer.echo(report)


@app.command()
def inspect(
    base: Annotated[str, typer.Option("--base", help="Base branch to inspect against.")],
    policy: Annotated[
        Path | None,
        typer.Option("--policy", help="Path to the YAML policy file."),
    ] = None,
    title: Annotated[str, typer.Option("--title", help="Merge request title.")] = "",
    description: Annotated[
        str | None,
        typer.Option("--description", help="Merge request description text."),
    ] = None,
    description_file: Annotated[
        Path | None,
        typer.Option("--description-file", help="Path to a merge request description file."),
    ] = None,
) -> None:
    """Inspect the currently wired local review pipeline."""
    settings = get_settings()
    try:
        resolved_description = resolve_description(
            description=description,
            description_file=description_file,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    result = inspect_review(
        base_ref=base,
        policy_path=policy or settings.policy_path,
        repo_path=settings.repo_path,
        title=title,
        description=resolved_description,
    )
    typer.echo(render_inspection_result(result))


@app.command("inspect-all")
def inspect_all(
    base: Annotated[str, typer.Option("--base", help="Base branch to inspect against.")],
    policy_dir: Annotated[
        Path | None,
        typer.Option("--policy-dir", help="Directory containing YAML policy files."),
    ] = None,
    title: Annotated[str, typer.Option("--title", help="Merge request title.")] = "",
    description: Annotated[
        str | None,
        typer.Option("--description", help="Merge request description text."),
    ] = None,
    description_file: Annotated[
        Path | None,
        typer.Option("--description-file", help="Path to a merge request description file."),
    ] = None,
) -> None:
    """Inspect every YAML policy."""
    settings = get_settings()
    try:
        resolved_description = resolve_description(
            description=description,
            description_file=description_file,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    result = inspect_all_reviews(
        base_ref=base,
        policy_directory=policy_dir or settings.policy_dir,
        repo_path=settings.repo_path,
        title=title,
        description=resolved_description,
    )
    typer.echo(render_inspection_suite_result(result))


@app.command()
def logs(
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to the SQLite review history database."),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", help="Number of recent runs to show.")] = 20,
) -> None:
    """Show stored review history in a readable table."""
    settings = get_settings()
    store = ReviewHistoryStore(db or settings.history_db_path)
    try:
        typer.echo(
            render_review_history(
                store.recent_review_runs(limit=limit),
                most_triggered_rules=store.most_triggered_rules(limit=10),
            )
        )
    finally:
        store.close()


@app.command("log-report")
def log_report(
    review_id: Annotated[int, typer.Argument(help="Stored review ID to display.")],
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to the SQLite review history database."),
    ] = None,
) -> None:
    """Show the generated report for a stored review run."""
    settings = get_settings()
    store = ReviewHistoryStore(db or settings.history_db_path)
    try:
        run = store.review_run(review_id)
    finally:
        store.close()

    if run is None:
        raise typer.BadParameter(f"No review run found with ID {review_id}.")

    typer.echo(run.generated_review_report)


@app.command("clear-logs")
def clear_logs(
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to the SQLite review history database."),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Confirm deletion of review history.")] = False,
) -> None:
    """Remove all stored review history."""
    if not yes:
        raise typer.BadParameter("Pass --yes to confirm deleting review history.")

    settings = get_settings()
    store = ReviewHistoryStore(db or settings.history_db_path)
    try:
        typer.echo(render_clear_history_result(store.clear_history()))
    finally:
        store.close()


def _store_review_result(
    result: ReviewResult,
    *,
    report: str,
    database_path: Path,
) -> None:
    store = ReviewHistoryStore(database_path)
    try:
        store.store_review_run(
            ReviewRunCreate(
                project_name=result.policy_path.stem,
                branch_name=result.base_ref,
                policy_version=result.policy_version,
                risk=result.engine_result.risk,
                blocking_count=result.engine_result.counts.blocking,
                high_count=result.engine_result.counts.high,
                warning_count=result.engine_result.counts.warning,
                info_count=result.engine_result.counts.info,
                changed_file_count=len(result.review_input.changed_files),
                changed_line_count=_changed_line_count(result),
                triggered_rule_ids=[
                    finding.rule_id
                    for finding in result.engine_result.findings
                ],
                generated_review_report=report,
            )
        )
    finally:
        store.close()


def _changed_line_count(result: ReviewResult) -> int:
    return sum(
        1
        for changed_file in result.review_input.changed_files
        for hunk in changed_file.hunks
        for diff_line in hunk.lines
        if diff_line.kind in {"addition", "deletion"}
    )


if __name__ == "__main__":
    app()
