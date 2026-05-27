# Unity Rule Roadmap

This document records the current Unity rule expansion decision.

## Decision

Use deterministic rules for cheap, concrete patterns. Use LLM rules for
Unity-specific review judgment where context matters and simple string matching
would create noisy findings.

## Accepted Rules

1. `UNITY-LIFECYCLE-LLM-001`
   - Type: LLM
   - Purpose: Review fragile Unity lifecycle coupling around `Awake`,
     `OnEnable`, `Start`, `Update`, `FixedUpdate`, and script execution order.

2. `UNITY-EVENTS-001`
   - Type: deterministic
   - Purpose: Detect likely event subscription lifecycle issues, especially
     subscriptions added without matching unsubscribe paths.

3. `UNITY-PERF-GC-001`
   - Type: deterministic
   - Purpose: Detect common per-frame allocation risks in Unity callbacks.

4. `UNITY-POOLING-001`
   - Type: deterministic
   - Purpose: Detect repeated runtime `Instantiate` / `Destroy` patterns that
     may need pooling.

5. `UNITY-UI-PERF-LLM-001`
   - Type: LLM
   - Purpose: Review UI changes for Canvas rebuild, raycast target, layout, and
     dynamic UI performance risk.

6. `UNITY-RESOURCES-001`
   - Type: deterministic
   - Purpose: Detect newly introduced `Resources.Load` usage.

7. `UNITY-ASSET-LOADING-LLM-001`
   - Type: LLM
   - Purpose: Review broader Addressables, AssetBundle, runtime loading, and
     memory-management concerns.

8. `UNITY-PHYSICS-LLM-001`
   - Type: LLM
   - Purpose: Review physics update/query changes for Unity-specific correctness
     and performance risks.

9. `UNITY-SCRIPTABLEOBJECT-LLM-001`
   - Type: LLM
   - Purpose: Review ScriptableObject usage and warn when changed SOs appear to
     hold mutable non-stateless runtime state or hidden global state.

## Rejected / Deferred

- Inspector serialization and data migration LLM rule: ignored for now.
- Gameplay testability and manual validation LLM rule: ignored for now.

## Implementation Workflow

Implement one ticket at a time:

1. Add the rule to YAML.
2. Add deterministic implementation when required.
3. Add focused tests for the rule.
4. Update LLM prompt docs when adding LLM rules.
5. Run:

```bash
python -m pytest
python -m ruff check .
python -m mypy mr_guardian
```

LLM rules remain advisory and must not use `severity: blocking`.
