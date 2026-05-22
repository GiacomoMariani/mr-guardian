# MR Guardian

Python-based Unity Merge Request review assistant.

MR Guardian reviews local Git diffs or GitLab merge requests against Unity best-practice policies.

YAML files in `sources/yaml/` are the runtime source of truth. Markdown files in
`sources/markdown/` are human guidance only and are not loaded or validated by the tool.

## YAML Policy Format

YAML policy files are a set of executable rules. The only top-level policy fields
are:

- `version`
- `rules`

Every item under `rules` is a rule. All runtime rules come from YAML, and each
rule must declare its execution type:

- `deterministic`: implemented in Python and registered in MR Guardian.
- `llm`: prompt-driven advisory checks that will be sent to an LLM with review context.

Each rule has stable metadata plus optional parameters:

```yaml
version: 1

rules:
  - id: PYTHON-PRINT-001
    type: deterministic
    implementation: python_print
    enabled: true
    severity: warning
    source: python-policy.yml#PYTHON-PRINT-001
    description: Python code should use logging instead of newly introduced print calls.
    parameters:
      match:
        changed_files:
          - "**/*.py"
        added_lines_contain:
          - "print("
```

Rule-specific settings belong under `parameters`. Deterministic rules require an
`implementation`. LLM rules require a `prompt` and cannot use `severity: blocking`.

## Development

Install dependencies:

```bash
pip install -e ".[dev]"
```

Configure local paths:

```bash
cp .env.example .env
```

MR Guardian reads `.env` automatically. Use it to set the default repository,
YAML policy directory, default YAML policy file, human guidance directory,
SQLite history database, and reports directory. Shell environment variables
override values from `.env`.

Run the CLI:

```bash
python -m mr_guardian.cli.main review --base main
```

Run the CLI with local MR metadata:

```bash
python -m mr_guardian.cli.main review --base main --title "Add player movement" --description-file mr-description.md
```

The MR metadata options are useful for local reviews because local Git does not
provide a merge request title or description. Use `--description` for short text
or `--description-file` for a Markdown file. The same options work with
`inspect` and `inspect-all`.

Show stored review logs in a readable table:

```bash
python -m mr_guardian.cli.main logs
```

Limit how many recent review logs are shown:

```bash
python -m mr_guardian.cli.main logs --limit 10
```

Show the generated report for a stored review ID:

```bash
python -m mr_guardian.cli.main log-report 1
```

Remove all stored review logs:

```bash
python -m mr_guardian.cli.main clear-logs --yes
```

Run checks:

```bash
pytest
ruff check .
mypy mr_guardian
```
