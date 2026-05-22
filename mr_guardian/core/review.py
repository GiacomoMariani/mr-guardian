"""Review orchestration entry points."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from mr_guardian.core.engine import run_review
from mr_guardian.models.review import EngineReviewResult
from mr_guardian.models.review_input import ReviewInput
from mr_guardian.policies import load_policy
from mr_guardian.providers import LocalGitProvider
from mr_guardian.rules import RuleRegistry, default_rule_registry


class ReviewRequest(BaseModel):
    """Inputs needed to run a merge request review."""

    model_config = ConfigDict(frozen=True)

    base: str
    policy_path: Path


class ReviewResult(BaseModel):
    """Result of a merge request review."""

    model_config = ConfigDict(frozen=True)

    base_ref: str
    policy_path: Path
    review_input: ReviewInput
    engine_result: EngineReviewResult

    @property
    def risk(self) -> str:
        """Return the calculated review risk."""
        return self.engine_result.risk


def review_merge_request(
    request: ReviewRequest,
    *,
    repo_path: str | Path = ".",
    rule_registry: RuleRegistry | None = None,
) -> ReviewResult:
    """Run the local review pipeline for a merge request."""
    policy = load_policy(request.policy_path)
    review_input = LocalGitProvider(repo_path).collect(request.base)
    engine_result = run_review(
        policy=policy,
        review_input=review_input,
        rule_registry=rule_registry or default_rule_registry(),
    )

    return ReviewResult(
        base_ref=request.base,
        policy_path=request.policy_path,
        review_input=review_input,
        engine_result=engine_result,
    )
