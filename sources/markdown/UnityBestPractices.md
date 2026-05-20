# Unity Best Practices for MR Guardian

## SIZE-FILES-001 — Large file-count changes should be split or explained

Merge requests that touch many files are harder to review safely.

Large file-count changes should be split into focused reviewable units or include a clear explanation of why the broad change is necessary.

## SIZE-LINES-001 — Large line-count changes should be split or explained

Merge requests with large changed-line counts are harder to validate and more likely to hide regressions.

Large line-count changes should be split when practical or include reviewer notes explaining the scope.

## SIZE-DIRECTORIES-001 — Broad directory changes should be split or explained

Merge requests that touch many directories can indicate unrelated scope.

Broad directory changes should be split by concern or include a clear explanation of why the directories changed together.

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

## CSHARP-DEBUG-001 — Avoid newly introduced debug logging

Debug.Log and print statements are useful during development but should not usually be committed into production code unless explicitly allowed.

Temporary logs can make AI-generated code look unfinished.

## CSHARP-GETCOMPONENT-001 — Cache GetComponent calls in Awake when possible

Repeated or late GetComponent calls can hide dependencies and create unnecessary runtime work.

Prefer caching components in Awake when possible.

## AI-CODE-001 — AI-assisted code should not add unnecessary scope

AI-generated code can become too broad, add unused abstractions, or touch unrelated files.

Every AI-assisted MR should be checked for scope, tests, validation evidence, and unnecessary generated code.
