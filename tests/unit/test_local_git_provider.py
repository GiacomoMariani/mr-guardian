import subprocess
from pathlib import Path

import pytest

from mr_guardian.providers import GitRepositoryError, LocalGitProvider


def run_git(repo_path: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        check=True,
        encoding="utf-8",
    )


def create_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    subprocess.run(
        ["git", "init", "-b", "main", str(repo_path)],
        capture_output=True,
        check=True,
        encoding="utf-8",
    )
    run_git(repo_path, "config", "user.email", "test@example.com")
    run_git(repo_path, "config", "user.name", "Test User")

    file_path = repo_path / "Assets" / "Scripts" / "Player.cs"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("public class Player\n{\n}\n", encoding="utf-8")
    run_git(repo_path, "add", ".")
    run_git(repo_path, "commit", "-m", "initial commit")
    run_git(repo_path, "checkout", "-b", "feature")
    return repo_path


def test_handles_repository_with_no_changes(tmp_path: Path) -> None:
    repo_path = create_repo(tmp_path)
    provider = LocalGitProvider(repo_path)

    review_input = provider.collect("main")

    assert review_input.base_ref == "main"
    assert review_input.changed_files == []


def test_handles_repository_with_one_modified_file(tmp_path: Path) -> None:
    repo_path = create_repo(tmp_path)
    changed_path = repo_path / "Assets" / "Scripts" / "Player.cs"
    changed_path.write_text(
        "public class Player\n{\n    public void Move() {}\n}\n",
        encoding="utf-8",
    )
    provider = LocalGitProvider(repo_path)

    review_input = provider.collect("main")

    assert len(review_input.changed_files) == 1
    assert review_input.changed_files[0].path == Path("Assets/Scripts/Player.cs")
    assert review_input.changed_files[0].status == "modified"


def test_captures_changed_line_content_in_diff_hunks(tmp_path: Path) -> None:
    repo_path = create_repo(tmp_path)
    changed_path = repo_path / "Assets" / "Scripts" / "Player.cs"
    changed_path.write_text(
        "public class Player\n{\n    public void Move() {}\n}\n",
        encoding="utf-8",
    )
    provider = LocalGitProvider(repo_path)

    review_input = provider.collect("main")

    changed_file = review_input.changed_files[0]
    additions = [
        line.content
        for hunk in changed_file.hunks
        for line in hunk.lines
        if line.kind == "addition"
    ]
    assert "    public void Move() {}" in additions
    assert changed_file.hunks[0].new_start >= 1


def test_handles_invalid_base_branch_with_clear_error(tmp_path: Path) -> None:
    repo_path = create_repo(tmp_path)
    provider = LocalGitProvider(repo_path)

    with pytest.raises(GitRepositoryError, match="does-not-exist"):
        provider.collect("does-not-exist")


def test_handles_added_deleted_and_renamed_file_statuses(tmp_path: Path) -> None:
    repo_path = create_repo(tmp_path)
    run_git(repo_path, "mv", "Assets/Scripts/Player.cs", "Assets/Scripts/Hero.cs")
    added_path = repo_path / "Assets" / "Scripts" / "Enemy.cs"
    added_path.write_text("public class Enemy {}\n", encoding="utf-8")
    run_git(repo_path, "add", "Assets/Scripts/Enemy.cs")
    provider = LocalGitProvider(repo_path)

    review_input = provider.collect("main")
    files_by_path = {
        changed_file.path.as_posix(): changed_file for changed_file in review_input.changed_files
    }

    assert files_by_path["Assets/Scripts/Hero.cs"].status == "renamed"
    assert files_by_path["Assets/Scripts/Hero.cs"].old_path == Path("Assets/Scripts/Player.cs")
    assert files_by_path["Assets/Scripts/Enemy.cs"].status == "added"
