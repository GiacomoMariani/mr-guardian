# Packaging

MR Guardian can be installed from a wheel for CLI and server usage.

## Build a Wheel

From the repository root:

```bash
python -m pip wheel . --no-deps -w dist
```

The wheel includes:

- `mr_guardian` runtime package.
- `app` FastAPI and Streamlit entrypoint package.
- Packaged default YAML policies under `mr_guardian/defaults/yaml`.
- PEP 561 typing marker, `mr_guardian/py.typed`.

Source distributions include the README, installation docs, requirements files,
`.env.example`, repo-local `sources/yaml` policies, and any future files placed
under `examples/`.

## Default Policies

During local development, MR Guardian uses repo-local policies from:

```text
sources/yaml
```

When MR Guardian is installed as a package and that directory is missing or
empty, it falls back to packaged default policies. This keeps:

```bash
mr-guardian review --base main
```

usable from a clean project checkout after installation.

To use team-specific policies, set either:

```bash
mr-guardian review --base main --policy-dir path/to/policies
```

or:

```env
MR_GUARDIAN_POLICY_DIR=path/to/policies
```

Custom policy directories never fall back to packaged defaults. If the custom
directory is empty, no policy rules are evaluated.

## Smoke Checks

After building a wheel, inspect that the runtime policies are present:

```bash
python -c "import pathlib, zipfile; wheel = next(pathlib.Path('dist').glob('mr_guardian-*.whl')); names = zipfile.ZipFile(wheel).namelist(); print([name for name in names if 'defaults/yaml' in name])"
```

Then install the wheel in a clean environment and run:

```bash
mr-guardian --help
mr-guardian review --base main --no-store
```

The review command still needs to run inside a Git repository because the local
provider compares the current branch to the requested base branch.
