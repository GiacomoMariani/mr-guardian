"""Typer command wiring for MR Guardian."""

from pathlib import Path
from typing import Annotated

import typer

from mr_guardian.config import get_settings
from mr_guardian.core.manual_review import (
    ManualReviewError,
    manual_review_error_report,
    manual_review_success_report,
    store_manual_review_file,
)
from mr_guardian.core.metadata import resolve_description
from mr_guardian.core.review import ReviewRequest, review_merge_request
from mr_guardian.core.review_history import store_review_result
from mr_guardian.reporting.history import render_clear_history_result, render_review_history
from mr_guardian.reporting.report import render_review_report
from mr_guardian.storage import ReviewHistoryStore
from mr_guardian.summarizer_ai import (
    create_llm_review_summary_runner,
    create_llm_rule_runner,
)

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """MR Guardian command-line interface."""


@app.command()
def review(
    base: Annotated[str, typer.Option("--base", help="Base branch to review against.")],
    policy_dir: Annotated[
        Path | None,
        typer.Option("--policy-dir", help="Directory containing YAML policy files."),
    ] = None,
    no_store: Annotated[
        bool,
        typer.Option("--no-store", help="Print the report without storing review history."),
    ] = False,
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
        policy_directory=policy_dir or settings.policy_dir,
        title=title,
        description=resolved_description,
    )
    result = review_merge_request(
        request,
        repo_path=settings.repo_path,
        llm_rule_runner=create_llm_rule_runner(
            provider=settings.llm_provider,
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            openai_timeout_seconds=settings.openai_timeout_seconds,
            openai_max_retries=settings.openai_max_retries,
        ),
        llm_summary_runner=create_llm_review_summary_runner(
            enabled=settings.llm_summary_enabled,
            provider=settings.llm_provider,
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            openai_timeout_seconds=settings.openai_timeout_seconds,
            openai_max_retries=settings.openai_max_retries,
        ),
        llm_summary_max_chars=settings.llm_summary_max_chars,
    )
    report = render_review_report(result)
    if not no_store:
        store_review_result(
            result,
            report=report,
            database_path=settings.history_db_path,
            review_scope="local-all-policies",
        )
    typer.echo(report)


@app.command("submit-manual-review")
def submit_manual_review(
    file: Annotated[Path, typer.Option("--file", help="Manual review JSON payload.")],
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to the SQLite review history database."),
    ] = None,
) -> None:
    """Validate and store a manually written review."""
    settings = get_settings()
    try:
        record = store_manual_review_file(file, database_path=db or settings.history_db_path)
    except ManualReviewError as exc:
        raise typer.BadParameter(manual_review_error_report(exc)) from exc

    typer.echo(manual_review_success_report(record))


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
    yes: Annotated[bool, typer.Option("--yes", help="Confirm deleting all stored data.")] = False,
) -> None:
    """Remove all stored data: review runs, weekly reviews, and ETA notes."""
    if not yes:
        raise typer.BadParameter("Pass --yes to confirm deleting all stored data.")

    settings = get_settings()
    store = ReviewHistoryStore(db or settings.history_db_path)
    try:
        typer.echo(render_clear_history_result(store.clear_history()))
    finally:
        store.close()


if __name__ == "__main__":
    app()
