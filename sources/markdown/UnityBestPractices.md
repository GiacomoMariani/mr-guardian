# Unity Best Practices for MR Guardian

## MR-META-001 — MR must include a test plan

Every MR should explain how the author validated the change.

A good test plan should include:

- compile check
- affected scene check
- main success path
- edge case or regression check
- Unity Console check

## UNITY-SCENE-001 — Scene changes require manual validation

Unity scene files are serialized assets and can introduce runtime behavior changes that are hard to review from code alone.

Every MR that changes or adds a `.unity` scene must include manual validation notes.

## UNITY-PREFAB-001 — Prefab changes require validation evidence

Prefab changes can affect inspector references, runtime behavior, UI layout, and object composition.

Every prefab change should include validation evidence or reviewer notes.

## UNITY-PROJECTSETTINGS-001 — ProjectSettings changes require explanation

ProjectSettings changes can affect the whole Unity project.

Every ProjectSettings change should include risk notes and reviewer notes.

## UNITY-TESTS-001 — Gameplay code changes require tests or manual validation

Gameplay code changes should include automated tests when practical.

When tests are not practical, the MR should include manual validation notes.

## CSHARP-DEBUG-001 — Avoid committed Debug.Log statements

Debug.Log is useful during development but should not usually be committed into production code.

Temporary logs can make AI-generated code look unfinished.

## CSHARP-GETCOMPONENT-001 — Cache GetComponent calls in Awake when possible

Repeated or late GetComponent calls can hide dependencies and create unnecessary runtime work.

Prefer caching components in Awake when possible.

## AI-CODE-001 — AI-assisted code should not add unnecessary scope

AI-generated code can become too broad, add unused abstractions, or touch unrelated files.

Every AI-assisted MR should be checked for scope, tests, validation evidence, and unnecessary generated code.
