#!/usr/bin/env python3
"""
HyRISE SierraLocal Integration

This module provides integration with SierraLocal to generate JSON files from FASTA inputs.
These JSON files can then be processed by the main HyRISE functionality.
"""

import os
import sys
import subprocess
import logging
import argparse
import tempfile
import shutil
from pathlib import Path

from hyrise.utils.container_utils import (
    ensure_dependencies,
    run_with_singularity,
    check_command_available,
    find_singularity_container,
)
from hyrise.utils.common_args import (
    add_container_arguments,
    add_report_arguments,
    add_visualization_arguments,
)

# Set up logging
logger = logging.getLogger("hyrise-sierra")


def add_sierra_subparser(subparsers):
    """
    Add the sierra command to the CLI.

    Args:
        subparsers: Subparsers object to add the sierra parser to
    """
    # Create the sierra parser
    sierra_parser = subparsers.add_parser(
        "sierra",
        help="Generate JSON files from FASTA inputs using SierraLocal",
        description="Process FASTA files with SierraLocal to generate JSON files for analysis.",
    )

    # Add Sierra-specific options
    sierra_parser.add_argument(
        "fasta", nargs="+", help="Input FASTA file(s) to process"
    )

    sierra_parser.add_argument(
        "-o",
        "--output",
        help="Output JSON filename (default: input filename with .json extension)",
    )

    # bundled default XML in your package:
    xml_default = Path(
        __file__
    ).parent.parent.joinpath(  # src/hyrise/commands  # src/hyrise
        "HIVDB_9.8.xml"
    )
    sierra_parser.add_argument(
        "--xml",
        default=str(xml_default),
        help=f"Path to HIVdb ASI2 XML file (default: {xml_default.name})",
    )

    sierra_parser.add_argument("--json", help="Path to JSON HIVdb APOBEC DRM file")

    sierra_parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete NucAmino alignment file after processing",
    )

    sierra_parser.add_argument(
        "--forceupdate",
        action="store_true",
        help="Force update of HIVdb algorithm (requires network connection)",
    )

    sierra_parser.add_argument(
        "--alignment",
        choices=["post", "nuc"],
        default="post",
        help="Alignment program to use: 'post' for post align, 'nuc' for nucamino (default: post)",
    )

    # Add common container arguments
    add_container_arguments(sierra_parser)

    # Add processing options with a separate group
    process_group = sierra_parser.add_argument_group("Processing options")

    process_group.add_argument(
        "--process",
        action="store_true",
        help="Process the generated JSON file with HyRISE after generation",
    )

    process_group.add_argument(
        "--process-dir",
        help='Output directory for HyRISE processing (default: current directory + "_output")',
    )

    # Add common report and visualization arguments
    # These are only relevant if --process is used
    add_report_arguments(process_group)
    add_visualization_arguments(process_group)

    # Add verbose option
    sierra_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    # Set the function to be called when this subcommand is used
    sierra_parser.set_defaults(func=run_sierra_command)


def run_sierra_local(
    fasta_files,
    output=None,
    xml=None,
    json_file=None,
    cleanup=False,
    forceupdate=False,
    alignment="post",
    container=None,
    container_path=None,
):
    """
    Run SierraLocal on the given FASTA files.

    Args:
        fasta_files (list): List of FASTA file paths
        output (str, optional): Output JSON filename
        xml (str, optional): Path to HIVdb ASI2 XML file
        json_file (str, optional): Path to JSON HIVdb APOBEC DRM file
        cleanup (bool): Whether to delete alignment files after processing
        forceupdate (bool): Whether to force update of HIVdb algorithm
        alignment (str): Alignment program to use
        container (bool, optional): Whether to use container (True, False, or None for auto)
        container_path (str, optional): Path to container file

    Returns:
        dict: Results of the operation including output path
    """
    results = {
        "success": False,
        "output_path": None,
        "container_used": False,
        "error": None,
        "input_files": fasta_files,
    }

    logger.info(
        f"Processing {len(fasta_files)} FASTA files: {[os.path.basename(f) for f in fasta_files]}"
    )

    # Validate file existence
    for fasta_file in fasta_files:
        if not os.path.exists(fasta_file):
            results["error"] = f"FASTA file not found: {fasta_file}"
            return results

    # Create absolute paths for container binding
    fasta_files_abs = [os.path.abspath(f) for f in fasta_files]
    if xml:
        xml = os.path.abspath(xml)
        if not os.path.exists(xml):
            results["error"] = f"XML file not found: {xml}"
            return results

    if json_file:
        json_file = os.path.abspath(json_file)
        if not os.path.exists(json_file):
            results["error"] = f"JSON file not found: {json_file}"
            return results

    # Determine output path
    if not output:
        # Use first FASTA file name as base
        base_name = os.path.splitext(os.path.basename(fasta_files[0]))[0]
        output = f"{base_name}_NGS_results.json"

    output_abs = os.path.abspath(output)

    # Check dependencies and container
    deps = ensure_dependencies(container)

    # Determine if we should use container
    use_container = deps["use_container"]

    # Override container path if specified
    if container_path:
        if os.path.exists(container_path):
            deps["container_path"] = container_path
        else:
            results["error"] = f"Container not found at {container_path}"
            return results

    # If we need container but don't have it
    if use_container and not deps["container_path"]:
        results["error"] = "Container required but not found"
        return results

    # If not using container but SierraLocal not available
    if not use_container and not deps["sierra_local_available"]:
        results["error"] = "SierraLocal not available and container usage disabled"
        return results

    try:
        if use_container:
            # Create a temporary directory for the operation
            with tempfile.TemporaryDirectory() as temp_dir:
                # Build command for container
                cmd_parts = ["sierralocal"]

                # For container execution, we need to handle paths differently
                # Copy all FASTA files to the temp directory
                temp_fasta_files = []
                for fasta_file in fasta_files_abs:
                    dest_file = os.path.join(temp_dir, os.path.basename(fasta_file))
                    shutil.copy2(fasta_file, dest_file)
                    temp_fasta_files.append(dest_file)

                # Add output option (will be in the temp directory)
                output_name = os.path.basename(output_abs)
                temp_output = os.path.join(temp_dir, output_name)
                cmd_parts.extend(["-o", output_name])

                # Add other options
                if xml:
                    # Copy XML file to temp dir
                    temp_xml = os.path.join(temp_dir, os.path.basename(xml))
                    shutil.copy2(xml, temp_xml)
                    cmd_parts.extend(["-xml", os.path.basename(xml)])

                if json_file:
                    # Copy JSON file to temp dir
                    temp_json = os.path.join(temp_dir, os.path.basename(json_file))
                    shutil.copy2(json_file, temp_json)
                    cmd_parts.extend(["-json", os.path.basename(json_file)])

                if cleanup:
                    cmd_parts.append("--cleanup")

                if forceupdate:
                    cmd_parts.append("--forceupdate")

                if alignment:
                    cmd_parts.extend(["-alignment", alignment])

                # Add FASTA files (just the basenames since we're in temp dir)
                for fasta_file in temp_fasta_files:
                    cmd_parts.append(os.path.basename(fasta_file))

                # Get the container path
                singularity_path = find_singularity_container()

                # Build command to run inside the container
                # This time WITHOUT using cd or shell operators like &&
                cmd = " ".join(cmd_parts)
                logger.info(
                    f"Running SierraLocal with container from dir {temp_dir}: {cmd}"
                )

                # Run the command with the working directory set to the temp dir
                # Using subprocess directly to have more control
                full_cmd = [
                    "singularity",
                    "exec",
                    "--bind",
                    temp_dir,
                    deps["container_path"],
                    "sh",
                    "-c",
                    f"cd {temp_dir} && {cmd}",
                ]

                subprocess.run(full_cmd, check=True)

                # Check if output file was created in the temp directory
                if os.path.exists(temp_output):
                    # Copy the output file to the original destination
                    shutil.copy2(temp_output, output_abs)
                    results["success"] = True
                    results["output_path"] = output_abs
                    results["container_used"] = True
                else:
                    results["error"] = "Output file was not created in container"
        else:
            # Build command for native execution
            cmd_parts = ["sierralocal"]

            if output:
                cmd_parts.extend(["-o", output_abs])

            if xml:
                cmd_parts.extend(["-xml", xml])

            if json_file:
                cmd_parts.extend(["-json", json_file])

            if cleanup:
                cmd_parts.append("--cleanup")

            if forceupdate:
                cmd_parts.append("--forceupdate")

            if alignment:
                cmd_parts.extend(["-alignment", alignment])

            # Add FASTA files
            cmd_parts.extend(fasta_files_abs)

            # Run command
            logger.info(f"Running SierraLocal natively: {' '.join(cmd_parts)}")
            subprocess.run(cmd_parts, check=True)

            # Check if output file was created
            if os.path.exists(output_abs):
                results["success"] = True
                results["output_path"] = output_abs
            else:
                results["error"] = "Output file was not created"

        return results

    except subprocess.CalledProcessError as e:
        results["error"] = f"SierraLocal execution failed: {str(e)}"
        return results

    except Exception as e:
        results["error"] = f"Error running SierraLocal: {str(e)}"
        return results


def run_sierra_command(args):
    """
    Run the sierra command.

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

    # Determine container usage
    use_container = None
    if args.container:
        use_container = True
    elif args.no_container:
        use_container = False

    # Check if any processing flags are set, adjust accordingly
    if args.run_multiqc:
        args.report = True
    if args.report:
        args.process = True

    # Run SierraLocal
    sierra_results = run_sierra_local(
        args.fasta,
        output=args.output,
        xml=args.xml,
        json_file=args.json,
        cleanup=args.cleanup,
        forceupdate=args.forceupdate,
        alignment=args.alignment,
        container=use_container,
        container_path=args.container_path,
    )

    if not sierra_results["success"]:
        logger.error(f"Error: {sierra_results['error']}")
        return 1

    # Check if glob pattern didn't match any files
    if not args.fasta:
        logger.error("No FASTA files found matching the provided pattern.")
        return 1

    logger.info(f"Found {len(args.fasta)} FASTA files to process")
    logger.info(
        f"SierraLocal completed successfully. Output saved to: {sierra_results['output_path']}"
    )

    # Process the generated JSON file if requested
    if args.process:
        from hyrise.core.processor import process_files

        # Determine output directory for processing
        if args.process_dir:
            process_dir = args.process_dir
        else:
            # Default to input filename + _output
            base_dir = os.path.splitext(sierra_results["output_path"])[0]
            process_dir = f"{base_dir}_output"

        logger.info(f"Processing generated JSON with HyRISE, output to: {process_dir}")

        try:
            # Process the JSON file - pass all relevant arguments
            process_results = process_files(
                sierra_results["output_path"],
                process_dir,
                generate_report=args.report,
                run_multiqc=args.run_multiqc,
                guide=args.guide,
                sample_info=args.sample_info,
                contact_email=args.contact_email,
                logo_path=args.logo if hasattr(args, "logo") else None,
                use_container=use_container,
                container_path=(
                    args.container_path if hasattr(args, "container_path") else None
                ),
            )

            # Print summary
            if args.report and args.run_multiqc and process_results.get("report_dir"):
                logger.info(f"\nSummary:")
                logger.info(f"- JSON generated at: {sierra_results['output_path']}")
                logger.info(f"- Report generated at: {process_results['report_dir']}")
                logger.info(
                    f"- Files processed: {len(process_results['files_generated'])}"
                )
                if process_results["container_used"]:
                    logger.info(f"- Processing execution mode: Singularity container")
                else:
                    logger.info(f"- Processing execution mode: Native")
            else:
                logger.info(
                    f"JSON generated and processed. Files created in: {process_dir}"
                )

        except Exception as e:
            logger.error(f"Error processing JSON file: {str(e)}")
            logger.info(f"JSON generation was successful, but processing failed.")
            logger.info(
                f"You can still process the JSON file manually with: hyrise process -i {sierra_results['output_path']} -o <output_dir>"
            )
            return 1

    return 0


def main():
    """
    Main entry point for the standalone sierra command.
    """
    parser = argparse.ArgumentParser(description="HyRISE SierraLocal Integration")

    # Add arguments - using the same structure as the subparser for consistency
    parser.add_argument("fasta", nargs="+", help="Input FASTA file(s) to process")

    parser.add_argument(
        "-o",
        "--output",
        help="Output JSON filename (default: input filename with .json extension)",
    )
    # bundled default XML in your package:
    xml_default = Path(
        __file__
    ).parent.parent.joinpath(  # src/hyrise/commands  # src/hyrise
        "HIVDB_9.8.xml"
    )
    parser.add_argument(
        "--xml",
        default=str(xml_default),
        help=f"Path to HIVdb ASI2 XML file (default: {xml_default.name})",
    )
    parser.add_argument("--json", help="Path to JSON HIVdb APOBEC DRM file")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete NucAmino alignment file after processing",
    )
    parser.add_argument(
        "--forceupdate",
        action="store_true",
        help="Force update of HIVdb algorithm (requires network connection)",
    )
    parser.add_argument(
        "--alignment",
        choices=["post", "nuc"],
        default="post",
        help="Alignment program to use: 'post' for post align, 'nuc' for nucamino (default: post)",
    )

    # Add common arguments using our utility functions
    add_container_arguments(parser)

    # Processing options
    parser.add_argument(
        "--process",
        action="store_true",
        help="Process the generated JSON file with HyRISE after generation",
    )
    parser.add_argument(
        "--process-dir",
        help='Output directory for HyRISE processing (default: current directory + "_output")',
    )

    # Add reporting and visualization options
    add_report_arguments(parser)
    add_visualization_arguments(parser)

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    return run_sierra_command(args)


if __name__ == "__main__":
    sys.exit(main())
