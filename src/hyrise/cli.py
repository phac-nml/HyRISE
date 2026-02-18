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
from hyrise.config import (
    load_config,
    resolve_container_path,
    resolve_container_runtime,
    resolve_resource_dir,
)
from hyrise.core.processor import process_files
from hyrise.utils.container_utils import ensure_dependencies
from hyrise.commands import container, sierra
from hyrise.utils.resource_updater import add_resources_subparser
from hyrise.utils.common_args import (
    add_config_argument,
    add_container_arguments,
    add_report_arguments,
    add_visualization_arguments,
    add_interactive_arguments,  # New import
)

# Try to import Questionary for interactive UI
try:
    import questionary
    from questionary import Style

    QUESTIONARY_AVAILABLE = True
except ImportError:
    QUESTIONARY_AVAILABLE = False

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("hyrise-cli")

# Custom style for questionary prompts
CUSTOM_STYLE = None
if QUESTIONARY_AVAILABLE:
    CUSTOM_STYLE = Style(
        [
            ("question", "bold cyan"),
            ("answer", "bold green"),
            ("pointer", "bold cyan"),
            ("highlighted", "bold green"),
            ("selected", "bold green"),
        ]
    )


def main():
    """
    Main entry point for the CLI

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    quickstart = """
Quickstart examples:
  hyrise process -i sample_results.json -o out
  hyrise process -i sample_results.json -o out --report --run-multiqc
  hyrise sierra sample.fasta --process --process-dir out
"""
    parser = argparse.ArgumentParser(
        description="HyRISE: HIV Resistance Interpretation and Visualization System",
        prog="hyrise",
        epilog=quickstart,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_config_argument(parser)
    add_interactive_arguments(parser)

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Process command (default)
    process_parser = subparsers.add_parser(
        "process", help="Process Sierra JSON file and generate visualizations"
    )

    process_parser.add_argument(
        "inputs",
        nargs="*",
        help="Optional Sierra JSON input file(s) as positional arguments",
    )
    process_parser.add_argument(
        "-i",
        "--input",
        required=False,
        help="Sierra JSON file (alternative to positional input)",
    )

    process_parser.add_argument(
        "-o",
        "--output-dir",
        "--output_dir",
        "--out",
        dest="output_dir",
        required=True,
        help="Directory to write MultiQC custom content files",
    )
    add_config_argument(process_parser)

    process_parser.add_argument(
        "-s",
        "--sample_name",
        help="Sample name to use in the report (default: extracted from filename)",
    )

    # Add common argument groups
    add_report_arguments(process_parser)
    add_visualization_arguments(process_parser)
    add_container_arguments(process_parser)
    add_interactive_arguments(process_parser)  # Add interactive mode flag

    # Add check-deps command
    check_parser = subparsers.add_parser(
        "check-deps", help="Check for dependencies and container availability"
    )

    check_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed information"
    )
    add_config_argument(check_parser)
    add_container_arguments(check_parser)
    add_interactive_arguments(check_parser)  # Add interactive mode flag

    # Add container building command
    container.add_container_subparser(subparsers)

    # Add SierraLocal integration command
    sierra.add_sierra_subparser(subparsers)
    add_resources_subparser(subparsers)

    # Add version argument to main parser
    parser.add_argument(
        "-v", "--version", action="version", version=f"HyRISE {__version__}"
    )

    args = parser.parse_args()

    config = load_config(getattr(args, "config", None))
    if hasattr(args, "container_path"):
        args.container_path = resolve_container_path(
            config=config, cli_container_path=getattr(args, "container_path", None)
        )
    if hasattr(args, "container_runtime"):
        args.container_runtime = resolve_container_runtime(
            config=config, cli_runtime=getattr(args, "container_runtime", None)
        )
    if hasattr(args, "resource_dir"):
        args.resource_dir = resolve_resource_dir(
            config=config, cli_resource_dir=getattr(args, "resource_dir", None)
        )

    # If no command specified, show help and exit (deterministic default behavior)
    if not args.command:
        if getattr(args, "interactive", False):
            return run_interactive_mode()
        parser.print_help()
        return 0

    # Check if interactive mode requested for specific command
    if hasattr(args, "interactive") and args.interactive:
        return run_interactive_command(args.command)

    # Dispatch to appropriate command handlers
    if args.command == "process":
        return run_process_command(args)
    if args.command == "check-deps":
        return run_check_deps_command(args)
    if hasattr(args, "func"):
        return args.func(args)

    # If we reach here, something went wrong with command dispatch
    parser.print_help()
    return 1


def run_interactive_mode():
    """
    Run HyRISE in fully interactive mode, guiding the user through all options.

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    if not QUESTIONARY_AVAILABLE:
        logger.error("Interactive mode requires the 'questionary' package.")
        logger.error("Please install it with: pip install questionary")
        return 1

    logger.info("Welcome to the interactive HyRISE interface!")

    # Ask which command to run
    command = questionary.select(
        "What would you like to do?",
        choices=[
            {"name": "Process Sierra JSON file", "value": "process"},
            {"name": "Run SierraLocal on FASTA files", "value": "sierra"},
            {"name": "Build Singularity container", "value": "container"},
            {"name": "Check dependencies", "value": "check-deps"},
            {"name": "Exit", "value": "exit"},
        ],
        style=CUSTOM_STYLE,
    ).ask()

    if command == "exit" or command is None:
        return 0

    # Run the specific interactive command
    return run_interactive_command(command)


def run_interactive_command(command):
    """
    Run a specific command in interactive mode.

    Args:
        command: The command to run interactively

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    if not QUESTIONARY_AVAILABLE:
        logger.error("Interactive mode requires the 'questionary' package.")
        logger.error("Please install it with: pip install questionary")
        return 1

    if command == "process":
        return run_interactive_process()
    elif command == "sierra":
        return sierra.run_interactive_sierra()
    elif command == "container":
        return container.run_interactive_container()
    elif command == "check-deps":
        return run_interactive_check_deps()
    else:
        logger.error(f"Unknown command: {command}")
        return 1


def run_interactive_process():
    """
    Run the process command interactively.

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    # Get input file
    input_file = questionary.path(
        "Sierra JSON file path:",
        style=CUSTOM_STYLE,
        validate=lambda x: os.path.isfile(x) or "File doesn't exist",
    ).ask()

    if not input_file:
        return 1

    # Get output directory
    default_output = os.path.splitext(input_file)[0] + "_output"
    output_dir = questionary.path(
        "Output directory:", default=default_output, style=CUSTOM_STYLE
    ).ask()

    if not output_dir:
        return 1

    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        create_dir = questionary.confirm(
            f"Directory '{output_dir}' doesn't exist. Create it?",
            default=True,
            style=CUSTOM_STYLE,
        ).ask()

        if create_dir:
            os.makedirs(output_dir, exist_ok=True)
        else:
            return 1

    # Get sample name
    default_sample = os.path.splitext(os.path.basename(input_file))[0]
    use_custom_sample = questionary.confirm(
        "Use a custom sample name?", default=False, style=CUSTOM_STYLE
    ).ask()

    sample_name = None
    if use_custom_sample:
        sample_name = questionary.text(
            "Sample name:", default=default_sample, style=CUSTOM_STYLE
        ).ask()

    # Get report options
    report = questionary.confirm(
        "Generate MultiQC configuration file?", default=True, style=CUSTOM_STYLE
    ).ask()

    run_multiqc = False
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

    contact_email = None
    if report:
        use_email = questionary.confirm(
            "Include contact email in report?", default=False, style=CUSTOM_STYLE
        ).ask()

        if use_email:
            contact_email = questionary.text("Contact email:", style=CUSTOM_STYLE).ask()

    # Get container options
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

    use_container = None
    if container_option == "container":
        use_container = True
    elif container_option == "no-container":
        use_container = False

    container_path = None
    if use_container and not deps["container_path"]:
        use_custom_container = questionary.confirm(
            "Specify custom container path?", default=False, style=CUSTOM_STYLE
        ).ask()

        if use_custom_container:
            container_path = questionary.path(
                "Container path:",
                style=CUSTOM_STYLE,
                validate=lambda x: os.path.isfile(x) or "File doesn't exist",
            ).ask()

    # Confirm and run
    logger.info("\nProcessing with the following options:")
    logger.info(f"Input file: {input_file}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Sample name: {sample_name or 'Auto-detected'}")
    logger.info(f"Generate report: {report}")
    logger.info(f"Run MultiQC: {run_multiqc}")
    logger.info(f"Include guides: {guide}")
    logger.info(f"Include sample info: {sample_info}")
    logger.info(f"Contact email: {contact_email or 'None'}")
    logger.info(f"Container usage: {container_option}")

    confirm = questionary.confirm(
        "Proceed with processing?", default=True, style=CUSTOM_STYLE
    ).ask()

    if not confirm:
        logger.info("Operation cancelled.")
        return 0

    try:
        results = process_files(
            input_file,
            output_dir,
            sample_name=sample_name,
            generate_report=report,
            run_multiqc=run_multiqc,
            guide=guide,
            sample_info=sample_info,
            contact_email=contact_email,
            logo_path=None,  # Could add logo option if needed
            use_container=use_container,
            container_path=container_path,
            container_runtime=None,
        )

        # Print summary
        if report and run_multiqc and results.get("report_dir"):
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


def run_interactive_check_deps():
    """
    Run the check-deps command interactively.

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    deps = ensure_dependencies(required_tools=["multiqc", "sierralocal"])

    logger.info("\nDependency Check Results:")
    logger.info("-------------------------")
    logger.info(f"MultiQC available: {deps['multiqc_available']}")
    logger.info(f"SierraLocal available: {deps['sierra_local_available']}")
    runtime_name = deps.get("runtime_name") or "none"
    logger.info(
        f"Container runtime available: {deps['singularity_available']} ({runtime_name})"
    )

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
                "\nMissing dependencies can be handled using the container runtime."
            )
            logger.info("Use the --container flag to enable container execution.")
        else:
            logger.info(
                "\nPlease install missing dependencies or provide a container image."
            )
            logger.info(
                "Pull a prebuilt image with: hyrise container --pull -o hyrise.sif"
            )

            build_container = questionary.confirm(
                "Would you like to build the container now?",
                default=True,
                style=CUSTOM_STYLE,
            ).ask()

            if build_container:
                return run_interactive_command("container")
    else:
        logger.info("\nAll dependencies are satisfied. Native execution is possible.")

    return 0


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

    input_files = []
    if getattr(args, "input", None):
        input_files.append(args.input)
    input_files.extend(getattr(args, "inputs", []))
    input_files = [path for path in input_files if path]

    if not input_files:
        logger.error(
            "Error: no input JSON provided. Use -i/--input or positional input."
        )
        return 1

    overall_success = True
    for input_file in input_files:
        try:
            results = process_files(
                input_file,
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
                container_runtime=getattr(args, "container_runtime", None),
            )

            if not results.get("success", True):
                logger.error(f"Error: {results.get('error', 'processing failed')}")
                overall_success = False
                continue

            # Print summary
            if args.report and args.run_multiqc and results.get("report_dir"):
                logger.info("\nSummary:")
                logger.info(f"- Report generated at: {results['report_dir']}")
                logger.info(f"- Files processed: {len(results['files_generated'])}")
                if results["container_used"]:
                    logger.info("- Execution mode: Container")
                else:
                    logger.info("- Execution mode: Native")
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            overall_success = False

        if len(input_files) > 1:
            logger.info(f"Completed processing input: {input_file}")

    return 0 if overall_success else 1


def run_check_deps_command(args):
    """
    Run the check-deps command

    Args:
        args: Parsed command-line arguments

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    # Check if interactive mode is requested
    if hasattr(args, "interactive") and args.interactive:
        return run_interactive_check_deps()

    deps = ensure_dependencies(
        required_tools=["multiqc", "sierralocal"],
        container_path=getattr(args, "container_path", None),
        container_runtime=getattr(args, "container_runtime", None),
    )

    logger.info("\nDependency Check Results:")
    logger.info("-------------------------")
    logger.info(f"MultiQC available: {deps['multiqc_available']}")
    logger.info(f"SierraLocal available: {deps['sierra_local_available']}")
    runtime_name = deps.get("runtime_name") or "none"
    logger.info(
        f"Container runtime available: {deps['singularity_available']} ({runtime_name})"
    )

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
                "\nMissing dependencies can be handled using the container runtime."
            )
            logger.info("Use the --container flag to enable container execution.")
        else:
            logger.info(
                "\nPlease install missing dependencies or provide a container image."
            )
            logger.info(
                "Pull a prebuilt image with: hyrise container --pull -o hyrise.sif"
            )
    else:
        logger.info("\nAll dependencies are satisfied. Native execution is possible.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
