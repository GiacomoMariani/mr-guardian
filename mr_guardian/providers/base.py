"""Provider interfaces for review inputs."""

from typing import Protocol

from mr_guardian.models.review_input import ReviewInput


class ReviewInputProvider(Protocol):
    """Collect structured review input from a backing source."""

    def collect(self, base_ref: str) -> ReviewInput:
        """Collect changed files and diff information compared with a base ref."""
