import subprocess

import pytest

import hyrise.utils.container_utils as cu


def test_check_command_available_uses_shutil_which(monkeypatch):
    monkeypatch.setattr(
        cu.shutil, "which", lambda cmd: "/usr/bin/tool" if cmd == "tool" else None
    )
    assert cu.check_command_available("tool") is True
    assert cu.check_command_available("missing") is False


def test_detect_container_runtime_prefers_requested(monkeypatch):
    monkeypatch.setattr(
        cu.shutil,
        "which",
        lambda name: "/usr/bin/singularity" if name == "singularity" else None,
    )
    runtime, path = cu.detect_container_runtime(preferred_runtime="singularity")
    assert runtime == "singularity"
    assert path == "/usr/bin/singularity"


def test_detect_container_runtime_fallback_order(monkeypatch):
    monkeypatch.setattr(
        cu.shutil,
        "which",
        lambda name: "/usr/bin/apptainer" if name == "apptainer" else None,
    )
    runtime, path = cu.detect_container_runtime()
    assert runtime == "apptainer"
    assert path == "/usr/bin/apptainer"


def test_find_singularity_container_uses_search_paths(tmp_path):
    first = tmp_path / "missing.sif"
    second = tmp_path / "hyrise.sif"
    second.write_text("ok")
    found = cu.find_singularity_container([str(first), str(second)])
    assert found == str(second.resolve())


def test_run_with_singularity_builds_argv_command(tmp_path, monkeypatch):
    container = tmp_path / "hyrise.sif"
    container.write_text("data")
    captured = {}

    monkeypatch.setattr(cu, "verify_container", lambda *_args, **_kwargs: True)

    def fake_run(cmd, check):
        captured["cmd"] = cmd
        assert check is True
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    monkeypatch.setattr(cu.subprocess, "run", fake_run)

    result = cu.run_with_singularity(
        container_path=str(container),
        command=["sierralocal", "-o", "out.json", "input.fasta"],
        bind_paths=[str(tmp_path)],
        runtime_path="/usr/bin/apptainer",
    )

    assert result.returncode == 0
    assert captured["cmd"][0] == "/usr/bin/apptainer"
    assert captured["cmd"][1] == "exec"
    assert str(container) in captured["cmd"]
    assert "sierralocal" in captured["cmd"]


def test_run_with_singularity_errors_without_runtime(tmp_path, monkeypatch):
    container = tmp_path / "hyrise.sif"
    container.write_text("data")
    monkeypatch.setattr(
        cu, "detect_container_runtime", lambda preferred_runtime=None: (None, None)
    )
    with pytest.raises(ValueError, match="No supported container runtime found"):
        cu.run_with_singularity(str(container), ["echo", "hello"])


def test_ensure_dependencies_scopes_required_tools(tmp_path, monkeypatch):
    container = tmp_path / "hyrise.sif"
    container.write_text("image")

    monkeypatch.setattr(
        cu,
        "check_command_available",
        lambda cmd: {"multiqc": False, "sierralocal": True}.get(cmd, False),
    )
    monkeypatch.setattr(
        cu,
        "detect_container_runtime",
        lambda preferred_runtime=None: ("apptainer", "/usr/bin/apptainer"),
    )
    monkeypatch.setattr(
        cu, "find_singularity_container", lambda search_paths=None: str(container)
    )

    deps = cu.ensure_dependencies(
        required_tools=["multiqc"],
        use_container=None,
        container_runtime="apptainer",
    )

    assert deps["runtime_name"] == "apptainer"
    assert deps["container_path"] == str(container)
    assert deps["multiqc_available"] is False
    assert deps["sierra_local_available"] is True
    assert deps["missing_dependencies"] == ["multiqc"]
    assert deps["use_container"] is True
