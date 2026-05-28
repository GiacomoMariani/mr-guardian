# LLM Rule Authoring

MR Guardian LLM rules are YAML rules with `type: llm`. They are used for
advisory review checks that need judgment over the diff, such as unnecessary
abstraction, unclear scope, or risky design changes.

LLM rules are never allowed to create blocking findings. Use deterministic rules
for checks that must block a Merge Request.

Every LLM rule declares an evaluation dimension:

- `coding` for implementation, runtime, design, maintainability, and Unity/C#/Python
  code concerns.
- `mr_structure` for MR readiness, scope, metadata, validation evidence, and
  reviewer context.

## Minimal Rule

```yaml
- id: PYTHON-DESIGN-LLM-001
  type: llm
  evaluation: coding
  enabled: true
  severity: info
  source: python-policy.yml#PYTHON-DESIGN-LLM-001
  description: Check whether the Python change adds unnecessary abstraction.
  prompt: |
    Review the provided Python diff for unnecessary abstraction,
    over-engineering, or unrelated scope.
    Only report issues grounded in the diff.
  parameters:
    inputs:
      include_diff: true
      include_changed_files: true
    output_contract:
      max_findings: 3
      allow_blocking: false
```

## Prompt Shape

Write prompts as review instructions, not as general policy essays.

Good prompts:

```text
Review the provided Python diff for unnecessary abstraction,
over-engineering, or unrelated scope.
Only report issues grounded in the diff.
```

```text
Review the Unity C# diff for gameplay changes that are hard to validate
manually or lack a clear test path.
Only report concrete concerns visible in the changed lines.
```

Avoid prompts like:

```text
Find all possible problems in this Merge Request.
```

```text
Make sure this code follows all best practices.
```

Those prompts are too broad and produce noisy findings.

## Inputs

LLM rules can choose which review context they receive:

```yaml
parameters:
  inputs:
    include_diff: true
    include_changed_files: true
```

Use `include_diff: true` when the rule needs line-level evidence.

Use `include_changed_files: true` when the rule needs scope or file-pattern
context.

Do not disable both unless the rule can operate from only the title and
description. Today, most LLM rules should keep both enabled.

## Output Contract

MR Guardian asks the LLM to return structured JSON and validates the response.
The YAML rule can limit how much output is accepted:

```yaml
parameters:
  output_contract:
    max_findings: 3
    allow_blocking: false
```

`max_findings` keeps reports readable. A good default is `3`.

`allow_blocking` should remain `false`. MR Guardian also enforces this in code:
if an LLM response tries to create a blocking finding, it is downgraded to
`high`.

LLM output may include an `evaluation` value per finding. When it is omitted,
MR Guardian uses the YAML rule's configured evaluation. Invalid evaluation
values are rejected during output validation.

## Severity

Allowed severities are:

```text
high
warning
info
```

Do not use `blocking` for LLM rules. Policy loading rejects blocking LLM rules.

Suggested defaults:

- `info` for design, scope, readability, and maintainability prompts.
- `warning` for prompts that identify concrete review risk.
- `high` only when the prompt is narrow and the finding is likely actionable.

## Source

Use the YAML rule ID as the source reference:

```yaml
source: python-policy.yml#PYTHON-DESIGN-LLM-001
```

Markdown documents are human guidance only. Runtime code does not load Markdown
for LLM rules.

## Runtime Configuration

LLM rules run only when OpenAI is enabled:

```env
MR_GUARDIAN_LLM_PROVIDER=openai
MR_GUARDIAN_OPENAI_API_KEY=your_openai_api_key_here
MR_GUARDIAN_OPENAI_MODEL=gpt-4.1-mini
MR_GUARDIAN_OPENAI_TIMEOUT_SECONDS=30
MR_GUARDIAN_OPENAI_MAX_RETRIES=2
```

If the provider is disabled or the API key is missing, LLM rules are skipped.

If OpenAI times out, rate-limits, or returns malformed JSON, MR Guardian reports
an advisory `info` finding for the affected LLM rule and continues deterministic
review execution.

## Authoring Checklist

- Use `type: llm`.
- Set `evaluation` to `coding` or `mr_structure`.
- Keep the rule `enabled` only when the prompt is ready for normal reports.
- Keep severity advisory: `info`, `warning`, or `high`.
- Make the prompt narrow and evidence-based.
- Include `Only report issues grounded in the diff.`
- Set `max_findings` to a small number, usually `3`.
- Keep `allow_blocking: false`.
- Test the rule with `python -m mr_guardian.cli.main review --base main --no-store`.
