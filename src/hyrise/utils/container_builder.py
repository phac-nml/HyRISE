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
import pkg_resources
import logging
from pathlib import Path


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


def get_def_file_path():
    """
    Get the path to the HyRISE definition file.

    Returns:
        str: Path to the HyRISE definition file
    """
    try:
        # Try to get the path from the installed package
        def_file = pkg_resources.resource_filename("hyrise", "hyrise.def")
        if os.path.exists(def_file):
            return def_file
    except (ImportError, pkg_resources.DistributionNotFound):
        logger.warning("Could not locate the definition file in the package.")

    # Check if the file exists in the current directory
    if os.path.exists("hyrise.def"):
        return os.path.abspath("hyrise.def")

    # Check if the file exists in the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_def = os.path.join(script_dir, "hyrise.def")
    if os.path.exists(local_def):
        return local_def

    return None


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


def copy_def_file_to_directory(target_dir, def_file_path):
    """
    Copy the definition file to a specified directory.

    Args:
        target_dir (str): Target directory
        def_file_path (str): Path to the definition file

    Returns:
        str: Path to the copied definition file
    """
    target_path = os.path.join(target_dir, "hyrise.def")
    try:
        os.makedirs(target_dir, exist_ok=True)
        shutil.copy2(def_file_path, target_path)
        logger.info(f"Copied definition file to {target_path}")
        return target_path
    except Exception as e:
        logger.error(f"Failed to copy definition file: {e}")
        return None


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


def install_container(def_file=None, output_path=None, sudo=False, force=False):
    """
    Build and install the Singularity container.

    Args:
        def_file (str, optional): Path to the Singularity definition file.
            If None, use the default def file from the package.
        output_path (str, optional): Path where the container should be saved.
            If None, install in the package directory.
        sudo (bool): Whether to use sudo when building the container
        force (bool): Whether to force rebuild if the container already exists

    Returns:
        dict: Results of the container installation
    """
    results = {"success": False, "container_path": None, "error": None, "message": None}

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

    args = parser.parse_args()

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
