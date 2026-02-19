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
)
from hyrise.utils.common_args import (
    add_config_argument,
    add_container_arguments,
    add_report_arguments,
    add_visualization_arguments,
    add_interactive_arguments,
)
from hyrise.config import (
    load_config,
    resolve_container_path,
    resolve_container_runtime,
    resolve_resource_dir,
)

from hyrise.utils.resource_updater import (
    get_latest_resource_path,
    select_latest_hivdb_xml,
    update_apobec_drms,
    update_hivdb_xml,
)

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

# Set up logging
logger = logging.getLogger("hyrise-sierra")


def _default_sierra_output_name(fasta_files) -> str:
    """Return default SierraLocal JSON filename based on first FASTA."""
    base_name = os.path.splitext(os.path.basename(fasta_files[0]))[0]
    return f"{base_name}_NGS_results.json"


def _resolve_output_json_path(output, fasta_files) -> str:
    """
    Resolve user-provided output into a concrete JSON filepath.

    Rules:
    - empty output: default filename in current directory
    - existing directory or trailing slash: write default filename inside directory
    - explicit file path without suffix: append `.json`
    """
    default_name = _default_sierra_output_name(fasta_files)
    if not output:
        return os.path.abspath(default_name)

    output_str = str(output)
    output_path = Path(output_str).expanduser()

    if output_path.exists() and output_path.is_dir():
        return str((output_path / default_name).resolve())

    if output_str.endswith(os.sep) or (os.altsep and output_str.endswith(os.altsep)):
        return str((output_path / default_name).resolve())

    if output_path.suffix == "":
        output_path = output_path.with_suffix(".json")

    return str(output_path.resolve())


def _bundled_hivdb_xml_path() -> Path:
    """Return the latest bundled HIVdb XML path shipped with HyRISE."""
    package_root = Path(__file__).resolve().parent.parent
    bundled_xml_files = list(package_root.glob("HIVDB_*.xml"))
    latest = select_latest_hivdb_xml(bundled_xml_files)
    if latest:
        return latest
    if bundled_xml_files:
        return sorted(bundled_xml_files)[-1]
    # Fallback path for clearer error handling if package data is missing.
    return package_root.joinpath("HIVDB.xml")


def _prefer_latest_downloaded_hivdb_xml(
    selected_xml: str | None, resource_dir: str | None = None
) -> str | None:
    """
    If user is using the bundled default XML, prefer a downloaded HIVDB_*.xml resource.

    Explicit custom XML paths are preserved.
    """
    if not selected_xml:
        return selected_xml

    bundled_default = _bundled_hivdb_xml_path().resolve()
    selected_path = Path(selected_xml).expanduser().resolve()
    if selected_path != bundled_default:
        return selected_xml

    latest_xml = get_latest_resource_path("hivdb_xml", resource_dir=resource_dir)
    if not latest_xml:
        return selected_xml

    latest_path = Path(latest_xml).expanduser().resolve()
    if latest_path.exists() and latest_path != bundled_default:
        logger.info(f"Using latest downloaded HIVdb XML from resources: {latest_path}")
        return str(latest_path)

    return selected_xml


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
        help=(
            "Output JSON path. Accepts a filename or directory "
            "(default: <input>_NGS_results.json)."
        ),
    )

    # bundled default XML in your package:
    xml_default = _bundled_hivdb_xml_path()
    sierra_parser.add_argument(
        "--xml",
        default=str(xml_default),
        help=(
            "Path to HIVdb ASI2 XML file (default: latest bundled HIVDB_*.xml; "
            "automatically uses latest downloaded HIVDB_*.xml from resources "
            "when available)"
        ),
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
        "--resource-dir",
        help="Writable directory for downloaded HIVdb resource updates",
    )

    sierra_parser.add_argument(
        "--alignment",
        choices=["post", "nuc"],
        default="post",
        help="Alignment program to use: 'post' for post align, 'nuc' for nucamino (default: post)",
    )

    # Add common container arguments
    add_container_arguments(sierra_parser)
    add_config_argument(sierra_parser)

    # Add interactive mode argument
    add_interactive_arguments(sierra_parser)

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
    container_runtime=None,
    resource_dir=None,
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

    # Handle forceupdate here rather than passing to SierraLocal
    if forceupdate:
        logger.info("Force update requested, updating HIVdb resources...")
        try:
            new_xml = update_hivdb_xml(resource_dir=resource_dir)
            new_json = update_apobec_drms(resource_dir=resource_dir)

            if new_xml and os.path.exists(new_xml):
                logger.info(f"Using updated HIVdb XML: {new_xml}")
                xml = new_xml

            if new_json and os.path.exists(new_json):
                logger.info(f"Using updated APOBEC data: {new_json}")
                json_file = new_json

        except Exception as e:
            logger.warning(f"Error updating resources: {str(e)}")
            logger.warning("Continuing with existing resources")

    # Determine normalized output path
    output_abs = _resolve_output_json_path(output, fasta_files_abs)
    output_parent = os.path.dirname(output_abs)
    if output_parent:
        os.makedirs(output_parent, exist_ok=True)

    # Check dependencies and container
    deps = ensure_dependencies(
        use_container=container,
        required_tools=["sierralocal"],
        container_path=container_path,
        container_runtime=container_runtime,
    )

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
        results["error"] = (
            "Container required but not found.\n"
            "Options:\n"
            "  1) Pull prebuilt image: apptainer pull hyrise.sif docker://ghcr.io/phac-nml/hyrise:latest\n"
            "  2) Provide explicit path with --container-path\n"
            "  3) Use native sierralocal install and rerun with --no-container"
        )
        return results

    # If not using container but SierraLocal not available
    if not use_container and not deps["sierra_local_available"]:
        results["error"] = (
            "SierraLocal is not available and container usage is disabled.\n"
            "Install options:\n"
            "  - Native: pip install sierralocal post-align\n"
            "  - Container: hyrise sierra ... --container --container-path /path/to/hyrise.sif\n"
            "  - HPC pull: apptainer pull hyrise.sif docker://ghcr.io/phac-nml/hyrise:latest"
        )
        return results

    try:
        if use_container:
            runtime_path = deps.get("runtime_path")
            if not runtime_path:
                results["error"] = (
                    "No supported container runtime found (apptainer/singularity)"
                )
                return results

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

                if alignment:
                    cmd_parts.extend(["-alignment", alignment])

                # Add FASTA files (just the basenames since we're in temp dir)
                for fasta_file in temp_fasta_files:
                    cmd_parts.append(os.path.basename(fasta_file))

                full_cmd = [
                    runtime_path,
                    "exec",
                    "--bind",
                    temp_dir,
                    "--pwd",
                    temp_dir,
                    deps["container_path"],
                    *cmd_parts,
                ]
                logger.info(
                    f"Running SierraLocal with container from dir {temp_dir}: {' '.join(full_cmd)}"
                )

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


def run_interactive_sierra():
    """
    Run SierraLocal in interactive mode.

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    if not QUESTIONARY_AVAILABLE:
        logger.error("Interactive mode requires the 'questionary' package.")
        logger.error("Please install it with: pip install questionary")
        return 1

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    print("\n=== HyRISE SierraLocal Integration (Interactive Mode) ===\n")

    # Step 1: Select FASTA files
    fasta_files = []
    while True:
        # For the first file, make it required
        if not fasta_files:
            fasta_file = questionary.path(
                "Select FASTA file:",
                style=CUSTOM_STYLE,
                validate=lambda x: os.path.isfile(x) or "File doesn't exist",
            ).ask()

            if not fasta_file:
                return 1

            fasta_files.append(fasta_file)
        else:
            # For additional files, make them optional
            add_more = questionary.confirm(
                "Add another FASTA file?", default=False, style=CUSTOM_STYLE
            ).ask()

            if not add_more:
                break

            fasta_file = questionary.path(
                f"Select FASTA file #{len(fasta_files) + 1}:",
                style=CUSTOM_STYLE,
                validate=lambda x: os.path.isfile(x) or "File doesn't exist",
            ).ask()

            if fasta_file:
                fasta_files.append(fasta_file)

    # Step 2: Output file
    default_output = (
        os.path.splitext(os.path.basename(fasta_files[0]))[0] + "_NGS_results.json"
    )
    output = questionary.text(
        "Output JSON filename:", default=default_output, style=CUSTOM_STYLE
    ).ask()

    # Step 3: XML file
    xml_default = _bundled_hivdb_xml_path()
    use_default_xml = questionary.confirm(
        f"Use default HIVdb XML file ({xml_default.name})?",
        default=True,
        style=CUSTOM_STYLE,
    ).ask()

    xml = str(xml_default) if use_default_xml else None

    if not use_default_xml:
        xml = questionary.path(
            "Path to HIVdb ASI2 XML file:",
            style=CUSTOM_STYLE,
            validate=lambda x: os.path.isfile(x) or "File doesn't exist",
        ).ask()
    else:
        xml = _prefer_latest_downloaded_hivdb_xml(xml, resource_dir=None)

    # Step 4: JSON file (optional)
    use_json = questionary.confirm(
        "Use a JSON HIVdb APOBEC DRM file?", default=False, style=CUSTOM_STYLE
    ).ask()

    json_file = None
    if use_json:
        json_file = questionary.path(
            "Path to JSON HIVdb APOBEC DRM file:",
            style=CUSTOM_STYLE,
            validate=lambda x: os.path.isfile(x) or "File doesn't exist",
        ).ask()

    # Step 5: Alignment program
    choices = [
        {"name": "Post-Align (recommended)", "value": "post"},
        {"name": "NucAmino", "value": "nuc"},
    ]

    alignment = questionary.select(
        "Select alignment program:",
        choices=choices,
        default=choices[0],  # Use the first choice object
        style=CUSTOM_STYLE,
    ).ask()

    # Step 6: Other SierraLocal options
    cleanup = questionary.confirm(
        "Delete NucAmino alignment file after processing?",
        default=True,
        style=CUSTOM_STYLE,
    ).ask()

    forceupdate = questionary.confirm(
        "Force update of HIVdb algorithm? (requires network connection)",
        default=False,
        style=CUSTOM_STYLE,
    ).ask()

    # Step 7: Container options
    deps = ensure_dependencies()
    container_option = questionary.select(
        "Container usage:",
        choices=[
            {"name": "Auto-detect (recommended)", "value": None},
            {"name": "Force container usage", "value": "container"},
            {"name": "Force native execution", "value": "no-container"},
        ],
        style=CUSTOM_STYLE,
    ).ask()

    container = None
    if container_option == "container":
        container = True
    elif container_option == "no-container":
        container = False

    container_path = None
    if container is True and not deps["container_path"]:
        use_custom_container = questionary.confirm(
            "Specify custom container path?", default=False, style=CUSTOM_STYLE
        ).ask()

        if use_custom_container:
            container_path = questionary.path(
                "Container path:",
                style=CUSTOM_STYLE,
                validate=lambda x: os.path.isfile(x) or "File doesn't exist",
            ).ask()

    # Step 8: Process options
    process = questionary.confirm(
        "Process the generated JSON file with HyRISE after generation?",
        default=True,
        style=CUSTOM_STYLE,
    ).ask()

    process_dir = None
    report = False
    run_multiqc = False
    guide = False
    sample_info = False
    contact_email = None

    if process:
        # Default process dir
        default_process_dir = os.path.splitext(output)[0] + "_output"
        process_dir = questionary.text(
            "Output directory for processing:",
            default=default_process_dir,
            style=CUSTOM_STYLE,
        ).ask()

        report = questionary.confirm(
            "Generate MultiQC configuration file?", default=True, style=CUSTOM_STYLE
        ).ask()

        if report:
            run_multiqc = questionary.confirm(
                "Run MultiQC to generate HTML report?", default=True, style=CUSTOM_STYLE
            ).ask()

        guide = questionary.confirm(
            "Include interpretation guides?", default=True, style=CUSTOM_STYLE
        ).ask()

        sample_info = questionary.confirm(
            "Include sample information?", default=True, style=CUSTOM_STYLE
        ).ask()

        if report:
            use_email = questionary.confirm(
                "Include contact email in report?", default=False, style=CUSTOM_STYLE
            ).ask()

            if use_email:
                contact_email = questionary.text(
                    "Contact email:", style=CUSTOM_STYLE
                ).ask()

    # Step 9: Confirm and run
    logger.info("\nSierraLocal processing with the following options:")
    logger.info(f"FASTA files: {', '.join(fasta_files)}")
    logger.info(f"Output JSON: {output}")
    logger.info(f"XML file: {xml}")
    logger.info(f"JSON file: {json_file or 'None'}")
    logger.info(f"Alignment program: {alignment}")
    logger.info(f"Cleanup: {cleanup}")
    logger.info(f"Force update: {forceupdate}")
    logger.info(f"Container usage: {container_option}")

    if process:
        logger.info("\nProcessing options:")
        logger.info(f"Process directory: {process_dir}")
        logger.info(f"Generate report: {report}")
        logger.info(f"Run MultiQC: {run_multiqc}")
        logger.info(f"Include guides: {guide}")
        logger.info(f"Include sample info: {sample_info}")
        logger.info(f"Contact email: {contact_email or 'None'}")

    confirm = questionary.confirm(
        "Proceed with processing?", default=True, style=CUSTOM_STYLE
    ).ask()

    if not confirm:
        logger.info("Operation cancelled.")
        return 0

    # Run SierraLocal
    sierra_results = run_sierra_local(
        fasta_files,
        output=output,
        xml=xml,
        json_file=json_file,
        cleanup=cleanup,
        forceupdate=forceupdate,
        alignment=alignment,
        container=container,
        container_path=container_path,
        container_runtime=None,
        resource_dir=None,
    )

    if not sierra_results["success"]:
        logger.error(f"Error: {sierra_results['error']}")
        return 1

    logger.info(
        f"SierraLocal completed successfully. Output saved to: {sierra_results['output_path']}"
    )

    # Process the generated JSON file if requested
    if process:
        from hyrise.core.processor import process_files

        logger.info(f"Processing generated JSON with HyRISE, output to: {process_dir}")

        try:
            # Create the output directory if it doesn't exist
            if not os.path.exists(process_dir):
                os.makedirs(process_dir, exist_ok=True)

            # Process the JSON file - pass all relevant arguments
            process_results = process_files(
                sierra_results["output_path"],
                process_dir,
                generate_report=report,
                run_multiqc=run_multiqc,
                guide=guide,
                sample_info=sample_info,
                contact_email=contact_email,
                logo_path=None,  # Could add logo option if needed
                use_container=container,
                container_path=container_path,
                container_runtime=None,
            )

            # Print summary
            if report and run_multiqc and process_results.get("report_dir"):
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

            return 0

        except Exception as e:
            logger.error(f"Error processing JSON file: {str(e)}")
            logger.info(f"JSON generation was successful, but processing failed.")
            logger.info(
                f"You can still process the JSON file manually with: hyrise process -i {sierra_results['output_path']} -o <output_dir>"
            )
            return 1

    return 0


def run_sierra_command(args):
    """
    Run the sierra command.

    Args:
        args: Parsed command-line arguments

    Returns:
        int: Exit code (0 for success, non-zero for errors)
    """
    # Check if interactive mode is requested
    if hasattr(args, "interactive") and args.interactive:
        return run_interactive_sierra()

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
    resolved_xml = _prefer_latest_downloaded_hivdb_xml(
        args.xml, resource_dir=getattr(args, "resource_dir", None)
    )
    resolved_output = args.output
    if args.process and not args.output and args.process_dir:
        # Keep Sierra JSON next to the processing output when process-dir is explicit.
        default_name = _default_sierra_output_name(args.fasta)
        resolved_output = str(Path(args.process_dir) / default_name)

    sierra_results = run_sierra_local(
        args.fasta,
        output=resolved_output,
        xml=resolved_xml,
        json_file=args.json,
        cleanup=args.cleanup,
        forceupdate=args.forceupdate,
        alignment=args.alignment,
        container=use_container,
        container_path=args.container_path,
        container_runtime=getattr(args, "container_runtime", None),
        resource_dir=getattr(args, "resource_dir", None),
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
                container_runtime=getattr(args, "container_runtime", None),
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
        help=(
            "Output JSON path. Accepts a filename or directory "
            "(default: <input>_NGS_results.json)."
        ),
    )
    # bundled default XML in your package:
    xml_default = _bundled_hivdb_xml_path()
    parser.add_argument(
        "--xml",
        default=str(xml_default),
        help=(
            "Path to HIVdb ASI2 XML file (default: latest bundled HIVDB_*.xml; "
            "automatically uses latest downloaded HIVDB_*.xml from resources "
            "when available)"
        ),
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
        "--resource-dir",
        help="Writable directory for downloaded HIVdb resource updates",
    )
    parser.add_argument(
        "--alignment",
        choices=["post", "nuc"],
        default="post",
        help="Alignment program to use: 'post' for post align, 'nuc' for nucamino (default: post)",
    )

    # Add common arguments using our utility functions
    add_container_arguments(parser)
    add_config_argument(parser)
    add_interactive_arguments(parser)  # Add interactive mode flag

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
    config = load_config(getattr(args, "config", None))
    args.container_path = resolve_container_path(config, args.container_path)
    args.container_runtime = resolve_container_runtime(config, args.container_runtime)
    args.resource_dir = resolve_resource_dir(config, args.resource_dir)

    # Check if interactive mode is requested
    if hasattr(args, "interactive") and args.interactive:
        return run_interactive_sierra()

    return run_sierra_command(args)


if __name__ == "__main__":
    sys.exit(main())
