from __future__ import annotations

import ast
import pathlib
import sys

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
SRC_ROOT = REPO_ROOT / "src" / "hyrise"


IMPORT_TO_PACKAGE = {
    "bs4": "beautifulsoup4",
    "questionary": "questionary",
    "requests": "requests",
    "rich": "rich",
    "tomli": "tomli",
    "yaml": "pyyaml",
}


def _normalize_requirement_name(requirement: str) -> str:
    base = requirement.split(";", 1)[0].strip()
    if "@" in base:
        base = base.split("@", 1)[0].strip()
    for token in ("==", ">=", "<=", "!=", "~=", ">", "<"):
        if token in base:
            base = base.split(token, 1)[0].strip()
            break
    return base.lower().replace("_", "-")


def _read_project_data() -> dict:
    with PYPROJECT_PATH.open("rb") as handle:
        return tomllib.load(handle)["project"]


def _third_party_import_roots() -> set[str]:
    imports: set[str] = set()
    stdlib = set(sys.stdlib_module_names)

    for path in SRC_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.add(name.name.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports.add(node.module.split(".", 1)[0])

    return {name for name in imports if name not in stdlib and name != "hyrise"}


def test_questionary_is_core_dependency():
    project = _read_project_data()
    dependency_names = {
        _normalize_requirement_name(requirement)
        for requirement in project["dependencies"]
    }
    assert "questionary" in dependency_names


def test_multiqc_is_core_dependency():
    project = _read_project_data()
    dependency_names = {
        _normalize_requirement_name(requirement)
        for requirement in project["dependencies"]
    }
    assert "multiqc" in dependency_names


def test_third_party_imports_have_declared_dependencies():
    project = _read_project_data()
    all_requirements = list(project["dependencies"])
    for extra_requirements in project.get("optional-dependencies", {}).values():
        all_requirements.extend(extra_requirements)

    declared = {_normalize_requirement_name(req) for req in all_requirements}
    third_party_roots = _third_party_import_roots()

    missing = []
    for import_root in sorted(third_party_roots):
        package_name = IMPORT_TO_PACKAGE.get(import_root)
        if package_name is None:
            missing.append(import_root)
            continue
        if package_name not in declared:
            missing.append(import_root)

    assert not missing, f"Missing dependency declarations for imports: {missing}"


def test_package_data_includes_hivdb_xml_glob():
    pyproject_data = tomllib.loads(PYPROJECT_PATH.read_text())
    package_data = pyproject_data["tool"]["setuptools"]["package-data"]["hyrise"]
    assert "HIVDB_*.xml" in package_data
