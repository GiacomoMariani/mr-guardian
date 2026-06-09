# MR Guardian

**Human-centered pre-review automation for merge requests.**

AI-assisted development helps teams ship faster, but it also makes changes harder to track.

MR Guardian turns best-practices into automated MR checks. 
- Deterministic rules catch clear risks like oversized MRs or protected files being modified
- LLM rules cover issues that need more context.

Developers spend less time on routine checks and more attention where human judgment creates value.

> **See it in action:** [MR-Guardian](https://mr-guardian.onrender.com)

**LLM analysis requires an API key.**

## MR Review Layout

MR Guardian generates a clear review report for every MR, showing each triggered rule alongside its severity.   
It also uses an LLM to produce a short summary of the key context behind the changes, so reviewers know *why* before they dig into *what*.

![MR Guardian dashboard in dark mode](Docs/assets/mr-guardian-dark.png)

## Rules

MR Guardian reviews merge requests using two kinds of rules:

### Deterministic Rules

Deterministic rules check clear, repeatable conditions: missing MR sections, oversized changes, or known coding patterns.   
Each one can be enabled, disabled, and tuned to match your team's standards (for example, defining exactly how many lines count as "too many").

### LLM Rules

LLM rules send selected merge request context, like the diff and changed files, through a configured prompt.  
This lets the LLM act as a reviewer for the targeted instructions you define: check this risk, inspect that pattern, or flag concerns that need broader context to catch.

## Rules Generation
MR Guardian ships with rules derived from this curated [set of best practices](https://github.com/GiacomoMariani/UnityBestPractices). You're welcome to apply them as-is, but I strongly recommend building your own: every project has its own quirks and demands its own tuning.

Deterministic rule configuration lives in [`sources/yaml/unity-policy.yml`](sources/yaml/unity-policy.yml) and [`sources/yaml/python-policy.yml`](sources/yaml/python-policy.yml). The Python implementations live in [`mr_guardian/rules/`](mr_guardian/rules/).

LLM rules need setup: write the prompt, choose the context to send, and keep the output focused. To turn existing guidance into rule candidates, use the [`rule-generation prompt`](Docs/rule-generation-prompt.md). Full LLM rule instructions are in [`Docs/llm-rule-authoring.md`](Docs/llm-rule-authoring.md).

Here's an example:

```yaml
- id: SIZE-LINES-001
  type: deterministic
  implementation: size_changed_lines
  evaluation: mr_structure
  enabled: true
  severity: warning
  source: unity-policy.yml#SIZE-LINES-001
  description: Large line-count changes should be split or explained.
  parameters:
    threshold:
      max_changed_lines: 500
```

## Review Philosophy
MR Guardian is intentionally conservative. It exists to display risks, not manufacture noise—to make human review easier without ever trying to replace it. It gives junior developers earlier feedback, frees senior engineers from mechanical checks, and gives teams a clearer memory of the risks that resurface across merge requests.

The goal isn't fewer human reviews. It's *better* ones: clearer, more focused, and more respectful of everyone's time.

## Architecture

For system layout, component boundaries, and runtime policy flow, see [`Docs/architecture.md`](Docs/architecture.md).

## Technical scope

MR Guardian applies production-oriented agentic AI engineering. It uses LLMs inside a controlled software system, not as an unbounded reviewer.

It combines tool-backed context, deterministic rules, advisory model reasoning, reporting, persistence, and human review into one review workflow.

Key technical areas:

- **Agentic workflow design:** loads policy, collects diffs, routes rules, runs LLM checks, generates reports, and persists review history.
- **Deterministic-first architecture:** keeps enforceable checks outside the model, so correctness does not depend on LLM behavior.
- **Bounded LLM execution:** scopes model input, requires structured output, limits findings, handles retries, tracks tokens, and keeps feedback advisory.
- **Tool-augmented reasoning:** uses MR metadata, changed files, diff hunks, GitLab webhook events, repository state, and historical review data.
- **Policy-as-code:** defines executable YAML rules with stable IDs, typed validation, and package-ready defaults.
- **Human-in-the-loop review:** surfaces risk for engineers while keeping final judgment with the people responsible for the system.
- **Production reliability:** handles structured outputs, fallbacks, rate limits, non-fatal provider failures, tests, packaging, persisted metrics, and optional MR comments.
- **Unity-specific review judgment:** checks scenes, prefabs, `ProjectSettings`, gameplay scripts, validation evidence, runtime loading, lifecycle behavior, physics, UI, ScriptableObjects, `GetComponent`, event subscriptions, per-frame allocations, pooling, and `Resources.Load`.

This is not “AI reviews code.”

This is an agentic review layer that is traceable, bounded, testable, and useful in a real engineering workflow.

## Documentation

- Architecture: [`Docs/architecture.md`](Docs/architecture.md)
- Installation: [`Docs/installation.md`](Docs/installation.md)
- Packaging notes: [`Docs/packaging.md`](Docs/packaging.md)
- Agent-assisted setup: [`Docs/agent-setup-prompt.md`](Docs/agent-setup-prompt.md)
- Rule generation prompt: [`Docs/rule-generation-prompt.md`](Docs/rule-generation-prompt.md)
- LLM rule authoring: [`Docs/llm-rule-authoring.md`](Docs/llm-rule-authoring.md)
- PM dashboard: [`Docs/pm-dashboard.md`](Docs/pm-dashboard.md)
- Lead dashboard: [`Docs/lead-dashboard.md`](Docs/lead-dashboard.md)
- Developer performance: [`Docs/developer-performance.md`](Docs/developer-performance.md)
- Developer AI profiles: [`Docs/developer-ai-profiles.md`](Docs/developer-ai-profiles.md)
- Weekly LLM review: [`Docs/weekly-llm-review.md`](Docs/weekly-llm-review.md)
- Manual review submission: [`Docs/manual-review-submission.md`](Docs/manual-review-submission.md)
- Ticket key conventions: [`Docs/ticket-key-conventions.md`](Docs/ticket-key-conventions.md)
- Review history schema: [`Docs/review-history-schema.md`](Docs/review-history-schema.md)
- Docker and Render notes: [`Docs/docker-deployment.md`](Docs/docker-deployment.md)
- API — review feeds: [`Docs/api-review-feeds.md`](Docs/api-review-feeds.md)
- API — review finality: [`Docs/api-review-finality.md`](Docs/api-review-finality.md)
- API — review deletion: [`Docs/api-review-deletion.md`](Docs/api-review-deletion.md)
- API — dashboard ETA note: [`Docs/api-eta-note.md`](Docs/api-eta-note.md)
- API — reset all data: [`Docs/api-reset.md`](Docs/api-reset.md)

## Roadmap

Implemented features include local review, all-policy YAML loading, deterministic Unity/C#/MR rules, advisory OpenAI-backed LLM rules, optional LLM review summaries, GitLab webhooks, optional GitLab MR comments, SQLite review history, manual review import, PM and lead Streamlit dashboards, developer performance summaries, report noise control, and wheel packaging.

Planned improvements:

- Add evaluation benchmarks for deterministic rules, LLM rules, and LLM summaries.
- Add richer observability for rule execution, prompt size, provider latency, token usage, and review outcomes.
- Add review comparison views to track how an MR changes between review attempts.
- Expand GitLab integration with richer MR metadata, merge state, approval state, and deployment signals.
- Harden deployment with database migrations, authentication boundaries, CI packaging checks, and release automation.
