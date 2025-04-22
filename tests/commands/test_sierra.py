import os
import subprocess
import tempfile
from types import SimpleNamespace
from pathlib import Path
import pytest

import hyrise.commands.sierra as sierra_module


def test_add_sierra_subparser_sets_func():
    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    sierra_module.add_sierra_subparser(subparsers)
    args = parser.parse_args(["sierra", "input.fa"])
    assert hasattr(args, "func")
    assert args.func == sierra_module.run_sierra_command


def test_run_sierra_local_missing_fasta(tmp_path):
    # Non-existent FASTA file
    fasta = str(tmp_path / "no.fa")
    results = sierra_module.run_sierra_local([fasta])
    assert not results["success"]
    assert "FASTA file not found" in results["error"]


def test_run_sierra_local_missing_xml(tmp_path):
    # Create dummy fasta
    fasta = tmp_path / "input.fa"
    fasta.write_text(">seq\nATGC")
    xml = str(tmp_path / "no.xml")
    results = sierra_module.run_sierra_local([str(fasta)], xml=xml)
    assert not results["success"]
    assert "XML file not found" in results["error"]


def test_run_sierra_local_missing_json_file(tmp_path):
    # Create dummy fasta
    fasta = tmp_path / "input.fa"
    fasta.write_text(">seq\nATGC")
    json_file = str(tmp_path / "no.json")
    results = sierra_module.run_sierra_local([str(fasta)], json_file=json_file)
    assert not results["success"]
    assert "JSON file not found" in results["error"]


def test_run_sierra_local_native_success(monkeypatch, tmp_path):
    # Setup dummy fasta and dependencies
    fasta = tmp_path / "input.fa"
    fasta.write_text(">seq\nATGC")
    output = tmp_path / "out.json"
    # Stub dependencies
    monkeypatch.setattr(
        sierra_module,
        "ensure_dependencies",
        lambda c: {"use_container": False, "sierra_local_available": True},
    )
    # Capture the output path for closure
    output_abs = str(output)

    # Stub subprocess.run to create the output file
    def fake_run(cmd_parts, check):
        open(output_abs, "w").close()

    monkeypatch.setattr(subprocess, "run", fake_run)

    results = sierra_module.run_sierra_local([str(fasta)], output=output_abs)
    assert results["success"]
    assert results["output_path"] == output_abs
    assert not results["container_used"]


def test_run_sierra_local_native_dependency_missing(monkeypatch, tmp_path):
    # Setup dummy fasta
    fasta = tmp_path / "input.fa"
    fasta.write_text(">seq\nATGC")
    # Stub dependencies to disable native and container
    monkeypatch.setattr(
        sierra_module,
        "ensure_dependencies",
        lambda c: {"use_container": False, "sierra_local_available": False},
    )
    results = sierra_module.run_sierra_local([str(fasta)])
    assert not results["success"]
    assert "SierraLocal not available and container usage disabled" in results["error"]


def test_run_sierra_local_container_success(monkeypatch, tmp_path):
    # Setup dummy fasta and dependencies
    fasta = tmp_path / "input.fa"
    fasta.write_text(">seq\nATGC")
    output = tmp_path / "out.json"
    # Stub dependencies
    monkeypatch.setattr(
        sierra_module,
        "ensure_dependencies",
        lambda c: {
            "use_container": True,
            "container_path": "/fake/container.sif",
            "sierra_local_available": True,
        },
    )
    # Stub find_singularity_container
    monkeypatch.setattr(
        sierra_module, "find_singularity_container", lambda: "/usr/bin/singularity"
    )

    # Stub subprocess.run to create file in temp directory
    def fake_run(cmd_list, check):
        # temp_dir is cmd_list[3]
        temp_dir = cmd_list[3]
        output_name = os.path.basename(str(output))
        temp_output = os.path.join(temp_dir, output_name)
        open(temp_output, "w").close()

    monkeypatch.setattr(subprocess, "run", fake_run)

    results = sierra_module.run_sierra_local([str(fasta)], output=str(output))
    assert results["success"]
    assert results["container_used"]
    assert results["output_path"] == str(output)


def test_run_sierra_command_error_propagation(monkeypatch, caplog):
    # Stub run_sierra_local to fail
    monkeypatch.setattr(
        sierra_module,
        "run_sierra_local",
        lambda *args, **kwargs: {"success": False, "error": "fail"},
    )
    # Prepare args
    args = SimpleNamespace(
        fasta=["in.fa"],
        output=None,
        xml=None,
        json=None,
        cleanup=False,
        forceupdate=False,
        alignment="post",
        container=None,
        no_container=None,
        process=False,
        run_multiqc=False,
        report=False,
        process_dir=None,
        container_path=None,
        verbose=False,
    )
    caplog.set_level("ERROR")
    result = sierra_module.run_sierra_command(args)
    assert result == 1
    assert "Error: fail" in caplog.text
    assert result == 1
    assert "Error: fail" in caplog.text


def test_run_sierra_command_success_without_process(monkeypatch):
    # Stub run_sierra_local to succeed
    monkeypatch.setattr(
        sierra_module,
        "run_sierra_local",
        lambda *args, **kwargs: {"success": True, "output_path": "path"},
    )
    # Prepare args with no processing
    args = SimpleNamespace(
        fasta=["in.fa"],
        output=None,
        xml=None,
        json=None,
        cleanup=False,
        forceupdate=False,
        alignment="post",
        container=None,
        no_container=None,
        process=False,
        run_multiqc=False,
        report=False,
        process_dir=None,
        container_path=None,
        verbose=False,
    )
    result = sierra_module.run_sierra_command(args)
    assert result == 0
