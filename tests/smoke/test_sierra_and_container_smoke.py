import subprocess
from types import SimpleNamespace

import hyrise.commands.container as container_module
import hyrise.commands.sierra as sierra_module


def test_sierra_smoke_native_stubbed(monkeypatch, tmp_path):
    fasta = tmp_path / "sample.fasta"
    fasta.write_text(">seq\nATGCATGCATGC\n")
    output = tmp_path / "sample_results.json"
    captured = {}

    monkeypatch.setattr(
        sierra_module,
        "ensure_dependencies",
        lambda **kwargs: {"use_container": False, "sierra_local_available": True},
    )

    def fake_run(cmd_parts, check):
        captured["cmd"] = cmd_parts
        output.write_text("[]")
        return subprocess.CompletedProcess(args=cmd_parts, returncode=0)

    monkeypatch.setattr(sierra_module.subprocess, "run", fake_run)

    result = sierra_module.run_sierra_local([str(fasta)], output=str(output))
    assert result["success"] is True
    assert result["output_path"] == str(output)
    assert captured["cmd"][0] == "sierralocal"
    assert "-alignment" in captured["cmd"]


def test_container_pull_command_deterministic(monkeypatch, tmp_path):
    out_path = tmp_path / "hyrise.sif"
    captured = {}

    monkeypatch.setattr(
        container_module, "find_singularity_binary", lambda: "/usr/bin/apptainer"
    )

    def fake_pull(image_ref, output_path, singularity_path=None, force=False):
        captured["image_ref"] = image_ref
        captured["output_path"] = output_path
        captured["runtime"] = singularity_path
        captured["force"] = force
        out_path.write_text("fake")
        return True

    monkeypatch.setattr(container_module, "pull_container_image", fake_pull)
    monkeypatch.setattr(
        container_module, "verify_container", lambda *_args, **_kwargs: True
    )

    args = SimpleNamespace(
        pull=True,
        image="ghcr.io/phac-nml/hyrise:test",
        output=str(out_path),
        singularity=None,
        force=False,
        verbose=False,
        interactive=False,
    )

    exit_code = container_module.run_container_command(args)
    assert exit_code == 0
    assert captured["image_ref"] == "ghcr.io/phac-nml/hyrise:test"
    assert captured["output_path"] == str(out_path.resolve())
    assert captured["runtime"] == "/usr/bin/apptainer"
