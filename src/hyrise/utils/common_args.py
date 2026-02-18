"""
Common CLI arguments for HyRISE
This module provides functions to add common arguments to CLI parsers,
reducing duplication between different command interfaces.
"""


def add_container_arguments(parser):
    """
    Add container-related arguments to a parser.

    Args:
        parser: ArgumentParser or argument group object
    """
    container_group = parser.add_argument_group("Container options")
    container_exclusive = container_group.add_mutually_exclusive_group()

    container_exclusive.add_argument(
        "--container",
        action="store_true",
        help="Force using an Apptainer/Singularity container for execution",
    )

    container_exclusive.add_argument(
        "--no-container",
        action="store_true",
        help="Force native execution, do not use container even if dependencies are missing",
    )

    container_group.add_argument(
        "--container-path",
        help="Custom path to the container image (default: auto-detect)",
    )

    container_group.add_argument(
        "--container-runtime",
        choices=["apptainer", "singularity"],
        help=(
            "Preferred container runtime binary (default: auto-detect, preferring "
            "apptainer over singularity)"
        ),
    )


def add_config_argument(parser):
    """Add a global config path argument to a parser."""
    parser.add_argument(
        "--config",
        help="Path to HyRISE config TOML file (default: ~/.config/hyrise/config.toml)",
    )


def add_report_arguments(parser):
    """
    Add report generation arguments to a parser.

    Args:
        parser: ArgumentParser or argument group object
    """
    parser.add_argument(
        "-r",
        "--report",
        action="store_true",
        help="Generate MultiQC config file for report creation",
    )

    parser.add_argument(
        "--run-multiqc",
        action="store_true",
        help="Run MultiQC to generate the final report (requires MultiQC to be installed)",
    )


def add_visualization_arguments(parser):
    """
    Add visualization customization arguments to a parser.

    Args:
        parser: ArgumentParser or argument group object
    """
    parser.add_argument(
        "--guide",
        action="store_true",
        help="Creates guide tables for understanding resistance scores and mutations",
    )

    parser.add_argument(
        "--sample-info",
        action="store_true",
        help="Include sample information in the report",
    )

    parser.add_argument(
        "-e",
        "--email",
        metavar="EMAIL",
        dest="contact_email",
        type=str,
        help="Contact e‑mail to include in the report header (optional)",
    )

    parser.add_argument("-l", "--logo", help="Path to custom logo file (PNG or SVG)")


def add_interactive_arguments(parser):
    """
    Add interactive mode arguments to a parser.

    Args:
        parser: ArgumentParser or argument group object
    """
    parser.add_argument(
        "-I",
        "--interactive",
        action="store_true",
        help="Run in interactive mode with guided prompts",
    )
