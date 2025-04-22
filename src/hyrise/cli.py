#!/usr/bin/env python3
# hyrise/cli.py
"""
Command line interface for HyRISE (HIV Resistance Interpretation and Visualization System)
"""
import argparse
import sys
import os
import logging
from hyrise import __version__
from hyrise.core.processor import process_files
from hyrise.utils.container_utils import ensure_dependencies
from hyrise.commands import container, sierra
from hyrise.utils.common_args import (
    add_container_arguments,
    add_report_arguments,
    add_visualization_arguments,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("hyrise-cli")


def main():
    """
    Main entry point for the CLI

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="HyRISE: HIV Resistance Interpretation and Visualization System",
        prog="hyrise",
    )

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Process command (default)
    process_parser = subparsers.add_parser(
        "process", help="Process Sierra JSON file and generate visualizations"
    )

    process_parser.add_argument("-i", "--input", required=True, help="Sierra JSON file")

    process_parser.add_argument(
        "-o",
        "--output_dir",
        required=True,
        help="Directory to write MultiQC custom content files",
    )

    process_parser.add_argument(
        "-s",
        "--sample_name",
        help="Sample name to use in the report (default: extracted from filename)",
    )

    # Add common argument groups
    add_report_arguments(process_parser)
    add_visualization_arguments(process_parser)
    add_container_arguments(process_parser)

    # Add check-deps command
    check_parser = subparsers.add_parser(
        "check-deps", help="Check for dependencies and container availability"
    )

    check_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed information"
    )

    # Add container building command
    container.add_container_subparser(subparsers)

    # Add SierraLocal integration command
    sierra.add_sierra_subparser(subparsers)

    # Add version argument to main parser
    parser.add_argument(
        "-v", "--version", action="version", version=f"HyRISE {__version__}"
    )

    args = parser.parse_args()

    # If no command specified, show help and exit
    if not args.command:
        parser.print_help()
        return 0

    # Dispatch to appropriate command handlers
    if args.command == "process":
        return run_process_command(args)
    elif args.command == "check-deps":
        return run_check_deps_command(args)
    elif args.command == "sierra":
        # This is handled by the sierra module's set_defaults
        if hasattr(args, "func"):
            return args.func(args)
    elif args.command == "container":
        # This is handled by the container module's set_defaults
        if hasattr(args, "func"):
            return args.func(args)

    # If we reach here, something went wrong with command dispatch
    parser.print_help()
    return 1


def run_process_command(args):
    """
    Run the process command

    Args:
        args: Parsed command-line arguments

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    # Determine container usage
    use_container = None
    if args.container:
        use_container = True
    elif args.no_container:
        use_container = False

    # If custom container path is provided, verify it exists
    if args.container_path:
        if not os.path.exists(args.container_path):
            logger.error(
                f"Error: Specified container not found at {args.container_path}"
            )
            return 1

    # If run-multiqc is specified, ensure report is also set
    if args.run_multiqc:
        args.report = True

    try:
        results = process_files(
            args.input,
            args.output_dir,
            sample_name=args.sample_name,
            generate_report=args.report,
            run_multiqc=args.run_multiqc,
            guide=args.guide,
            sample_info=args.sample_info,
            contact_email=args.contact_email,
            logo_path=args.logo,
            use_container=use_container,
            container_path=args.container_path,
        )

        # Print summary
        if args.report and args.run_multiqc and results.get("report_dir"):
            logger.info(f"\nSummary:")
            logger.info(f"- Report generated at: {results['report_dir']}")
            logger.info(f"- Files processed: {len(results['files_generated'])}")
            if results["container_used"]:
                logger.info(f"- Execution mode: Singularity container")
            else:
                logger.info(f"- Execution mode: Native")

        return 0
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return 1


def run_check_deps_command(args):
    """
    Run the check-deps command

    Args:
        args: Parsed command-line arguments

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    deps = ensure_dependencies()

    logger.info("\nDependency Check Results:")
    logger.info("-------------------------")
    logger.info(f"MultiQC available: {deps['multiqc_available']}")
    logger.info(f"SierraLocal available: {deps['sierra_local_available']}")
    logger.info(f"Singularity available: {deps['singularity_available']}")

    container_path = deps["container_path"]
    if container_path:
        logger.info(f"Container found at: {container_path}")
    else:
        logger.info("Container not found")

    if deps["missing_dependencies"]:
        logger.info(
            f"\nMissing dependencies: {', '.join(deps['missing_dependencies'])}"
        )

        if deps["singularity_available"] and container_path:
            logger.info(
                "\nMissing dependencies can be handled using the Singularity container."
            )
            logger.info("Use the --container flag to enable container execution.")
        else:
            logger.info(
                "\nPlease install missing dependencies or provide a Singularity container."
            )
            logger.info("You can build a container with: hyrise container")
    else:
        logger.info("\nAll dependencies are satisfied. Native execution is possible.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
