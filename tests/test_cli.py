import sys
import os
import logging
from types import SimpleNamespace

import pytest

import hyrise.cli as cli


def test_main_no_args_prints_help(monkeypatch, capsys):
    # Simulate running "hyrise" with no subcommand
    monkeypatch.setattr(sys, "argv", ["hyrise"])
    code = cli.main()
    captured = capsys.readouterr()
    assert code == 0
    assert (
        "HyRISE: HIV Resistance Interpretation and Visualization System" in captured.out
    )


def test_main_version_exits_zero(monkeypatch):
    # --version invokes argparse version action and raises SystemExit(0)
    monkeypatch.setattr(sys, "argv", ["hyrise", "--version"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0


def test_main_invalid_command_raises_error(monkeypatch, capsys):
    # Provide an unknown command -> argparse will exit with code 2
    monkeypatch.setattr(sys, "argv", ["hyrise", "no-such-cmd"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "invalid choice: 'no-such-cmd'" in err
    assert "usage: hyrise" in err


def make_args(**kwargs):
    defaults = {
        "container": False,
        "no_container": False,
        "container_path": None,
        "input": "in.json",
        "output_dir": "out",
        "sample_name": "SAMPLE",
        "report": False,
        "run_multiqc": False,
        "guide": None,
        "sample_info": None,
        "contact_email": None,
        "logo": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_run_process_container_path_not_found(monkeypatch, caplog):
    # If custom container path doesn’t exist, should log an error
    caplog.set_level(logging.ERROR)
    args = make_args(container_path="/does/not/exist")
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    code = cli.run_process_command(args)
    assert code == 1
    assert "Error: Specified container not found at /does/not/exist" in caplog.text


def test_run_process_sets_report_when_multiqc(monkeypatch):
    # run_multiqc implies report=True
    args = make_args(container=False, run_multiqc=True, report=False)
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    called = {}

    def fake_process(
        input,
        output_dir,
        sample_name,
        generate_report,
        run_multiqc,
        guide,
        sample_info,
        contact_email,
        logo_path,
        use_container,
        container_path,
    ):
        called.update(locals())
        return {
            "report_dir": "myreport",
            "files_generated": ["a", "b", "c"],
            "container_used": False,
        }

    monkeypatch.setattr(cli, "process_files", fake_process)
    code = cli.run_process_command(args)
    assert code == 0
    assert called["generate_report"] is True
    assert called["run_multiqc"] is True
    assert called["use_container"] is None


def test_run_process_exception(monkeypatch, caplog):
    # Exceptions from process_files should be caught and logged
    caplog.set_level(logging.ERROR)
    args = make_args()
    monkeypatch.setattr(
        cli,
        "process_files",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    code = cli.run_process_command(args)
    assert code == 1
    assert "Error: boom" in caplog.text


@pytest.mark.parametrize(
    "deps, expect_phrases",
    [
        (
            {
                "multiqc_available": True,
                "sierra_local_available": True,
                "singularity_available": True,
                "container_path": "/some/path",
                "missing_dependencies": [],
            },
            ["All dependencies are satisfied. Native execution is possible."],
        ),
        (
            {
                "multiqc_available": False,
                "sierra_local_available": False,
                "singularity_available": True,
                "container_path": "/some/path",
                "missing_dependencies": ["multiqc", "sierra-local"],
            },
            [
                "Missing dependencies: multiqc, sierra-local",
                "Missing dependencies can be handled using the Singularity container.",
                "Use the --container flag to enable container execution.",
            ],
        ),
        (
            {
                "multiqc_available": False,
                "sierra_local_available": False,
                "singularity_available": False,
                "container_path": None,
                "missing_dependencies": ["multiqc"],
            },
            [
                "Missing dependencies: multiqc",
                "Please install missing dependencies or provide a Singularity container.",
                "You can build a container with: hyrise container",
            ],
        ),
    ],
)
def test_run_check_deps_various(monkeypatch, caplog, deps, expect_phrases):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(cli, "ensure_dependencies", lambda: deps)
    code = cli.run_check_deps_command(SimpleNamespace())
    assert code == 0
    text = caplog.text
    for phrase in expect_phrases:
        assert phrase in text
