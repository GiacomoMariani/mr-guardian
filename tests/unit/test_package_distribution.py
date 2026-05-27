from importlib.resources import as_file, files
from pathlib import Path

from mr_guardian.policies import policy_paths_from_directory, resolve_policy_directory


def test_packaged_default_policies_are_available() -> None:
    resource = files("mr_guardian").joinpath("defaults", "yaml")

    with as_file(resource) as policy_directory:
        policy_names = {path.name for path in policy_paths_from_directory(policy_directory)}

    assert {"python-policy.yml", "unity-policy.yml"}.issubset(policy_names)


def test_default_policy_directory_falls_back_to_packaged_policies(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    with resolve_policy_directory(Path("sources/yaml")) as policy_directory:
        policy_names = {path.name for path in policy_paths_from_directory(policy_directory)}

    assert not Path("sources/yaml").exists()
    assert {"python-policy.yml", "unity-policy.yml"}.issubset(policy_names)


def test_custom_policy_directory_does_not_fall_back_to_packaged_policies(
    tmp_path: Path,
) -> None:
    custom_policy_directory = tmp_path / "custom-policies"

    with resolve_policy_directory(custom_policy_directory) as policy_directory:
        policy_names = {path.name for path in policy_paths_from_directory(policy_directory)}

    assert policy_directory == custom_policy_directory
    assert policy_names == set()
