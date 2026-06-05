"""Deterministic rule counting Unity mesh triangles from changed assets.

Ticket 055. Reads changed mesh files via the review checkout (ticket 058) and
counts triangles directly. v1 parses Wavefront ``.obj`` (text, no dependency);
binary formats (``.fbx``, ``.blend``, ``.dae``) are skipped until a mesh-parsing
dependency is added.
"""

from mr_guardian.models.policy import PolicyRule
from mr_guardian.models.review import Finding
from mr_guardian.rules.base import RuleEvaluationContext
from mr_guardian.rules.helpers import finding, int_parameter

# Parseable today. Deferred (need a mesh lib): .fbx, .blend, .dae.
_PARSEABLE_SUFFIXES = {".obj"}
_DEFAULT_BLOCK_TRIANGLES = 50000


class UnityGeometryBudgetRule:
    """Flag changed meshes whose triangle count exceeds the geometry budget."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, context: RuleEvaluationContext, rule: PolicyRule) -> list[Finding]:
        block_triangles = (
            int_parameter(rule, "threshold", "block_triangles") or _DEFAULT_BLOCK_TRIANGLES
        )
        findings: list[Finding] = []
        for changed_file in context.review_input.changed_files:
            if changed_file.status not in {"added", "modified", "renamed"}:
                continue
            if changed_file.path.suffix.lower() not in _PARSEABLE_SUFFIXES:
                continue
            data = context.read_changed_bytes(changed_file.path)
            if data is None:
                continue
            triangles = _obj_triangle_count(data)
            if triangles < block_triangles:
                continue
            findings.append(
                finding(
                    rule,
                    (
                        f"Mesh {changed_file.path.as_posix()} has ~{triangles:,} triangles, "
                        f"over the {block_triangles:,} budget. Decimate the mesh or add LODs."
                    ),
                    file_path=changed_file.path,
                )
            )
        return findings


def _obj_triangle_count(data: bytes) -> int:
    """Count triangles in a Wavefront .obj: each face of N vertices is N-2 triangles."""
    triangles = 0
    for line in data.decode("utf-8", errors="ignore").splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0] == "f":
            triangles += len(parts) - 3  # (len(parts) - 1) vertices, minus 2
    return triangles
