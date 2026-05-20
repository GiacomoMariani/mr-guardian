"""Typer command wiring for MR Guardian."""

from pathlib import Path
from typing import Annotated

import typer

from mr_guardian.core.inspection import inspect_all_reviews, inspect_review
from mr_guardian.core.review import ReviewRequest, review_merge_request
from mr_guardian.reporting.inspection import (
    render_inspection_result,
    render_inspection_suite_result,
)
from mr_guardian.reporting.report import render_review_report

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """MR Guardian command-line interface."""


@app.command()
def review(
    base: Annotated[str, typer.Option("--base", help="Base branch to review against.")],
    policy: Annotated[
        Path,
        typer.Option("--policy", help="Path to the YAML policy file."),
    ],
) -> None:
    """Generate a review report for the current merge request."""
    request = ReviewRequest(base=base, policy_path=policy)
    result = review_merge_request(request)
    typer.echo(render_review_report(result))


@app.command()
def inspect(
    base: Annotated[str, typer.Option("--base", help="Base branch to inspect against.")],
    policy: Annotated[
        Path,
        typer.Option("--policy", help="Path to the YAML policy file."),
    ],
) -> None:
    """Inspect the currently wired local review pipeline."""
    result = inspect_review(base_ref=base, policy_path=policy)
    typer.echo(render_inspection_result(result))


@app.command("inspect-all")
def inspect_all(
    base: Annotated[str, typer.Option("--base", help="Base branch to inspect against.")],
    policy_dir: Annotated[
        Path,
        typer.Option("--policy-dir", help="Directory containing YAML policy files."),
    ] = Path("sources/yaml"),
) -> None:
    """Inspect every YAML policy."""
    result = inspect_all_reviews(
        base_ref=base,
        policy_directory=policy_dir,
    )
    typer.echo(render_inspection_suite_result(result))


if __name__ == "__main__":
    app()
