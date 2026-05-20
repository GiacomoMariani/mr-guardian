"""Developer-facing inspection workflow."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from mr_guardian.core.engine import run_review
from mr_guardian.models.review import EngineReviewResult
from mr_guardian.models.review_input import ReviewInput
from mr_guardian.policies import load_policy, policy_paths_from_directory
from mr_guardian.providers import LocalGitProvider
from mr_guardian.rules import RuleRegistry, default_rule_registry


class InspectionResult(BaseModel):
    """Summary of the currently wired review pipeline."""

    model_config = ConfigDict(frozen=True)

    policy_path: Path
    policy_version: int
    enabled_rule_count: int
    disabled_rule_count: int
    base_ref: str
    review_input: ReviewInput
    engine_result: EngineReviewResult


class InspectionSuiteResult(BaseModel):
    """Summary for inspecting every configured policy."""

    model_config = ConfigDict(frozen=True)

    policy_directory: Path
    policy_results: list[InspectionResult]


def inspect_review(
    *,
    base_ref: str,
    policy_path: str | Path,
    repo_path: str | Path = ".",
    rule_registry: RuleRegistry | None = None,
) -> InspectionResult:
    """Run the currently implemented review pipeline and return a compact summary."""
    resolved_policy_path = Path(policy_path)
    policy = load_policy(resolved_policy_path)
    review_input = LocalGitProvider(repo_path).collect(base_ref)
    engine_result = run_review(
        policy=policy,
        review_input=review_input,
        rule_registry=rule_registry or default_rule_registry(),
    )

    enabled_rule_count = sum(1 for rule in policy.rules if rule.enabled)
    disabled_rule_count = sum(1 for rule in policy.rules if not rule.enabled)

    return InspectionResult(
        policy_path=resolved_policy_path,
        policy_version=policy.version,
        enabled_rule_count=enabled_rule_count,
        disabled_rule_count=disabled_rule_count,
        base_ref=base_ref,
        review_input=review_input,
        engine_result=engine_result,
    )


def inspect_all_reviews(
    *,
    base_ref: str,
    policy_directory: str | Path = "sources/yaml",
    repo_path: str | Path = ".",
    rule_registry: RuleRegistry | None = None,
) -> InspectionSuiteResult:
    """Run the currently implemented review pipeline for every YAML policy."""
    resolved_policy_directory = Path(policy_directory)
    review_input = LocalGitProvider(repo_path).collect(base_ref)
    registry = rule_registry or default_rule_registry()

    policy_results = [
        _inspect_loaded_policy(
            base_ref=base_ref,
            policy_path=policy_path,
            review_input=review_input,
            rule_registry=registry,
        )
        for policy_path in policy_paths_from_directory(resolved_policy_directory)
    ]

    return InspectionSuiteResult(
        policy_directory=resolved_policy_directory,
        policy_results=policy_results,
    )


def _inspect_loaded_policy(
    *,
    base_ref: str,
    policy_path: Path,
    review_input: ReviewInput,
    rule_registry: RuleRegistry,
) -> InspectionResult:
    policy = load_policy(policy_path)
    engine_result = run_review(
        policy=policy,
        review_input=review_input,
        rule_registry=rule_registry,
    )

    enabled_rule_count = sum(1 for rule in policy.rules if rule.enabled)
    disabled_rule_count = sum(1 for rule in policy.rules if not rule.enabled)

    return InspectionResult(
        policy_path=policy_path,
        policy_version=policy.version,
        enabled_rule_count=enabled_rule_count,
        disabled_rule_count=disabled_rule_count,
        base_ref=base_ref,
        review_input=review_input,
        engine_result=engine_result,
    )
