"""
Utilities for container-based execution and dependency checking
"""

import os
import sys
import subprocess
import importlib.util
import pkg_resources
import site
from pathlib import Path
import logging

from .container_builder import find_singularity_binary, verify_container

# Set up logging
logger = logging.getLogger("hyrise-container")


def check_dependency_installed(dependency_name):
    """
    Check if a Python package is installed in the current environment

    Args:
        dependency_name (str): Name of the dependency to check

    Returns:
        bool: True if installed, False otherwise
    """
    try:
        spec = importlib.util.find_spec(dependency_name)
        return spec is not None
    except (ImportError, ModuleNotFoundError):
        # Try using pkg_resources as a fallback
        try:
            pkg_resources.get_distribution(dependency_name)
            return True
        except pkg_resources.DistributionNotFound:
            return False


def check_command_available(command):
    """
    Check if a command is available in the system PATH

    Args:
        command (str): Command to check

    Returns:
        bool: True if available, False otherwise
    """
    try:
        subprocess.run(
            f"which {command}",
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def find_singularity_container():
    """
    Find the hyrise.sif container in the package installation directory

    Returns:
        str: Path to the Singularity container or None if not found
    """
    # First, check if the container is in the current directory
    if os.path.exists("hyrise.sif"):
        return os.path.abspath("hyrise.sif")

    # Check in the same directory as this script
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sif_path = os.path.join(current_dir, "hyrise.sif")
    if os.path.exists(sif_path):
        return sif_path

    # Check in the package installation directory
    try:
        # Try to find package path using importlib
        spec = importlib.util.find_spec("hyrise")
        if spec and spec.origin:
            pkg_dir = os.path.dirname(os.path.dirname(spec.origin))
            container_path = os.path.join(pkg_dir, "hyrise", "hyrise.sif")
            if os.path.exists(container_path):
                return container_path
    except Exception:
        pass

    # Try using pkg_resources
    try:
        # Get all site-packages directories
        site_packages = site.getsitepackages()
        for site_dir in site_packages:
            # Look for egg or regular package
            for pattern in ["hyrise-*.egg/hyrise/hyrise.sif", "hyrise/hyrise.sif"]:
                # Use glob to find matching paths
                potential_paths = list(Path(site_dir).glob(pattern))
                if potential_paths:
                    return str(potential_paths[0])
    except Exception:
        pass

    # As a last resort, try to find in conda environment
    if "CONDA_PREFIX" in os.environ:
        conda_prefix = os.environ["CONDA_PREFIX"]
        conda_path = os.path.join(
            conda_prefix,
            "lib",
            f"python{sys.version_info.major}.{sys.version_info.minor}",
            "site-packages",
            "hyrise",
            "hyrise.sif",
        )
        if os.path.exists(conda_path):
            return conda_path

    return None


def check_singularity_available():
    """
    Check if Singularity is installed and available

    Returns:
        bool: True if available, False otherwise
    """
    return find_singularity_binary() is not None


def run_with_singularity(container_path, command, bind_paths=None):
    """
    Run a command using Singularity container

    Args:
        container_path (str): Path to the Singularity container file
        command (str): Command to run inside the container
        bind_paths (list, optional): List of paths to bind-mount into container

    Returns:
        subprocess.CompletedProcess: Result of the command execution

    Raises:
        subprocess.CalledProcessError: If the command fails
        ValueError: If Singularity or container not found
    """
    singularity_path = find_singularity_binary()
    if not singularity_path:
        raise ValueError("Singularity is not installed or not in PATH")

    if not os.path.exists(container_path):
        raise ValueError(f"Singularity container not found at {container_path}")

    # Check if container is valid
    if not verify_container(container_path, singularity_path):
        logger.warning(
            "Container verification failed but will attempt to use it anyway"
        )

    # Build bind options
    bind_opts = []
    if bind_paths:
        for path in bind_paths:
            # Ensure path exists
            if os.path.exists(path):
                bind_opts.append(f"--bind {path}")

    # By default bind current directory
    if not bind_opts:
        bind_opts.append(f"--bind {os.getcwd()}")

    # Build the full singularity command
    singularity_cmd = (
        f"{singularity_path} exec {' '.join(bind_opts)} {container_path} {command}"
    )

    # Run the command
    return subprocess.run(singularity_cmd, shell=True, check=True)


def ensure_dependencies(use_container=None):
    """
    Check for required dependencies and determine if container should be used

    Args:
        use_container (bool, optional): Force container usage on/off, or auto-detect if None

    Returns:
        dict: Information about dependencies and container availability
    """
    results = {
        "multiqc_available": check_command_available("multiqc"),
        "sierra_local_available": check_command_available("sierralocal"),
        "singularity_available": check_singularity_available(),
        "container_path": find_singularity_container(),
        "use_container": False,
        "missing_dependencies": [],
    }

    # Check for missing dependencies
    if not results["multiqc_available"]:
        results["missing_dependencies"].append("multiqc")

    if not results["sierra_local_available"]:
        results["missing_dependencies"].append("sierralocal")

    # Determine if container should be used
    if use_container is True:
        # User explicitly requested container
        results["use_container"] = True
    elif use_container is False:
        # User explicitly disabled container
        results["use_container"] = False
    else:
        # Auto-detect based on missing dependencies
        if (
            results["missing_dependencies"]
            and results["singularity_available"]
            and results["container_path"]
        ):
            results["use_container"] = True

    return results
