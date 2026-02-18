# Contributing to HyRISE

## Development Setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Run Tests

```bash
pytest -q
```

Run smoke tests only:

```bash
pytest -q tests/smoke
```

## Lint

```bash
ruff check src tests
```

## Build Package (sdist + wheel)

```bash
python -m pip install build twine
python -m build
twine check dist/*
```

## Verify Installed Wheel

```bash
python -m venv /tmp/hyrise-wheel-test
. /tmp/hyrise-wheel-test/bin/activate
python -m pip install --upgrade pip
python -m pip install dist/*.whl
hyrise --help
python -m hyrise --help
```

## End-to-End Live Smoke

Run the full release smoke flow (build + clean-wheel install + JSON process + Docker runtime):

```bash
bash scripts/live_smoke.sh
```

Notes:
- Set `HYRISE_SMOKE_IMAGE_REF` to test Apptainer against your published image ref.
- Set `HYRISE_SMOKE_STRICT_APPTAINER=1` to fail the script when Apptainer pull fails.

## Container Workflows

Pull prebuilt image:

```bash
hyrise container --pull -o hyrise.sif --image ghcr.io/phac-nml/hyrise:latest
```

Extract packaged runtime Dockerfile (pip-installed workflow):

```bash
hyrise container --extract-dockerfile ./container_build
docker build -f ./container_build/Dockerfile -t hyrise:local ./container_build
```

Build local image from definition file:

```bash
hyrise container --build-elsewhere -o hyrise.sif
```

Build OCI image from `src/hyrise/Dockerfile`:

```bash
docker build -f src/hyrise/Dockerfile -t ghcr.io/phac-nml/hyrise:local .
```

## Release Process (Maintainers)

1. Update `src/hyrise/__init__.py` version.
2. Run lint/tests and build checks locally.
3. Merge to main and let CI build/test wheel.
4. Publish OCI image (GHCR) from `src/hyrise/Dockerfile`.
5. Publish package to PyPI from CI artifacts.
6. Tag release and update changelog.
