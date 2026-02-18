from __future__ import annotations

import importlib
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def _purge_hyrise_modules() -> None:
    for name in list(sys.modules):
        if name == "hyrise" or name.startswith("hyrise."):
            sys.modules.pop(name, None)


def test_import_hyrise_is_lightweight_and_explicit() -> None:
    _purge_hyrise_modules()

    pkg = importlib.import_module("hyrise")

    assert isinstance(pkg.__version__, str)
    assert pkg.__version__
    assert pkg.__all__ == ["__version__"]

    # Top-level import should not eagerly import command/processing modules.
    assert "hyrise.cli" not in sys.modules
    assert "hyrise.core.processor" not in sys.modules
    assert "hyrise.commands.sierra" not in sys.modules


def test_star_import_uses_curated_public_api() -> None:
    _purge_hyrise_modules()

    namespace: dict[str, object] = {}
    exec("from hyrise import *", namespace)

    exposed = {name for name in namespace if name != "__builtins__"}
    assert exposed == {"__version__"}


def test_pyproject_dynamic_version_points_to_hyrise_version() -> None:
    with PYPROJECT_PATH.open("rb") as handle:
        pyproject_data = tomllib.load(handle)

    version_attr = pyproject_data["tool"]["setuptools"]["dynamic"]["version"]["attr"]
    assert version_attr == "hyrise.__version__"
