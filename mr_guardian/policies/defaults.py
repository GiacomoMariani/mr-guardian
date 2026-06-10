"""Packaged default policy resources."""

from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import as_file, files
from pathlib import Path

DEFAULT_POLICY_DIRECTORY = Path("sources/yaml")
DEFAULT_POLICY_RESOURCE_DIRECTORY = "defaults/yaml"


@contextmanager
def resolve_policy_directory(directory: str | Path) -> Iterator[Path]:
    """Resolve a policy directory, falling back to packaged defaults when appropriate."""
    requested_directory = Path(directory)
    if requested_directory != DEFAULT_POLICY_DIRECTORY or _contains_yaml(requested_directory):
        yield requested_directory
        return

    resource = files("mr_guardian").joinpath(DEFAULT_POLICY_RESOURCE_DIRECTORY)
    with as_file(resource) as packaged_directory:
        yield packaged_directory


def _contains_yaml(directory: Path) -> bool:
    if not directory.is_dir():
        return False
    return any(
        path.is_file() for pattern in ("*.yml", "*.yaml") for path in directory.glob(pattern)
    )
