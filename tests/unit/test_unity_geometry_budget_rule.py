"""Tests for UNITY-GEOMETRY-BUDGET-001 .obj triangle counting (ticket 055)."""

from pathlib import Path

from mr_guardian.core.engine import run_review
from mr_guardian.models.policy import Policy, PolicyRule
from mr_guardian.models.review_input import ChangedFile, ReviewInput
from mr_guardian.rules import default_rule_registry


def _changed(path: str) -> ChangedFile:
    return ChangedFile(path=Path(path), status="added", hunks=[])


def _review(changed: list[ChangedFile], repo_root: Path | None):
    rule = PolicyRule(
        id="UNITY-GEOMETRY-BUDGET-001",
        type="deterministic",
        implementation="unity_geometry_triangle_budget",
        enabled=True,
        severity="blocking",
        source="unity-policy.yml#UNITY-GEOMETRY-BUDGET-001",
        description="Geometry budget.",
        parameters={"threshold": {"warn_triangles": 20000, "block_triangles": 50000}},
    )
    return run_review(
        policy=Policy(version=1, rules=[rule]),
        review_input=ReviewInput(base_ref="main", changed_files=changed),
        rule_registry=default_rule_registry(),
        repo_root=repo_root,
    )


def _write_mesh(repo_root: Path, rel: str, content: str) -> None:
    asset = repo_root / rel
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_text(content, encoding="utf-8")


def test_flags_obj_over_triangle_budget(tmp_path: Path) -> None:
    # Header + vertices (ignored) + 60000 triangle faces.
    content = "# mesh\nv 0 0 0\nv 1 0 0\nv 0 1 0\n" + "f 1 2 3\n" * 60000
    _write_mesh(tmp_path, "Assets/Models/dense.obj", content)

    result = _review([_changed("Assets/Models/dense.obj")], tmp_path)

    assert [f.rule_id for f in result.findings] == ["UNITY-GEOMETRY-BUDGET-001"]
    assert result.findings[0].severity == "blocking"


def test_counts_polygons_as_multiple_triangles(tmp_path: Path) -> None:
    # 30000 quads => 60000 triangles, over budget.
    _write_mesh(tmp_path, "Assets/Models/quads.obj", "f 1 2 3 4\n" * 30000)

    result = _review([_changed("Assets/Models/quads.obj")], tmp_path)

    assert [f.rule_id for f in result.findings] == ["UNITY-GEOMETRY-BUDGET-001"]


def test_ignores_obj_under_budget(tmp_path: Path) -> None:
    _write_mesh(tmp_path, "Assets/Models/light.obj", "f 1 2 3\n" * 100)

    result = _review([_changed("Assets/Models/light.obj")], tmp_path)

    assert result.findings == []


def test_skips_unparsed_mesh_format(tmp_path: Path) -> None:
    _write_mesh(tmp_path, "Assets/Models/model.fbx", "binary-ish content")

    result = _review([_changed("Assets/Models/model.fbx")], tmp_path)

    assert result.findings == []


def test_no_finding_without_repo_root() -> None:
    result = _review([_changed("Assets/Models/dense.obj")], None)

    assert result.findings == []
