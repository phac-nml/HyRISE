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
    copy_def_file_to_directory,
    build_container,
    verify_container,
    build_container_in_def_directory,
)


def add_container_subparser(subparsers):
    """
    Add the container building command to the CLI.

    Args:
        subparsers: Subparsers object to add the container parser to
    """
    # Create the container parser
    container_parser = subparsers.add_parser(
        "container",
        help="Build the HyRISE Singularity container",
        description="Build a Singularity/Apptainer container with MultiQC, SierraLocal, and other dependencies for HIV resistance analysis.",
    )

    # Add options
    container_parser.add_argument(
        "--output",
        "-o",
        default="hyrise.sif",
        help="Output file path for the Singularity container (default: hyrise.sif)",
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
    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("hyrise-container")

    # Find the definition file
    def_file_path = args.def_file or get_def_file_path()
    if not def_file_path:
        logger.error(
            "Could not find the HyRISE definition file. Please specify with --def-file."
        )
        return 1

    logger.info(f"Using definition file: {def_file_path}")

    # If just extracting the definition file, do that and exit
    if args.extract_def:
        extract_path = os.path.abspath(args.extract_def)
        copied_path = copy_def_file_to_directory(extract_path, def_file_path)
        if copied_path:
            logger.info(f"Definition file extracted to: {copied_path}")
            return 0
        else:
            logger.error("Failed to extract definition file.")
            return 1

    # Find the Singularity binary
    singularity_path = args.singularity or find_singularity_binary()
    if not singularity_path:
        logger.error(
            "Could not find Singularity or Apptainer on your system. "
            "Please install it or specify the path with --singularity."
        )
        return 1

    # Determine where to build the container
    # By default, build in the same directory as the def file
    # unless --build-elsewhere flag is specified
    if args.build_elsewhere:
        # Use the provided output path
        output_path = os.path.abspath(args.output)

        # Build the container at the specified location
        build_success = build_container(
            def_file_path,
            output_path,
            singularity_path,
            sudo=args.sudo,
            force=args.force,
        )
    else:
        # Build in the same directory as the def file
        build_success, output_path = build_container_in_def_directory(
            def_file_path,
            output_name=(
                os.path.basename(args.output) if args.output != "hyrise.sif" else None
            ),
            singularity_path=singularity_path,
            sudo=args.sudo,
            force=args.force,
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


def main():
    """
    Main entry point for the standalone container builder command.
    """
    parser = argparse.ArgumentParser(description="HyRISE Container Builder")
    parser.add_argument(
        "--output",
        "-o",
        default="hyrise.sif",
        help="Output file path for the Singularity container (default: hyrise.sif)",
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

    args = parser.parse_args()

    return run_container_command(args)


if __name__ == "__main__":
    sys.exit(main())
