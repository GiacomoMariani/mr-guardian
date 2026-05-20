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


def load_policies_from_directory(directory: str | Path) -> list[Policy]:
    """Load every YAML policy file from a directory."""
    policy_directory = Path(directory)
    policy_paths = sorted(
        path
        for pattern in ("*.yml", "*.yaml")
        for path in policy_directory.glob(pattern)
        if path.is_file()
    )
    return [load_policy(path) for path in policy_paths]


def policy_paths_from_directory(directory: str | Path) -> list[Path]:
    """Return every YAML policy path from a directory."""
    policy_directory = Path(directory)
    return sorted(
        path
        for pattern in ("*.yml", "*.yaml")
        for path in policy_directory.glob(pattern)
        if path.is_file()
    )
