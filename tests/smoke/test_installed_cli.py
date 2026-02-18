import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_cli_entrypoints_help():
    module_help = subprocess.run(
        [sys.executable, "-m", "hyrise", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert module_help.returncode == 0
    assert "HyRISE" in module_help.stdout

    script_help = subprocess.run(
        ["hyrise", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert script_help.returncode == 0
    assert "HyRISE" in script_help.stdout


def test_process_smoke_creates_mqc_outputs(tmp_path):
    input_jsons = sorted(
        (REPO_ROOT / "example_data" / "public").glob("*_NGS_results.json")
    )
    assert input_jsons

    out_dir = tmp_path / "process-out"
    result = subprocess.run(
        [
            "hyrise",
            "process",
            *[str(path) for path in input_jsons],
            "-o",
            str(out_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert any(out_dir.glob("*_mqc.json"))
    assert any(out_dir.glob("*_mqc.html"))
