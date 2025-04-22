import pytest
import argparse
from hyrise.utils.common_args import (
    add_container_arguments,
    add_report_arguments,
    add_visualization_arguments,
)


def test_add_container_arguments_mutually_exclusive():
    parser = argparse.ArgumentParser()
    add_container_arguments(parser)
    # Collect container group args
    args = parser.parse_args([])
    # By default, neither flag
    assert not getattr(args, "container", False)
    assert not getattr(args, "no_container", False)

    # --container only
    args = parser.parse_args(["--container"])
    assert args.container is True
    assert args.no_container is False

    # --no-container only
    args = parser.parse_args(["--no-container"])
    assert args.container is False
    assert args.no_container is True

    # Both flags should error
    with pytest.raises(SystemExit):
        parser.parse_args(["--container", "--no-container"])

    # Test container-path
    path = "/tmp/container.sif"
    args = parser.parse_args(["--container-path", path])
    assert args.container_path == path


def test_add_report_arguments_flags():
    parser = argparse.ArgumentParser()
    add_report_arguments(parser)
    # Default
    args = parser.parse_args([])
    assert not getattr(args, "report", False)
    assert not getattr(args, "run_multiqc", False)

    # --report
    args = parser.parse_args(["--report"])
    assert args.report is True
    assert args.run_multiqc is False

    # --run-multiqc
    args = parser.parse_args(["--run-multiqc"])
    assert args.report is False
    assert args.run_multiqc is True

    # Both flags together
    args = parser.parse_args(["--report", "--run-multiqc"])
    assert args.report is True
    assert args.run_multiqc is True


def test_add_visualization_arguments_all_flags():
    parser = argparse.ArgumentParser()
    add_visualization_arguments(parser)
    # Default
    args = parser.parse_args([])
    assert not getattr(args, "guide", False)
    assert not getattr(args, "sample_info", False)
    assert getattr(args, "contact_email", None) is None
    assert getattr(args, "logo", None) is None

    # Provide all flags
    email = "user@example.com"
    logo = "path/to/logo.svg"
    args = parser.parse_args(
        ["--guide", "--sample-info", "--email", email, "--logo", logo]
    )
    assert args.guide is True
    assert args.sample_info is True
    assert args.contact_email == email
    assert args.logo == logo
