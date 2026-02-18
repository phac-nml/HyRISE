import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_DIR = REPO_ROOT / "example_data" / "public"


def _walk_strings(value):
    if isinstance(value, dict):
        for nested in value.values():
            yield from _walk_strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_strings(nested)
    elif isinstance(value, str):
        yield value


def test_public_fixtures_exist():
    expected = {
        "DEMO_IN_NGS.fasta",
        "DEMO_PRRT_NGS.fasta",
        "DEMO_COMBO_NGS.fasta",
        "DEMO_IN_NGS_results.json",
        "DEMO_PRRT_NGS_results.json",
        "DEMO_COMBO_NGS_results.json",
    }
    present = {path.name for path in PUBLIC_DIR.iterdir() if path.is_file()}
    assert expected.issubset(present)


def test_public_fixtures_do_not_contain_original_identifiers():
    forbidden_tokens = ("1010_", "GEN2025", "01.01A")

    for path in PUBLIC_DIR.iterdir():
        if not path.is_file():
            continue

        if path.suffix == ".fasta":
            text = path.read_text()
            for token in forbidden_tokens:
                assert token not in text, f"{token} found in {path.name}"
        elif path.suffix == ".json":
            data = json.loads(path.read_text())
            all_text = "\n".join(_walk_strings(data))
            for token in forbidden_tokens:
                assert token not in all_text, f"{token} found in {path.name}"
