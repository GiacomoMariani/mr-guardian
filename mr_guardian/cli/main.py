"""Typer command wiring for MR Guardian."""

from pathlib import Path
from typing import Annotated

import typer

from mr_guardian.core.review import ReviewRequest, review_merge_request
from mr_guardian.reporting.markdown import render_review_report

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


if __name__ == "__main__":
    app()
