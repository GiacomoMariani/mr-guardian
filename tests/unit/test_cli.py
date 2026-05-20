from typer.testing import CliRunner

from mr_guardian.cli.main import app


def test_review_command_exits_successfully() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["review", "--base", "main", "--policy", "sources/yaml/unity-policy.yml"],
    )

    assert result.exit_code == 0


def test_review_command_outputs_placeholder_report() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["review", "--base", "main", "--policy", "sources/yaml/unity-policy.yml"],
    )

    assert "MR Guardian Review" in result.output
    assert "**Risk:** Unknown" in result.output
    assert "No rules have been implemented yet." in result.output


def test_review_command_accepts_base_and_policy_options() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["review", "--base", "develop", "--policy", "custom-policy.yml"],
    )

    assert result.exit_code == 0
