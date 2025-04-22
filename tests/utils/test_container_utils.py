import os
import subprocess
import importlib.util
import pkg_resources
import site
import sys
import pytest
from types import SimpleNamespace

import hyrise.utils.container_utils as cu


# Tests for check_dependency_installed
def test_check_dependency_installed_existing():
    # sys is always installed
    assert cu.check_dependency_installed("sys") is True


def test_check_dependency_installed_nonexistent(monkeypatch):
    # Simulate find_spec returns None and pkg_resources raises
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    monkeypatch.setattr(
        pkg_resources,
        "get_distribution",
        lambda name: (_ for _ in ()).throw(pkg_resources.DistributionNotFound()),
    )
    assert cu.check_dependency_installed("fakepkg") is False


# Tests for check_command_available
def test_check_command_available_success(monkeypatch):
    # Simulate which success
    dummy = subprocess.CompletedProcess(args=["which", "cmd"], returncode=0)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: dummy)
    assert cu.check_command_available("cmd") is True


def test_check_command_available_failure(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, "cmd")
        ),
    )
    assert cu.check_command_available("cmd") is False


# Tests for find_singularity_container
def test_find_singularity_container_cwd(tmp_path, monkeypatch):
    # In cwd
    cwd = tmp_path
    monkeypatch.chdir(cwd)
    # Create hyrise.sif
    file = cwd / "hyrise.sif"
    file.write_text("")
    path = cu.find_singularity_container()
    assert path == str(file)


# Tests for check_singularity_available
def test_check_singularity_available(monkeypatch):
    monkeypatch.setattr(cu, "find_singularity_binary", lambda: "/bin/sing")
    assert cu.check_singularity_available() is True
    monkeypatch.setattr(cu, "find_singularity_binary", lambda: None)
    assert cu.check_singularity_available() is False


# Tests for run_with_singularity
def test_run_with_singularity_success(tmp_path, monkeypatch):
    # Create dummy container file
    cont = tmp_path / "hyrise.sif"
    cont.write_text("")
    # Stub find_singularity_binary and verify_container
    monkeypatch.setattr(cu, "find_singularity_binary", lambda: "/bin/sing")
    monkeypatch.setattr(cu, "verify_container", lambda path, sing: True)
    # Stub subprocess.run
    cp = subprocess.CompletedProcess(args=[], returncode=0)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: cp)
    result = cu.run_with_singularity(
        str(cont), "echo hello", bind_paths=[str(tmp_path)]
    )
    assert isinstance(result, subprocess.CompletedProcess)


def test_run_with_singularity_no_singularity(monkeypatch, tmp_path):
    cont = tmp_path / "hyrise.sif"
    cont.write_text("")
    monkeypatch.setattr(cu, "find_singularity_binary", lambda: None)
    with pytest.raises(ValueError):
        cu.run_with_singularity(str(cont), "cmd")


def test_run_with_singularity_no_container(monkeypatch):
    monkeypatch.setattr(cu, "find_singularity_binary", lambda: "/bin/sing")
    with pytest.raises(ValueError):
        cu.run_with_singularity("no.sif", "cmd")


# Tests for ensure_dependencies
def test_ensure_dependencies_auto(monkeypatch):
    # Simulate commands missing
    monkeypatch.setattr(cu, "check_command_available", lambda cmd: cmd == "multiqc")
    monkeypatch.setattr(cu, "check_singularity_available", lambda: True)
    monkeypatch.setattr(cu, "find_singularity_container", lambda: "/path/to/cont")
    res = cu.ensure_dependencies(use_container=None)
    # multiqc available, sierralocal missing
    assert res["multiqc_available"] is True
    assert res["sierra_local_available"] is False
    assert "sierralocal" in res["missing_dependencies"]
    # Container should be used because missing dependencies and singularity available
    assert res["use_container"] is True


def test_ensure_dependencies_forced_true(monkeypatch):
    monkeypatch.setattr(cu, "check_command_available", lambda cmd: True)
    res = cu.ensure_dependencies(use_container=True)
    assert res["use_container"] is True


def test_ensure_dependencies_forced_false(monkeypatch):
    monkeypatch.setattr(cu, "check_command_available", lambda cmd: True)
    res = cu.ensure_dependencies(use_container=False)
    assert res["use_container"] is False
