# Rule Generation Prompt

Use this prompt when you want help converting team guidance, review notes, or
best-practice text into MR Guardian YAML rule candidates.

Generated YAML is a draft. Review every rule before using it in a real policy.
YAML remains the runtime source of truth; Markdown or other guidance documents
are human context only.

## Prompt

```text
You are helping me convert project review guidance into MR Guardian YAML rules.

Goal:
- Produce YAML rule candidates that can be reviewed by a human.
- Create one rule per executable concern.
- Separate deterministic rules, LLM rules, human-only guidance, and open
  questions.
- Do not invent certainty. If information is missing, ask the smallest useful
  set of questions before finalizing the YAML.

Context:
- MR Guardian runtime policy files use YAML.
- The only valid top-level YAML fields are:
  - version
  - rules
- Every rule must include:
  - id
  - type
  - evaluation
  - enabled
  - severity
  - source
  - description
- Use parameters when the rule needs thresholds, file patterns, required
  sections, input options, or other customization.
- evaluation must be one of:
  - coding
  - mr_structure
- type must be one of:
  - deterministic
  - llm
- deterministic rules must include implementation.
- LLM rules must include prompt.
- LLM rules are advisory and must not use severity: blocking.
- Markdown or prose guidance is optional human context only. Do not rely on it
  at runtime.

Known deterministic implementations:
- size_changed_files
- size_changed_lines
- size_changed_directories
- mr_required_section
- mr_title_ticket_key
- changed_files_require_mr_section
- changed_files_require_validation
- production_code_requires_tests_or_validation
- unity_event_subscription
- unity_per_frame_allocation
- unity_runtime_instantiation
- unity_resources_load
- csharp_debug_log
- csharp_get_component
- csharp_class_size
- csharp_method_size
- csharp_method_parameters
- csharp_public_fields
- python_print
- ai_code_large_change

When choosing implementations:
- Use an existing deterministic implementation only when it clearly matches the
  requested behavior.
- If no existing implementation matches, label it as proposed_new_implementation
  and explain what Python rule would need to be added.
- Do not pretend a proposed implementation already exists.

For LLM rules:
- Write a usable prompt draft, but mark it as a draft for human review.
- Keep the prompt narrow and evidence-based.
- Tell the LLM to report only issues grounded in the supplied MR context.
- Include output_contract parameters when useful, especially max_findings.

Output format:

1. Assumptions
   - List assumptions you made.

2. Questions
   - Ask only questions that block safe YAML generation.
   - If no questions are needed, write "None."

3. Deterministic rule candidates
   - Explain why each rule is deterministic.
   - Include YAML snippets.
   - State whether the implementation exists or is proposed.

4. LLM rule candidates
   - Explain why each rule needs judgment.
   - Include YAML snippets with prompt drafts.

5. Human-only guidance
   - List guidance that should remain prose and not become runtime rules.

6. Combined YAML draft
   - Return one YAML policy draft using only version and rules as top-level
     fields.

Guidance to convert:
<<<PASTE GUIDANCE HERE>>>
```

## Example

Input guidance:

```text
Every MR must include a Test Plan. Large MRs over 500 changed lines should be
called out. Review broad design changes for unnecessary abstraction.
```

Example output excerpt:

```yaml
version: 1

rules:
  - id: MR-META-001
    type: deterministic
    implementation: mr_required_section
    evaluation: mr_structure
    enabled: true
    severity: blocking
    source: project-policy.yml#MR-META-001
    description: MR must include a test plan.
    parameters:
      require:
        mr_sections:
          - Test Plan

  - id: SIZE-LINES-001
    type: deterministic
    implementation: size_changed_lines
    evaluation: mr_structure
    enabled: true
    severity: warning
    source: project-policy.yml#SIZE-LINES-001
    description: Large line-count changes should be split or explained.
    parameters:
      threshold:
        max_changed_lines: 500

  - id: ARCH-DESIGN-LLM-001
    type: llm
    evaluation: coding
    enabled: true
    severity: info
    source: project-policy.yml#ARCH-DESIGN-LLM-001
    description: Review whether broad design changes add unnecessary abstraction.
    prompt: |
      Review the supplied MR context for unnecessary abstraction,
      over-engineering, or design changes that are not justified by the diff.
      Only report issues grounded in the supplied MR context.
    parameters:
      inputs:
        include_diff: true
        include_changed_files: true
      output_contract:
        max_findings: 3
        allow_blocking: false
```

## Review Checklist

Before applying generated rules:

- Confirm each rule describes one concern.
- Confirm deterministic implementations really exist, or create the missing
  Python implementation and tests first.
- Confirm LLM prompts are narrow enough to avoid noisy findings.
- Confirm severities match team expectations.
- Confirm `evaluation` is correct.
- Confirm file patterns and thresholds fit the target project.
- Run `python -m mr_guardian.cli.main review --base main --no-store` before
  storing review history from the new policy.
