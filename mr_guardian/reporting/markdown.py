"""Markdown report rendering."""

from mr_guardian.core.review import ReviewResult


def render_review_report(result: ReviewResult) -> str:
    """Render a review result as Markdown."""
    return "\n".join(
        [
            "## MR Guardian Review",
            "",
            f"**Risk:** {result.risk}",
            "",
            result.message,
        ]
    )

