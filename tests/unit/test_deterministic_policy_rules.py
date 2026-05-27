from pathlib import Path

from mr_guardian.core import run_review
from mr_guardian.models.policy import Policy, PolicyRule
from mr_guardian.models.review_input import ChangedFile, DiffHunk, DiffLine, ReviewInput
from mr_guardian.rules import default_rule_registry

DETERMINISTIC_RULE_IDS = {
    "SIZE-FILES-001",
    "SIZE-LINES-001",
    "SIZE-DIRECTORIES-001",
    "MR-META-001",
    "MR-META-002",
    "MR-META-003",
    "MR-META-004",
    "MR-META-005",
    "UNITY-SCENE-001",
    "UNITY-PREFAB-001",
    "UNITY-PROJECTSETTINGS-001",
    "UNITY-TESTS-001",
    "UNITY-EVENTS-001",
    "UNITY-PERF-GC-001",
    "UNITY-POOLING-001",
    "UNITY-RESOURCES-001",
    "CSHARP-DEBUG-001",
    "CSHARP-GETCOMPONENT-001",
    "CSHARP-SIZE-001",
    "CSHARP-SIZE-002",
    "CSHARP-PARAMETERS-001",
    "CSHARP-PUBLIC-FIELDS-001",
    "AI-CODE-001",
    "PYTHON-PRINT-001",
}


def make_policy(rule: PolicyRule) -> Policy:
    return Policy(version=1, rules=[rule])


def make_rule(
    rule_id: str,
    *,
    implementation: str,
    severity: str = "warning",
    parameters: dict[str, object] | None = None,
) -> PolicyRule:
    return PolicyRule(
        id=rule_id,
        type="deterministic",
        implementation=implementation,
        enabled=True,
        severity=severity,
        source=f"unity-policy.yml#{rule_id}",
        description="Test rule.",
        parameters=parameters or {},
    )


def make_changed_file(
    path: str,
    *,
    added_lines: list[str] | None = None,
    deleted_lines: list[str] | None = None,
) -> ChangedFile:
    lines: list[DiffLine] = []
    next_line = 1
    for content in deleted_lines or []:
        lines.append(
            DiffLine(
                kind="deletion",
                content=content,
                old_line_number=next_line,
                new_line_number=None,
            )
        )
    for content in added_lines or []:
        lines.append(
            DiffLine(
                kind="addition",
                content=content,
                old_line_number=None,
                new_line_number=next_line,
            )
        )
        next_line += 1

    return ChangedFile(
        path=Path(path),
        status="modified",
        hunks=[DiffHunk(old_start=1, old_count=1, new_start=1, new_count=1, lines=lines)],
    )


def review(rule: PolicyRule, review_input: ReviewInput):
    return run_review(
        policy=make_policy(rule),
        review_input=review_input,
        rule_registry=default_rule_registry(),
    )


def test_default_registry_contains_every_deterministic_rule() -> None:
    registry = default_rule_registry()

    assert all(registry.get(rule_id) is not None for rule_id in DETERMINISTIC_RULE_IDS)


def test_changed_file_count_threshold_triggers() -> None:
    rule = make_rule(
        "SIZE-FILES-001",
        implementation="size_changed_files",
        parameters={"threshold": {"max_changed_files": 1}},
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[
            make_changed_file("Assets/Scripts/A.cs"),
            make_changed_file("Assets/Scripts/B.cs"),
        ],
    )

    result = review(rule, review_input)

    assert result.findings[0].rule_id == "SIZE-FILES-001"


def test_changed_line_count_threshold_triggers() -> None:
    rule = make_rule(
        "SIZE-LINES-001",
        implementation="size_changed_lines",
        parameters={"threshold": {"max_changed_lines": 1}},
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[make_changed_file("Assets/Scripts/A.cs", added_lines=["a\n", "b\n"])],
    )

    result = review(rule, review_input)

    assert result.findings[0].rule_id == "SIZE-LINES-001"


def test_changed_directory_count_threshold_triggers() -> None:
    rule = make_rule(
        "SIZE-DIRECTORIES-001",
        implementation="size_changed_directories",
        parameters={"threshold": {"max_changed_directories": 1}},
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[
            make_changed_file("Assets/Scripts/A.cs"),
            make_changed_file("Assets/Scenes/Main.unity"),
        ],
    )

    result = review(rule, review_input)

    assert result.findings[0].rule_id == "SIZE-DIRECTORIES-001"


def test_required_mr_section_triggers_when_missing() -> None:
    rule = make_rule(
        "MR-META-001",
        implementation="mr_required_section",
        severity="blocking",
        parameters={"require": {"mr_sections": ["Test Plan"]}},
    )
    review_input = ReviewInput(base_ref="main", changed_files=[], description="Summary only")

    result = review(rule, review_input)

    assert result.findings[0].rule_id == "MR-META-001"
    assert result.findings[0].severity == "blocking"


def test_required_mr_section_passes_when_present() -> None:
    rule = make_rule(
        "MR-META-001",
        implementation="mr_required_section",
        parameters={"require": {"mr_sections": ["Test Plan"]}},
    )
    review_input = ReviewInput(base_ref="main", changed_files=[], description="## Test Plan\n- Ran")

    result = review(rule, review_input)

    assert result.findings == []


def test_each_mr_metadata_rule_id_triggers() -> None:
    expected_sections = {
        "MR-META-002": "Summary",
        "MR-META-003": "Linked Issue",
        "MR-META-004": "Risk",
        "MR-META-005": "Reviewer Notes",
    }

    for rule_id, section in expected_sections.items():
        rule = make_rule(
            rule_id,
            implementation="mr_required_section",
            parameters={"require": {"mr_sections": [section]}},
        )
        review_input = ReviewInput(
            base_ref="main",
            changed_files=[],
            description="Different section",
        )

        result = review(rule, review_input)

        assert result.findings[0].rule_id == rule_id
        assert section in result.findings[0].message


def test_unity_scene_requires_manual_validation_section() -> None:
    rule = make_rule(
        "UNITY-SCENE-001",
        implementation="changed_files_require_mr_section",
        parameters={
            "match": {"changed_files": ["Assets/**/*.unity"]},
            "require": {"mr_sections": ["Manual Validation"]},
        },
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[make_changed_file("Assets/Scenes/Main.unity")],
        description="## Test Plan\n- Ran",
    )

    result = review(rule, review_input)

    assert result.findings[0].file_path == Path("Assets/Scenes/Main.unity")


def test_prefab_requires_validation_evidence() -> None:
    rule = make_rule(
        "UNITY-PREFAB-001",
        implementation="changed_files_require_validation",
        parameters={"match": {"changed_files": ["Assets/**/*.prefab"]}},
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[make_changed_file("Assets/Prefabs/Player.prefab")],
        description="Summary only",
    )

    result = review(rule, review_input)

    assert result.findings[0].rule_id == "UNITY-PREFAB-001"


def test_project_settings_requires_risk_and_reviewer_notes() -> None:
    rule = make_rule(
        "UNITY-PROJECTSETTINGS-001",
        implementation="changed_files_require_mr_section",
        parameters={
            "match": {"changed_files": ["ProjectSettings/**"]},
            "require": {"mr_sections": ["Risk", "Reviewer Notes"]},
        },
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[make_changed_file("ProjectSettings/ProjectSettings.asset")],
        description="## Risk\nLow",
    )

    result = review(rule, review_input)

    assert "Reviewer Notes" in result.findings[0].message


def test_gameplay_code_requires_tests_or_validation() -> None:
    rule = make_rule(
        "UNITY-TESTS-001",
        implementation="production_code_requires_tests_or_validation",
        parameters={
            "match": {"changed_files": ["Assets/Scripts/**", "Assets/**/Scripts/**"]},
            "require_any": {
                "changed_files": ["Assets/Tests/**", "Assets/**/Tests/**", "Tests/**"],
                "mr_sections": ["Manual Validation"],
            },
        },
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[make_changed_file("Assets/Scripts/Player.cs")],
        description="Summary only",
    )

    result = review(rule, review_input)

    assert result.findings[0].rule_id == "UNITY-TESTS-001"


def test_gameplay_code_passes_when_test_file_changed() -> None:
    rule = make_rule(
        "UNITY-TESTS-001",
        implementation="production_code_requires_tests_or_validation",
        parameters={
            "match": {"changed_files": ["Assets/Scripts/**", "Assets/**/Scripts/**"]},
            "require_any": {"changed_files": ["Assets/Tests/**"]},
        },
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[
            make_changed_file("Assets/Scripts/Player.cs"),
            make_changed_file("Assets/Tests/PlayerTests.cs"),
        ],
    )

    result = review(rule, review_input)

    assert result.findings == []


def test_unity_event_subscription_rule_triggers_without_unsubscribe() -> None:
    rule = make_rule(
        "UNITY-EVENTS-001",
        implementation="unity_event_subscription",
        parameters={
            "match": {
                "changed_files": ["Assets/**/*.cs"],
                "subscribe_tokens": ["+=", ".AddListener(", "AddEventListener("],
                "unsubscribe_tokens": ["-=", ".RemoveListener(", "RemoveEventListener("],
            }
        },
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[
            make_changed_file(
                "Assets/Scripts/PlayerHud.cs",
                added_lines=["health.OnChanged += Refresh;\n"],
            )
        ],
    )

    result = review(rule, review_input)

    assert len(result.findings) == 1
    assert result.findings[0].rule_id == "UNITY-EVENTS-001"
    assert result.findings[0].severity == "warning"
    assert result.findings[0].file_path == Path("Assets/Scripts/PlayerHud.cs")
    assert result.findings[0].line_number == 1


def test_unity_event_subscription_rule_passes_with_unsubscribe() -> None:
    rule = make_rule(
        "UNITY-EVENTS-001",
        implementation="unity_event_subscription",
        parameters={
            "match": {
                "changed_files": ["Assets/**/*.cs"],
                "subscribe_tokens": ["+=", ".AddListener(", "AddEventListener("],
                "unsubscribe_tokens": ["-=", ".RemoveListener(", "RemoveEventListener("],
            }
        },
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[
            make_changed_file(
                "Assets/Scripts/PlayerHud.cs",
                added_lines=[
                    "health.OnChanged += Refresh;\n",
                    "health.OnChanged -= Refresh;\n",
                ],
            )
        ],
    )

    result = review(rule, review_input)

    assert result.findings == []


def test_unity_per_frame_allocation_rule_triggers_inside_update() -> None:
    rule = make_rule(
        "UNITY-PERF-GC-001",
        implementation="unity_per_frame_allocation",
        parameters={
            "match": {
                "changed_files": ["Assets/**/*.cs"],
                "callbacks": ["Update", "LateUpdate", "FixedUpdate"],
                "allocation_tokens": ["new ", ".Where(", ".Select(", ".ToList("],
            }
        },
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[
            make_changed_file(
                "Assets/Scripts/EnemyTracker.cs",
                added_lines=[
                    "private void Update() {\n",
                    "var visibleEnemies = new List<Enemy>();\n",
                    "}\n",
                ],
            )
        ],
    )

    result = review(rule, review_input)

    assert len(result.findings) == 1
    assert result.findings[0].rule_id == "UNITY-PERF-GC-001"
    assert result.findings[0].severity == "warning"
    assert result.findings[0].file_path == Path("Assets/Scripts/EnemyTracker.cs")
    assert result.findings[0].line_number == 2


def test_unity_per_frame_allocation_rule_passes_outside_update() -> None:
    rule = make_rule(
        "UNITY-PERF-GC-001",
        implementation="unity_per_frame_allocation",
        parameters={
            "match": {
                "changed_files": ["Assets/**/*.cs"],
                "callbacks": ["Update", "LateUpdate", "FixedUpdate"],
                "allocation_tokens": ["new ", ".Where(", ".Select(", ".ToList("],
            }
        },
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[
            make_changed_file(
                "Assets/Scripts/EnemyTracker.cs",
                added_lines=[
                    "private void Awake() {\n",
                    "visibleEnemies = new List<Enemy>();\n",
                    "}\n",
                ],
            )
        ],
    )

    result = review(rule, review_input)

    assert result.findings == []


def test_unity_pooling_rule_triggers_for_runtime_instantiate() -> None:
    rule = make_rule(
        "UNITY-POOLING-001",
        implementation="unity_runtime_instantiation",
        parameters={
            "match": {
                "changed_files": ["Assets/**/*.cs"],
                "pooling_tokens": ["Instantiate(", "Destroy("],
                "runtime_method_name_contains": ["Spawn", "Update", "OnTrigger"],
            }
        },
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[
            make_changed_file(
                "Assets/Scripts/EnemySpawner.cs",
                added_lines=[
                    "private void SpawnEnemy() {\n",
                    "var enemy = Instantiate(enemyPrefab);\n",
                    "}\n",
                ],
            )
        ],
    )

    result = review(rule, review_input)

    assert len(result.findings) == 1
    assert result.findings[0].rule_id == "UNITY-POOLING-001"
    assert result.findings[0].severity == "warning"
    assert result.findings[0].file_path == Path("Assets/Scripts/EnemySpawner.cs")
    assert result.findings[0].line_number == 2


def test_unity_pooling_rule_passes_for_setup_instantiate() -> None:
    rule = make_rule(
        "UNITY-POOLING-001",
        implementation="unity_runtime_instantiation",
        parameters={
            "match": {
                "changed_files": ["Assets/**/*.cs"],
                "pooling_tokens": ["Instantiate(", "Destroy("],
                "runtime_method_name_contains": ["Spawn", "Update", "OnTrigger"],
            }
        },
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[
            make_changed_file(
                "Assets/Scripts/EnemySpawner.cs",
                added_lines=[
                    "private void Awake() {\n",
                    "previewEnemy = Instantiate(enemyPrefab);\n",
                    "}\n",
                ],
            )
        ],
    )

    result = review(rule, review_input)

    assert result.findings == []


def test_unity_resources_load_rule_triggers_for_added_resource_load() -> None:
    rule = make_rule(
        "UNITY-RESOURCES-001",
        implementation="unity_resources_load",
        parameters={
            "match": {
                "changed_files": ["Assets/**/*.cs"],
                "resource_tokens": ["Resources.Load", "Resources.LoadAll"],
            }
        },
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[
            make_changed_file(
                "Assets/Scripts/AssetLoader.cs",
                added_lines=["var prefab = Resources.Load<GameObject>(assetPath);\n"],
            )
        ],
    )

    result = review(rule, review_input)

    assert len(result.findings) == 1
    assert result.findings[0].rule_id == "UNITY-RESOURCES-001"
    assert result.findings[0].severity == "warning"
    assert result.findings[0].file_path == Path("Assets/Scripts/AssetLoader.cs")
    assert result.findings[0].line_number == 1


def test_unity_resources_load_rule_passes_without_resource_load() -> None:
    rule = make_rule(
        "UNITY-RESOURCES-001",
        implementation="unity_resources_load",
        parameters={
            "match": {
                "changed_files": ["Assets/**/*.cs"],
                "resource_tokens": ["Resources.Load", "Resources.LoadAll"],
            }
        },
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[
            make_changed_file(
                "Assets/Scripts/AssetLoader.cs",
                added_lines=["var handle = Addressables.LoadAssetAsync<GameObject>(assetKey);\n"],
            )
        ],
    )

    result = review(rule, review_input)

    assert result.findings == []


def test_csharp_get_component_rule_triggers() -> None:
    rule = make_rule(
        "CSHARP-GETCOMPONENT-001",
        implementation="csharp_get_component",
        parameters={
            "match": {
                "changed_files": ["Assets/**/*.cs"],
                "added_lines_contain": ["GetComponent<"],
            }
        },
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[
            make_changed_file(
                "Assets/Scripts/Player.cs",
                added_lines=["var rb = GetComponent<Rigidbody>();\n"],
            )
        ],
    )

    result = review(rule, review_input)

    assert result.findings[0].line_number == 1


def test_csharp_class_size_rule_triggers() -> None:
    rule = make_rule(
        "CSHARP-SIZE-001",
        implementation="csharp_class_size",
        parameters={"threshold": {"max_class_lines": 3}},
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[
            make_changed_file(
                "Assets/Scripts/Large.cs",
                added_lines=["public class Large {\n", "void A() {}\n", "void B() {}\n", "}\n"],
            )
        ],
    )

    result = review(rule, review_input)

    assert result.findings[0].rule_id == "CSHARP-SIZE-001"


def test_csharp_method_size_rule_triggers() -> None:
    rule = make_rule(
        "CSHARP-SIZE-002",
        implementation="csharp_method_size",
        parameters={"threshold": {"max_method_lines": 2}},
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[
            make_changed_file(
                "Assets/Scripts/Large.cs",
                added_lines=["public void Move() {\n", "A();\n", "B();\n", "}\n"],
            )
        ],
    )

    result = review(rule, review_input)

    assert result.findings[0].rule_id == "CSHARP-SIZE-002"


def test_csharp_method_parameter_count_rule_triggers() -> None:
    rule = make_rule(
        "CSHARP-PARAMETERS-001",
        implementation="csharp_method_parameters",
        parameters={"threshold": {"max_method_parameters": 2}},
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[
            make_changed_file(
                "Assets/Scripts/Player.cs",
                added_lines=["public void Move(int a, int b, int c) {}\n"],
            )
        ],
    )

    result = review(rule, review_input)

    assert result.findings[0].rule_id == "CSHARP-PARAMETERS-001"


def test_csharp_public_fields_rule_triggers() -> None:
    rule = make_rule(
        "CSHARP-PUBLIC-FIELDS-001",
        implementation="csharp_public_fields",
        parameters={"match": {"changed_files": ["Assets/**/*.cs"]}},
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[
            make_changed_file("Assets/Scripts/Player.cs", added_lines=["public int Health;\n"])
        ],
    )

    result = review(rule, review_input)

    assert result.findings[0].rule_id == "CSHARP-PUBLIC-FIELDS-001"


def test_ai_code_large_change_rule_triggers() -> None:
    rule = make_rule(
        "AI-CODE-001",
        implementation="ai_code_large_change",
        parameters={"match": {"changed_files_count_greater_than": 1}},
    )
    review_input = ReviewInput(
        base_ref="main",
        changed_files=[
            make_changed_file("Assets/Scripts/A.cs"),
            make_changed_file("Assets/Scripts/B.cs"),
        ],
    )

    result = review(rule, review_input)

    assert result.findings[0].rule_id == "AI-CODE-001"
