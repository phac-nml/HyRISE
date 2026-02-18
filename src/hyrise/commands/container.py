#!/usr/bin/env python3
"""
HyRISE Container Builder CLI Integration

This module integrates the container builder functionality into the HyRISE CLI.
It provides the command to build the Singularity container for HyRISE.
"""

import os
import sys
import argparse
import logging
from hyrise.utils.container_builder import (
    find_singularity_binary,
    get_def_file_path,
    get_dockerfile_path,
    copy_def_file_to_directory,
    copy_file_to_directory,
    build_container,
    pull_container_image,
    verify_container,
    build_container_in_def_directory,
)
from hyrise.utils.common_args import add_interactive_arguments

# Try to import Questionary for interactive UI
try:
    import questionary
    from questionary import Style

    QUESTIONARY_AVAILABLE = True

    # Define custom style
    CUSTOM_STYLE = Style(
        [
            ("question", "bold cyan"),
            ("answer", "bold green"),
            ("pointer", "bold cyan"),
            ("highlighted", "bold green"),
            ("selected", "bold green"),
        ]
    )
except ImportError:
    QUESTIONARY_AVAILABLE = False
    CUSTOM_STYLE = None


def add_container_subparser(subparsers):
    """
    Add the container building command to the CLI.

    Args:
        subparsers: Subparsers object to add the container parser to
    """
    # Create the container parser
    container_parser = subparsers.add_parser(
        "container",
        help="Manage HyRISE container images",
        description=(
            "Pull prebuilt HyRISE containers for HPC use, or build from a local "
            "definition file."
        ),
    )

    # Add options
    container_parser.add_argument(
        "--output",
        "-o",
        default="hyrise.sif",
        help="Output file path for the container image (default: hyrise.sif)",
    )
    container_parser.add_argument(
        "--pull",
        action="store_true",
        help="Pull prebuilt OCI image instead of building from definition file",
    )
    container_parser.add_argument(
        "--image",
        default="ghcr.io/phac-nml/hyrise:latest",
        help=(
            "OCI image reference for --pull mode "
            "(default: ghcr.io/phac-nml/hyrise:latest)"
        ),
    )
    container_parser.add_argument(
        "--def-file",
        help="Path to the HyRISE definition file (default: auto-detect)",
    )
    container_parser.add_argument(
        "--extract-def",
        help="Extract the definition file to the specified directory without building",
        metavar="DIRECTORY",
    )
    container_parser.add_argument(
        "--extract-dockerfile",
        help=(
            "Extract a standalone runtime Dockerfile to the specified directory "
            "(works with pip-installed HyRISE, no repo clone required)"
        ),
        metavar="DIRECTORY",
    )
    container_parser.add_argument(
        "--singularity",
        help="Path to the Singularity or Apptainer binary (default: auto-detect)",
    )
    container_parser.add_argument(
        "--sudo",
        action="store_true",
        help="Use sudo when building the container (may be required on some systems)",
    )
    container_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force rebuild even if the container already exists",
    )
    container_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    container_parser.add_argument(
        "--build-elsewhere",
        action="store_true",
        help="Build the container at the specified output path instead of in the same directory as the definition file",
    )

    # Add interactive mode argument
    add_interactive_arguments(container_parser)

    # Set the function to be called when this subcommand is used
    container_parser.set_defaults(func=run_container_command)


def run_container_command(args):
    """
    Run the container building command.

    Args:
        args: Parsed command-line arguments

    Returns:
        int: Exit code (0 for success, non-zero for errors)
    """
    # Check if interactive mode is requested
    if getattr(args, "interactive", False):
        return run_interactive_container()

    # Set up logging
    log_level = logging.DEBUG if getattr(args, "verbose", False) else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("hyrise-container")

    if getattr(args, "pull", False):
        singularity_path = (
            getattr(args, "singularity", None) or find_singularity_binary()
        )
        if not singularity_path:
            logger.error(
                "Could not find Singularity or Apptainer on your system. "
                "Please install it or specify the path with --singularity."
            )
            return 1

        output_path = os.path.abspath(getattr(args, "output", "hyrise.sif"))
        pull_success = pull_container_image(
            image_ref=getattr(args, "image", "ghcr.io/phac-nml/hyrise:latest"),
            output_path=output_path,
            singularity_path=singularity_path,
            force=getattr(args, "force", False),
        )
        if not pull_success:
            logger.error("Container pull failed. Check the logs for details.")
            return 1
        verify_success = verify_container(output_path, singularity_path)
        if verify_success:
            logger.info(f"Container pulled and verified at: {output_path}")
            return 0
        logger.warning("Container pulled, but verification failed.")
        return 1

    extract_def_dir = getattr(args, "extract_def", None)
    extract_dockerfile_dir = getattr(args, "extract_dockerfile", None)
    if extract_def_dir or extract_dockerfile_dir:
        extraction_success = True

        if extract_def_dir:
            def_file_path = getattr(args, "def_file", None) or get_def_file_path()
            if not def_file_path:
                logger.error(
                    "Could not find the HyRISE definition file. "
                    "Please specify with --def-file."
                )
                extraction_success = False
            else:
                extract_path = os.path.abspath(extract_def_dir)
                copied_path = copy_def_file_to_directory(extract_path, def_file_path)
                if copied_path:
                    logger.info(f"Definition file extracted to: {copied_path}")
                else:
                    logger.error("Failed to extract definition file.")
                    extraction_success = False

        if extract_dockerfile_dir:
            dockerfile_path = get_dockerfile_path()
            if not dockerfile_path:
                logger.error("Could not find a packaged HyRISE Dockerfile to extract.")
                extraction_success = False
            else:
                extract_path = os.path.abspath(extract_dockerfile_dir)
                copied_path = copy_file_to_directory(
                    extract_path, dockerfile_path, output_name="Dockerfile"
                )
                if copied_path:
                    logger.info(f"Dockerfile extracted to: {copied_path}")
                else:
                    logger.error("Failed to extract Dockerfile.")
                    extraction_success = False

        return 0 if extraction_success else 1

    # Find the definition file
    def_file_path = getattr(args, "def_file", None) or get_def_file_path()
    if not def_file_path:
        logger.error(
            "Could not find the HyRISE definition file. Please specify with --def-file."
        )
        return 1

    logger.info(f"Using definition file: {def_file_path}")

    # Find the Singularity binary for local builds
    singularity_path = getattr(args, "singularity", None) or find_singularity_binary()
    if not singularity_path:
        logger.error(
            "Could not find Singularity or Apptainer on your system. "
            "Please install it or specify the path with --singularity."
        )
        return 1

    # Determine where to build the container
    # By default, build in the same directory as the def file
    # unless --build-elsewhere flag is specified
    if getattr(args, "build_elsewhere", False):
        # Use the provided output path
        output_path = os.path.abspath(getattr(args, "output", "hyrise.sif"))

        # Build the container at the specified location
        build_success = build_container(
            def_file_path,
            output_path,
            singularity_path,
            sudo=getattr(args, "sudo", False),
            force=getattr(args, "force", False),
        )
    else:
        # Build in the same directory as the def file
        build_success, output_path = build_container_in_def_directory(
            def_file_path,
            output_name=(
                os.path.basename(getattr(args, "output", "hyrise.sif"))
                if getattr(args, "output", "hyrise.sif") != "hyrise.sif"
                else None
            ),
            singularity_path=singularity_path,
            sudo=getattr(args, "sudo", False),
            force=getattr(args, "force", False),
        )

    if not build_success:
        logger.error("Container build failed. Check the logs for details.")
        return 1

    # Verify the container
    verify_success = verify_container(output_path, singularity_path)

    if verify_success:
        logger.info(f"Container successfully built and verified at: {output_path}")
        logger.info("You can now use the container with commands like:")
        logger.info(f"  {singularity_path} exec {output_path} multiqc --help")
        logger.info(f"  {singularity_path} exec {output_path} sierralocal --help")
        return 0
    else:
        logger.warning(
            f"Container was built but verification failed. "
            f"The container may still work, but proceed with caution."
        )
        return 1


def run_interactive_container():
    """
    Run container building interactively with questionary prompts.

    Returns:
        int: Exit code (0 for success, non-zero for errors)
    """
    if not QUESTIONARY_AVAILABLE:
        print("Error: Interactive mode requires the 'questionary' package.")
        print("Please install it with: pip install questionary")
        return 1

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("hyrise-container")

    print("\n=== HyRISE Container Builder (Interactive Mode) ===\n")
    logger.info("Container command tips:")
    logger.info(
        "  Pull prebuilt image: hyrise container --pull -o hyrise.sif --image ghcr.io/phac-nml/hyrise:latest"
    )
    logger.info("  Extract definition file: hyrise container --extract-def <directory>")
    logger.info(
        "  Extract runtime Dockerfile: hyrise container --extract-dockerfile <directory>"
    )

    # Find the definition file
    def_file_path = get_def_file_path()
    if def_file_path:
        logger.info(f"Found definition file: {def_file_path}")
        use_default_def = questionary.confirm(
            "Use the detected definition file?", default=True, style=CUSTOM_STYLE
        ).ask()

        if not use_default_def:
            def_file_path = questionary.path(
                "Path to definition file:",
                style=CUSTOM_STYLE,
                validate=lambda x: os.path.isfile(x) or "File doesn't exist",
            ).ask()
    else:
        logger.warning("Could not find the default HyRISE definition file.")
        def_file_path = questionary.path(
            "Path to definition file:",
            style=CUSTOM_STYLE,
            validate=lambda x: os.path.isfile(x) or "File doesn't exist",
        ).ask()

    if not def_file_path:
        logger.error("Definition file is required.")
        return 1

    # Find the Singularity binary
    singularity_path = find_singularity_binary()
    if not singularity_path:
        logger.error(
            "Could not find Singularity or Apptainer on your system. "
            "Please install it before building the container."
        )
        return 1

    logger.info(f"Using Singularity/Apptainer: {singularity_path}")

    # Ask for output path
    default_output = "hyrise.sif"
    output_path = questionary.text(
        "Output file name:", default=default_output, style=CUSTOM_STYLE
    ).ask()

    # Ask for sudo usage
    sudo = questionary.confirm(
        "Use sudo when building the container? (required on some systems)",
        default=False,
        style=CUSTOM_STYLE,
    ).ask()

    # Ask for force rebuild
    force = questionary.confirm(
        "Force rebuild even if the container already exists?",
        default=True,
        style=CUSTOM_STYLE,
    ).ask()

    # Ask where to build
    build_elsewhere = questionary.confirm(
        "Build the container at the specified output path? (otherwise builds in the same directory as definition file)",
        default=False,
        style=CUSTOM_STYLE,
    ).ask()

    # Confirm build
    logger.info("\nContainer build configuration:")
    logger.info(f"Definition file: {def_file_path}")
    logger.info(f"Output file: {output_path}")
    logger.info(f"Use sudo: {sudo}")
    logger.info(f"Force rebuild: {force}")
    logger.info(f"Build at output path: {build_elsewhere}")

    proceed = questionary.confirm(
        "Proceed with container build?", default=True, style=CUSTOM_STYLE
    ).ask()

    if not proceed:
        logger.info("Container build cancelled.")
        return 0

    # Build the container
    logger.info("Building container...")

    if build_elsewhere:
        output_path_abs = os.path.abspath(output_path)
        build_success = build_container(
            def_file_path,
            output_path_abs,
            singularity_path,
            sudo=sudo,
            force=force,
        )
        final_output_path = output_path_abs
    else:
        build_success, final_output_path = build_container_in_def_directory(
            def_file_path,
            output_name=(
                os.path.basename(output_path) if output_path != "hyrise.sif" else None
            ),
            singularity_path=singularity_path,
            sudo=sudo,
            force=force,
        )

    if not build_success:
        logger.error("Container build failed. Check the logs for details.")
        return 1

    # Verify the container
    logger.info("Verifying container...")
    verify_success = verify_container(final_output_path, singularity_path)

    if verify_success:
        logger.info(
            f"Container successfully built and verified at: {final_output_path}"
        )
        logger.info("\nYou can now use the container with commands like:")
        logger.info(f"  {singularity_path} exec {final_output_path} multiqc --help")
        logger.info(f"  {singularity_path} exec {final_output_path} sierralocal --help")
        logger.info(
            f"  hyrise process --container --container-path {final_output_path} ..."
        )
        return 0
    else:
        logger.warning(
            f"Container was built but verification failed. "
            f"The container may still work, but proceed with caution."
        )
        return 1


def main():
    """
    Main entry point for the standalone container builder command.
    """
    parser = argparse.ArgumentParser(description="HyRISE Container Builder")
    parser.add_argument(
        "--output",
        "-o",
        default="hyrise.sif",
        help="Output file path for the container image (default: hyrise.sif)",
    )
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Pull prebuilt OCI image instead of building from definition file",
    )
    parser.add_argument(
        "--image",
        default="ghcr.io/phac-nml/hyrise:latest",
        help="OCI image reference for --pull mode",
    )
    parser.add_argument(
        "--def-file",
        help="Path to the HyRISE definition file (default: auto-detect)",
    )
    parser.add_argument(
        "--extract-def",
        help="Extract the definition file to the specified directory without building",
        metavar="DIRECTORY",
    )
    parser.add_argument(
        "--singularity",
        help="Path to the Singularity or Apptainer binary (default: auto-detect)",
    )
    parser.add_argument(
        "--sudo",
        action="store_true",
        help="Use sudo when building the container (may be required on some systems)",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force rebuild even if the container already exists",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--build-elsewhere",
        action="store_true",
        help="Build the container at the specified output path instead of in the same directory as the definition file",
    )

    # Add interactive mode
    add_interactive_arguments(parser)

    args = parser.parse_args()

    # Check if interactive mode is requested
    if args.interactive:
        return run_interactive_container()

    return run_container_command(args)


if __name__ == "__main__":
    sys.exit(main())
