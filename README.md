# MR Guardian

Python-based Unity Merge Request review assistant.

MR Guardian reviews local Git diffs or GitLab merge requests against Unity best-practice policies.

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
