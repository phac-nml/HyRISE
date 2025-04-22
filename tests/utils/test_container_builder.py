import os
import io
import shutil
import subprocess
from pathlib import Path
import pytest
import pkg_resources

import hyrise.utils.container_builder as cb


def test_find_singularity_binary_not_found(monkeypatch):
    # Neither binary found
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert cb.find_singularity_binary() is None


def test_find_singularity_binary_singularity(monkeypatch):
    # Found singularity, version command succeeds
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: "/usr/bin/singularity" if name == "singularity" else None,
    )
    dummy = subprocess.CompletedProcess(
        args=["singularity", "--version"],
        returncode=0,
        stdout="singularity version 3.8.0",
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: dummy)
    path = cb.find_singularity_binary()
    assert path == "/usr/bin/singularity"


def test_get_def_file_path_resource(monkeypatch, tmp_path):
    # Simulate pkg_resources returns a temp file existing
    def_file = tmp_path / "hyrise.def"
    def_file.write_text("")
    monkeypatch.setattr(
        pkg_resources, "resource_filename", lambda pkg, res: str(def_file)
    )
    # Ensure os.path.exists sees it
    assert cb.get_def_file_path() == str(def_file)


def test_get_def_file_path_cwd(monkeypatch):
    # Simulate resource_filename raises and 'hyrise.def' exists in cwd
    monkeypatch.setattr(
        pkg_resources,
        "resource_filename",
        lambda pkg, res: (_ for _ in ()).throw(pkg_resources.DistributionNotFound()),
    )
    real_exists = os.path.exists
    monkeypatch.setattr(
        os.path, "exists", lambda p: True if p == "hyrise.def" else real_exists(p)
    )
    path = cb.get_def_file_path()
    assert path == os.path.abspath("hyrise.def")


def test_copy_def_file_to_directory_success(tmp_path):
    src = tmp_path / "src.def"
    src.write_text("content")
    dest_dir = tmp_path / "dest"
    result = cb.copy_def_file_to_directory(str(dest_dir), str(src))
    assert result == str(dest_dir / "hyrise.def")
    assert (dest_dir / "hyrise.def").read_text() == "content"


def test_copy_def_file_to_directory_failure(monkeypatch, tmp_path):
    src = tmp_path / "src.def"
    src.write_text("content")
    dest_dir = tmp_path / "dest"
    # Simulate copy2 failure
    monkeypatch.setattr(
        shutil, "copy2", lambda s, d: (_ for _ in ()).throw(IOError("fail"))
    )
    result = cb.copy_def_file_to_directory(str(dest_dir), str(src))
    assert result is None


def test_build_container_in_def_directory_with_binary(monkeypatch, tmp_path):
    # Prepare dummy def file
    def_file = tmp_path / "dir" / "hyrise.def"
    def_file.parent.mkdir()
    def_file.write_text("")
    # Stub build_container
    monkeypatch.setattr(cb, "build_container", lambda *args, **kwargs: True)
    status, out_path = cb.build_container_in_def_directory(
        str(def_file),
        output_name="out.sif",
        singularity_path="/bin/sing",
        sudo=True,
        force=True,
    )
    assert status is True
    assert out_path == os.path.join(str(def_file.parent), "out.sif")


def test_build_container_in_def_directory_no_binary(monkeypatch):
    # Stub find_singularity_binary to return None
    monkeypatch.setattr(cb, "find_singularity_binary", lambda: None)
    status, out = cb.build_container_in_def_directory(
        "nonexistent.def", output_name=None, singularity_path=None
    )
    assert status is False and out is None


def test_build_container_skip_existing(tmp_path, monkeypatch):
    # Create existing output
    output = tmp_path / "out.sif"
    output.write_text("")
    # Call without force
    result = cb.build_container(
        "defs.def", str(output), "/bin/sing", sudo=False, force=False
    )
    assert result is True


def test_build_container_force_and_run(monkeypatch, tmp_path):
    # Force rebuild invokes subprocess
    dummy_stdout = io.StringIO("line1\nline2\n")

    class FakeProc:
        def __init__(self):
            self.stdout = dummy_stdout

        def wait(self):
            return 0

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: FakeProc())
    result = cb.build_container(
        "def.def", "out.sif", "/bin/sing", sudo=True, force=True
    )
    assert result is True


def test_build_container_failure(monkeypatch, tmp_path):
    # Popen returns non-zero
    dummy_stdout = io.StringIO("")

    class FakeProc2:
        def __init__(self):
            self.stdout = dummy_stdout

        def wait(self):
            return 1

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: FakeProc2())
    result = cb.build_container(
        "def.def", "out.sif", "/bin/sing", sudo=False, force=True
    )
    assert result is False


def test_verify_container_not_exist(tmp_path):
    assert cb.verify_container(str(tmp_path / "nofile.sif"), "/bin/sing") is False


def test_verify_container_test_success(monkeypatch, tmp_path):
    # Create dummy container file
    cont = tmp_path / "c.sif"
    cont.write_text("")
    # First run returncode 0
    cp = subprocess.CompletedProcess(args=[], returncode=0)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: cp)
    assert cb.verify_container(str(cont), "/bin/sing") is True


def test_verify_container_test_fail_exec_success(monkeypatch, tmp_path):
    cont = tmp_path / "c.sif"
    cont.write_text("")
    # First run returncode 1, second returncode 0
    calls = {"count": 0}

    def fake_run(cmd, stdout, stderr, text, check=False):
        calls["count"] += 1
        if "test" in cmd:
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="out", stderr="err"
            )
        else:
            return subprocess.CompletedProcess(args=cmd, returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert cb.verify_container(str(cont), "/bin/sing") is True
    assert calls["count"] >= 2


def test_verify_container_both_fail(monkeypatch, tmp_path):
    cont = tmp_path / "c.sif"
    cont.write_text("")

    def fake_run2(cmd, stdout, stderr, text, check=False):
        return subprocess.CompletedProcess(
            args=cmd, returncode=1, stdout="o", stderr="e"
        )

    monkeypatch.setattr(subprocess, "run", fake_run2)
    assert cb.verify_container(str(cont), "/bin/sing") is False


def test_install_container_no_singularity(monkeypatch):
    monkeypatch.setattr(cb, "find_singularity_binary", lambda: None)
    res = cb.install_container()
    assert res["success"] is False
    assert "not installed" in res["error"]


def test_install_container_no_def(monkeypatch):
    monkeypatch.setattr(cb, "find_singularity_binary", lambda: "/bin/sing")
    monkeypatch.setattr(cb, "get_def_file_path", lambda: None)
    res = cb.install_container()
    assert res["success"] is False
    assert "Definition file not found" in res["error"]


def test_install_container_build_and_verify(monkeypatch, tmp_path):
    monkeypatch.setattr(cb, "find_singularity_binary", lambda: "/bin/sing")
    df = tmp_path / "d.def"
    df.write_text("")
    monkeypatch.setattr(cb, "get_def_file_path", lambda: str(df))
    # stub build and verify
    monkeypatch.setattr(
        cb,
        "build_container_in_def_directory",
        lambda df, singularity_path, sudo, force: (True, "out.sif"),
    )
    monkeypatch.setattr(cb, "verify_container", lambda p, s: True)
    res = cb.install_container()
    assert res["success"] is True
    assert res["container_path"] == "out.sif"


def test_install_container_build_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(cb, "find_singularity_binary", lambda: "/bin/sing")
    df = tmp_path / "d.def"
    df.write_text("")
    monkeypatch.setattr(cb, "get_def_file_path", lambda: str(df))
    monkeypatch.setattr(
        cb,
        "build_container_in_def_directory",
        lambda df, singularity_path, sudo, force: (False, None),
    )
    res = cb.install_container()
    assert res["success"] is False
    assert "build failed" in res["error"].lower()
