# MR Guardian

Python-based Unity Merge Request review assistant.

MR Guardian reviews local Git diffs or GitLab merge requests against Unity best-practice policies.

YAML files in `sources/yaml/` are the runtime source of truth. Markdown files in
`sources/markdown/` are human guidance only and are not loaded or validated by the tool.

YAML rules can be either:

- `deterministic`: implemented in Python and registered in MR Guardian.
- `llm`: prompt-driven advisory checks that will be sent to an LLM with review context.

## Development

Install dependencies:

```bash
pip install -e ".[dev]"
```

Run the CLI:

```bash
python -m mr_guardian.cli.main review --base main --policy sources/yaml/unity-policy.yml
```

Run checks:

```bash
pytest
ruff check .
mypy mr_guardian
```
