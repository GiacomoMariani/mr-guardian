"""Load and validate YAML policy files."""

from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import ValidationError

from mr_guardian.models.policy import Policy


class PolicyLoadError(Exception):
    """Base error for policy loading failures."""


class PolicyYamlError(PolicyLoadError):
    """Raised when a policy file contains invalid YAML."""


class PolicyValidationError(PolicyLoadError):
    """Raised when a policy file has an invalid structure."""


def load_policy(path: str | Path) -> Policy:
    """Load a policy YAML file from disk into typed models."""
    policy_path = Path(path)

    try:
        raw_policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        msg = f"Invalid YAML in policy file '{policy_path}': {exc}"
        raise PolicyYamlError(msg) from exc

    if not isinstance(raw_policy, Mapping):
        msg = (
            f"Invalid policy structure in '{policy_path}': "
            "expected a YAML mapping at the top level."
        )
        raise PolicyValidationError(msg)

    try:
        return Policy.model_validate(raw_policy)
    except ValidationError as exc:
        msg = f"Invalid policy structure in '{policy_path}': {exc}"
        raise PolicyValidationError(msg) from exc
