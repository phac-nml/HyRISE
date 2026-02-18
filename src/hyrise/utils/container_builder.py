#!/usr/bin/env python3
"""
HyRISE Container Builder

This script facilitates building the Singularity container for HyRISE.
It can be run as a standalone script after package installation to build
the Singularity container from the provided definition file.
"""

import os
import sys
import shutil
import subprocess
import tempfile
import argparse
import logging
from importlib import resources
from pathlib import Path

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
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("hyrise-builder")


def find_singularity_binary():
    """
    Find the Singularity or Apptainer binary on the system.

    Returns:
        str: Path to the Singularity or Apptainer binary, or None if not found
    """
    # Try Singularity first, then Apptainer (the new name for Singularity)
    for binary in ["singularity", "apptainer"]:
        path = shutil.which(binary)
        if path:
            # Verify it's executable and can run
            try:
                result = subprocess.run(
                    [path, "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    logger.info(f"Found {binary}: {result.stdout.strip()}")
                    return path
            except Exception as e:
                logger.debug(f"Error checking {binary} version: {e}")
                continue

    return None


def get_resource_file_path(resource_name: str):
    """
    Get the path to a packaged HyRISE resource file.

    Args:
        resource_name: Packaged file name under the ``hyrise`` package.

    Returns:
        str: Absolute path to the resource file, or None if not found.
    """
    try:
        resource_file = resources.files("hyrise").joinpath(resource_name)
        if resource_file.is_file():
            return str(resource_file)
    except Exception:
        logger.warning(f"Could not locate packaged resource: {resource_name}")

    # Fallbacks for source-tree execution
    cwd_candidate = os.path.abspath(resource_name)
    if os.path.exists(cwd_candidate):
        return cwd_candidate

    package_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    package_candidate = os.path.join(package_root, resource_name)
    if os.path.exists(package_candidate):
        return package_candidate

    return None


def get_def_file_path():
    """
    Get the path to the HyRISE definition file.

    Returns:
        str: Path to the HyRISE definition file
    """
    return get_resource_file_path("hyrise.def")


def get_dockerfile_path():
    """
    Get the path to a packaged runtime Dockerfile.

    Preference order:
    1) Dockerfile.runtime (standalone, pip-install-friendly)
    2) Dockerfile (repository build Dockerfile)
    """
    return get_resource_file_path("Dockerfile.runtime") or get_resource_file_path(
        "Dockerfile"
    )


def build_container_in_def_directory(
    def_file_path, output_name=None, singularity_path=None, sudo=False, force=False
):
    """
    Build the Singularity container in the same directory as the definition file.

    Args:
        def_file_path: Path to the definition file
        output_name: Optional name for the output file (default: uses the .sif extension)
        singularity_path: Path to the Singularity/Apptainer binary
        sudo: Whether to use sudo for building
        force: Whether to force rebuild

    Returns:
        Tuple of (success_status, output_path)
    """
    # Find singularity binary if not provided
    if not singularity_path:
        singularity_path = find_singularity_binary()
        if not singularity_path:
            logger.error("Could not find Singularity or Apptainer on your system.")
            return False, None

    # Determine output path in the same directory as the def file
    def_dir = os.path.dirname(os.path.abspath(def_file_path))
    def_basename = os.path.basename(def_file_path)

    # If an output name is provided, use it
    if output_name:
        output_path = os.path.join(def_dir, output_name)
    else:
        # Otherwise, replace the .def extension with .sif
        output_path = os.path.join(def_dir, def_basename.replace(".def", ".sif"))

    logger.info(f"Building container in the same directory as the definition file")
    logger.info(f"Definition file: {def_file_path}")
    logger.info(f"Output container: {output_path}")

    # Build the container
    build_success = build_container(
        def_file_path, output_path, singularity_path, sudo=sudo, force=force
    )

    return build_success, output_path


def copy_file_to_directory(target_dir, source_file_path, output_name=None):
    """
    Copy a file to a specified directory.

    Args:
        target_dir: Target directory.
        source_file_path: Source file path.
        output_name: Optional destination file name.

    Returns:
        str: Path to copied file, or None on failure.
    """
    destination_name = output_name or os.path.basename(source_file_path)
    target_path = os.path.join(target_dir, destination_name)
    try:
        os.makedirs(target_dir, exist_ok=True)
        shutil.copy2(source_file_path, target_path)
        logger.info(f"Copied file to {target_path}")
        return target_path
    except Exception as e:
        logger.error(f"Failed to copy file '{source_file_path}': {e}")
        return None


def copy_def_file_to_directory(target_dir, def_file_path):
    """
    Copy the definition file to a specified directory.

    Args:
        target_dir (str): Target directory
        def_file_path (str): Path to the definition file

    Returns:
        str: Path to the copied definition file
    """
    return copy_file_to_directory(target_dir, def_file_path, output_name="hyrise.def")


def build_container(
    def_file_path, output_path, singularity_path, sudo=False, force=False
):
    """
    Build the Singularity container using the definition file.

    Args:
        def_file_path (str): Path to the definition file
        output_path (str): Path where the container should be saved
        singularity_path (str): Path to the Singularity binary
        sudo (bool): Whether to use sudo when building the container
        force (bool): Whether to force rebuild if the container already exists

    Returns:
        bool: True if the build was successful, False otherwise
    """
    if os.path.exists(output_path) and not force:
        logger.info(
            f"Container already exists at {output_path}. Use --force to rebuild."
        )
        return True

    # Prepare the build command
    cmd = []
    if sudo:
        cmd.append("sudo")

    cmd.extend(
        [
            singularity_path,
            "build",
        ]
    )

    if force:
        cmd.append("--force")

    cmd.extend([output_path, def_file_path])

    logger.info(f"Building container with command: {' '.join(cmd)}")
    logger.info(
        "This may take some time depending on your internet connection and system..."
    )

    try:
        # Run the build command
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line buffered
        )

        # Stream the output while the process is running
        for line in iter(process.stdout.readline, ""):
            logger.info(line.strip())

        # Wait for the process to complete and get the return code
        return_code = process.wait()

        if return_code == 0:
            logger.info(f"Successfully built container at {output_path}")
            return True
        else:
            logger.error(f"Failed to build container, return code: {return_code}")
            return False

    except Exception as e:
        logger.error(f"Error building container: {e}")
        return False


def pull_container_image(
    image_ref: str,
    output_path: str,
    singularity_path: str = None,
    force: bool = False,
) -> bool:
    """
    Pull a prebuilt OCI image into a local SIF file.
    """
    if not singularity_path:
        singularity_path = find_singularity_binary()
        if not singularity_path:
            logger.error("Could not find Singularity or Apptainer on your system.")
            return False

    source = image_ref if image_ref.startswith("docker://") else f"docker://{image_ref}"
    cmd = [singularity_path, "pull"]
    if force:
        cmd.append("--force")
    cmd.extend([output_path, source])

    logger.info(f"Pulling prebuilt image with command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode == 0:
            logger.info(f"Successfully pulled container to {output_path}")
            return True
        logger.error(f"Failed to pull container, return code: {result.returncode}")
        return False
    except Exception as e:
        logger.error(f"Error pulling container image: {e}")
        return False


def verify_container(container_path, singularity_path):
    """
    Verify the container was built correctly by running a test command.

    Args:
        container_path (str): Path to the container
        singularity_path (str): Path to the Singularity binary

    Returns:
        bool: True if the verification was successful, False otherwise
    """
    if not os.path.exists(container_path):
        logger.error(f"Container file not found at {container_path}")
        return False

    logger.info("Verifying container...")

    # Run a simple test command to verify the container works
    try:
        # Run the built-in test section of the container
        test_cmd = [singularity_path, "test", container_path]
        test_result = subprocess.run(
            test_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        if test_result.returncode == 0:
            logger.info("Container verification passed!")
            return True
        else:
            logger.warning(
                f"Container test returned non-zero code: {test_result.returncode}"
            )
            logger.warning(f"Output: {test_result.stdout}")
            logger.warning(f"Error: {test_result.stderr}")

            # Even if the test fails, try running a basic command to see if the container works
            check_cmd = [
                singularity_path,
                "exec",
                container_path,
                "multiqc",
                "--version",
            ]
            check_result = subprocess.run(
                check_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            if check_result.returncode == 0:
                logger.info(
                    "Basic functionality check passed. Container seems to work."
                )
                return True
            else:
                logger.error("Both test and basic functionality check failed.")
                return False

    except Exception as e:
        logger.error(f"Error verifying container: {e}")
        return False


def run_interactive_container_builder():
    """
    Run the container builder in interactive mode.

    Returns:
        int: Exit code (0 for success, non-zero for errors)
    """
    if not QUESTIONARY_AVAILABLE:
        logger.error("Interactive mode requires 'questionary' package.")
        logger.error("Please install it with: pip install questionary")
        return 1

    print("\n=== HyRISE Container Builder (Interactive Mode) ===\n")

    # Step 1: Check for Singularity/Apptainer
    singularity_path = find_singularity_binary()
    if not singularity_path:
        logger.error(
            "Could not find Singularity or Apptainer on your system. "
            "Please install it before building the container."
        )
        return 1

    logger.info(f"Using Singularity/Apptainer: {singularity_path}")

    # Step 2: Find the definition file
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

    # Step 3: Options for building
    action = questionary.select(
        "What would you like to do?",
        choices=[
            {"name": "Build container", "value": "build"},
            {"name": "Extract definition file only", "value": "extract"},
        ],
        style=CUSTOM_STYLE,
    ).ask()

    if action == "extract":
        extract_dir = questionary.path(
            "Directory to extract definition file to:", style=CUSTOM_STYLE
        ).ask()

        if not extract_dir:
            logger.error("Extract directory is required.")
            return 1

        extract_path = os.path.abspath(extract_dir)
        copied_path = copy_def_file_to_directory(extract_path, def_file_path)

        if copied_path:
            logger.info(f"Definition file extracted to: {copied_path}")
            return 0
        else:
            logger.error("Failed to extract definition file.")
            return 1

    # Step 4: Container build configuration
    output_name = questionary.text(
        "Output container name:", default="hyrise.sif", style=CUSTOM_STYLE
    ).ask()

    sudo = questionary.confirm(
        "Use sudo when building the container? (required on some systems)",
        default=False,
        style=CUSTOM_STYLE,
    ).ask()

    force = questionary.confirm(
        "Force rebuild even if the container already exists?",
        default=True,
        style=CUSTOM_STYLE,
    ).ask()

    build_elsewhere = questionary.confirm(
        "Build the container in a different location than the definition file?",
        default=False,
        style=CUSTOM_STYLE,
    ).ask()

    # Step 5: Confirm and build
    logger.info("\nContainer build configuration:")
    logger.info(f"Definition file: {def_file_path}")
    logger.info(f"Output container: {output_name}")
    logger.info(f"Use sudo: {sudo}")
    logger.info(f"Force rebuild: {force}")
    logger.info(f"Build elsewhere: {build_elsewhere}")

    proceed = questionary.confirm(
        "Proceed with building the container?", default=True, style=CUSTOM_STYLE
    ).ask()

    if not proceed:
        logger.info("Container build cancelled.")
        return 0

    # Build the container
    if build_elsewhere:
        # Build at specified location
        output_path = os.path.abspath(output_name)

        build_success = build_container(
            def_file_path,
            output_path,
            singularity_path,
            sudo=sudo,
            force=force,
        )

        if not build_success:
            logger.error("Container build failed. Check the logs for details.")
            return 1

        # Verify the container
        verify_success = verify_container(output_path, singularity_path)
    else:
        # Build in same directory as definition file
        build_success, output_path = build_container_in_def_directory(
            def_file_path,
            output_name=output_name,
            singularity_path=singularity_path,
            sudo=sudo,
            force=force,
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
        logger.info(f"  hyrise process --container --container-path {output_path} ...")
        return 0
    else:
        logger.warning(
            f"Container was built but verification failed. "
            f"The container may still work, but proceed with caution."
        )
        return 1


def install_container(
    def_file=None, output_path=None, sudo=False, force=False, interactive=False
):
    """
    Build and install the Singularity container.

    Args:
        def_file (str, optional): Path to the Singularity definition file.
            If None, use the default def file from the package.
        output_path (str, optional): Path where the container should be saved.
            If None, install in the package directory.
        sudo (bool): Whether to use sudo when building the container
        force (bool): Whether to force rebuild if the container already exists
        interactive (bool): Whether to use interactive mode

    Returns:
        dict: Results of the container installation
    """
    results = {"success": False, "container_path": None, "error": None, "message": None}

    # If interactive mode is requested, run the interactive builder
    if interactive:
        if not QUESTIONARY_AVAILABLE:
            results["error"] = "Interactive mode requires 'questionary' package"
            results["message"] = "Please install it with: pip install questionary"
            return results

        exit_code = run_interactive_container_builder()
        if exit_code == 0:
            results["success"] = True
            results["message"] = "Container successfully built in interactive mode"
        else:
            results["error"] = "Container build failed"
            results["message"] = "Check the logs for details"

        return results

    # Check if Singularity is installed
    singularity_path = find_singularity_binary()
    if not singularity_path:
        results["error"] = "Singularity or Apptainer is not installed"
        results["message"] = (
            "Please install Singularity or Apptainer before building the container"
        )
        return results

    # Find the def file
    if not def_file:
        def_file_path = get_def_file_path()
        if not def_file_path:
            results["error"] = "Definition file not found"
            results["message"] = "Could not find the HyRISE definition file"
            return results
    else:
        def_file_path = def_file

    # Determine output path
    if not output_path:
        # If no output path is specified, build in the same directory as the def file
        build_success, container_path = build_container_in_def_directory(
            def_file_path, singularity_path=singularity_path, sudo=sudo, force=force
        )
    else:
        # Build at the specified location
        container_path = output_path
        build_success = build_container(
            def_file_path, container_path, singularity_path, sudo=sudo, force=force
        )

    if not build_success:
        results["error"] = "Container build failed"
        results["message"] = "Check the logs for details"
        return results

    # Verify the container
    verify_success = verify_container(container_path, singularity_path)

    if verify_success:
        results["success"] = True
        results["container_path"] = container_path
        results["message"] = (
            f"Container successfully built and verified at {container_path}"
        )
    else:
        results["success"] = False
        results["container_path"] = container_path
        results["error"] = "Container verification failed"
        results["message"] = (
            "The container was built but verification failed. It may still work, but proceed with caution."
        )

    return results


def main():
    """Main entry point for the container builder."""
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
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode with guided prompts",
    )

    args = parser.parse_args()

    # Check if interactive mode is requested
    if args.interactive:
        return run_interactive_container_builder()

    # Set up verbose logging if requested
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

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

        if not build_success:
            logger.error("Container build failed. Check the logs for details.")
            return 1
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


if __name__ == "__main__":
    sys.exit(main())
