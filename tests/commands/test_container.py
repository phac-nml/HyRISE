import pytest
import argparse
from types import SimpleNamespace
import hyrise.commands.container as container_module


def test_add_container_subparser_sets_func():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    container_module.add_container_subparser(subparsers)
    # Parsing without required func should not error
    args = parser.parse_args(["container"])
    assert hasattr(args, "func")
    assert args.func == container_module.run_container_command


def test_run_container_command_no_def(monkeypatch, caplog):
    # Simulate missing definition file
    monkeypatch.setattr(container_module, "get_def_file_path", lambda: None)
    args = SimpleNamespace(
        def_file=None,
        extract_def=None,
        singularity=None,
        sudo=False,
        force=False,
        build_elsewhere=False,
        verbose=False,
        output="hyrise.sif",
    )
    caplog.set_level("ERROR")
    result = container_module.run_container_command(args)
    assert result == 1
    assert "Could not find the HyRISE definition file" in caplog.text


def test_extract_def_success(monkeypatch):
    # Simulate extracting definition file successfully
    monkeypatch.setattr(
        container_module, "get_def_file_path", lambda: "/path/to/def.def"
    )
    monkeypatch.setattr(
        container_module,
        "copy_def_file_to_directory",
        lambda dest, src: "/dest/def.def",
    )
    args = SimpleNamespace(
        def_file=None,
        extract_def="some/dir",
        singularity=None,
        sudo=False,
        force=False,
        build_elsewhere=False,
        verbose=False,
        output="hyrise.sif",
    )
    result = container_module.run_container_command(args)
    assert result == 0


def test_extract_def_failure(monkeypatch):
    # Simulate failure extracting definition file
    monkeypatch.setattr(
        container_module, "get_def_file_path", lambda: "/path/to/def.def"
    )
    monkeypatch.setattr(
        container_module, "copy_def_file_to_directory", lambda dest, src: None
    )
    args = SimpleNamespace(
        def_file=None,
        extract_def="some/dir",
        singularity=None,
        sudo=False,
        force=False,
        build_elsewhere=False,
        verbose=False,
        output="hyrise.sif",
    )
    result = container_module.run_container_command(args)
    assert result == 1


def test_build_elsewhere_success_and_verify(monkeypatch):
    # Simulate successful build elsewhere and verification
    monkeypatch.setattr(
        container_module, "get_def_file_path", lambda: "/path/to/def.def"
    )
    monkeypatch.setattr(
        container_module, "find_singularity_binary", lambda: "/usr/bin/singularity"
    )
    monkeypatch.setattr(
        container_module,
        "build_container",
        lambda def_file, output, singularity, sudo, force: True,
    )
    monkeypatch.setattr(
        container_module, "verify_container", lambda output, singularity: True
    )
    args = SimpleNamespace(
        def_file=None,
        extract_def=None,
        singularity=None,
        sudo=True,
        force=True,
        build_elsewhere=True,
        verbose=True,
        output="out.sif",
    )
    result = container_module.run_container_command(args)
    assert result == 0


def test_build_elsewhere_build_failure(monkeypatch):
    # Simulate build failure
    monkeypatch.setattr(
        container_module, "get_def_file_path", lambda: "/path/to/def.def"
    )
    monkeypatch.setattr(
        container_module, "find_singularity_binary", lambda: "/usr/bin/singularity"
    )
    monkeypatch.setattr(
        container_module,
        "build_container",
        lambda def_file, output, singularity, sudo, force: False,
    )
    args = SimpleNamespace(
        def_file=None,
        extract_def=None,
        singularity=None,
        sudo=False,
        force=False,
        build_elsewhere=True,
        verbose=False,
        output="out.sif",
    )
    result = container_module.run_container_command(args)
    assert result == 1


def test_build_elsewhere_verify_failure(monkeypatch):
    # Simulate verification failure after successful build
    monkeypatch.setattr(
        container_module, "get_def_file_path", lambda: "/path/to/def.def"
    )
    monkeypatch.setattr(
        container_module, "find_singularity_binary", lambda: "/usr/bin/singularity"
    )
    monkeypatch.setattr(
        container_module,
        "build_container",
        lambda def_file, output, singularity, sudo, force: True,
    )
    monkeypatch.setattr(
        container_module, "verify_container", lambda output, singularity: False
    )
    args = SimpleNamespace(
        def_file=None,
        extract_def=None,
        singularity=None,
        sudo=False,
        force=False,
        build_elsewhere=True,
        verbose=False,
        output="out.sif",
    )
    result = container_module.run_container_command(args)
    assert result == 1


def test_build_in_def_directory_success(monkeypatch):
    # Simulate building in definition directory and verification success
    monkeypatch.setattr(
        container_module, "get_def_file_path", lambda: "/path/to/def.def"
    )
    monkeypatch.setattr(
        container_module, "find_singularity_binary", lambda: "/usr/bin/singularity"
    )
    monkeypatch.setattr(
        container_module,
        "build_container_in_def_directory",
        lambda def_file, output_name, singularity_path, sudo, force: (
            True,
            "/path/to/def/hyrise.sif",
        ),
    )
    monkeypatch.setattr(
        container_module, "verify_container", lambda output, singularity: True
    )
    args = SimpleNamespace(
        def_file=None,
        extract_def=None,
        singularity=None,
        sudo=False,
        force=False,
        build_elsewhere=False,
        verbose=False,
        output="hyrise.sif",
    )
    result = container_module.run_container_command(args)
    assert result == 0


def test_build_in_def_directory_build_failure(monkeypatch):
    # Simulate build failure in definition directory
    monkeypatch.setattr(
        container_module, "get_def_file_path", lambda: "/path/to/def.def"
    )
    monkeypatch.setattr(
        container_module, "find_singularity_binary", lambda: "/usr/bin/singularity"
    )
    monkeypatch.setattr(
        container_module,
        "build_container_in_def_directory",
        lambda def_file, output_name, singularity_path, sudo, force: (False, None),
    )
    args = SimpleNamespace(
        def_file=None,
        extract_def=None,
        singularity=None,
        sudo=False,
        force=False,
        build_elsewhere=False,
        verbose=False,
        output="hyrise.sif",
    )
    result = container_module.run_container_command(args)
    assert result == 1
