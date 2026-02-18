"""
Utilities for container-based execution and dependency checking.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

from hyrise.config import get_default_data_dir
from .container_builder import verify_container

logger = logging.getLogger("hyrise-container")


def check_dependency_installed(dependency_name: str) -> bool:
    """Check if a Python package is installed."""
    try:
        spec = importlib.util.find_spec(dependency_name)
        return spec is not None
    except (ImportError, ModuleNotFoundError):
        return False


def check_command_available(command: str) -> bool:
    """Check if a command is available in PATH."""
    return shutil.which(command) is not None


def detect_container_runtime(
    preferred_runtime: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve container runtime path.

    Runtime preference order:
    1) explicit preferred runtime (`apptainer` or `singularity`)
    2) `apptainer`
    3) `singularity`
    """
    candidates = []
    if preferred_runtime:
        candidates.append(preferred_runtime)
    for runtime in ("apptainer", "singularity"):
        if runtime not in candidates:
            candidates.append(runtime)

    for runtime in candidates:
        runtime_path = shutil.which(runtime)
        if runtime_path:
            return runtime, runtime_path
    return None, None


def find_singularity_container(
    search_paths: Optional[Iterable[str]] = None,
) -> Optional[str]:
    """
    Find a HyRISE container file from a deterministic path list.
    """
    if search_paths is None:
        search_paths = (
            str((Path.cwd() / "hyrise.sif").resolve()),
            str((get_default_data_dir() / "hyrise.sif").resolve()),
        )

    for path in search_paths:
        if not path:
            continue
        resolved = Path(path).expanduser().resolve()
        if resolved.exists():
            return str(resolved)
    return None


def check_singularity_available(preferred_runtime: Optional[str] = None) -> bool:
    """Check whether a supported container runtime is available."""
    _, runtime_path = detect_container_runtime(preferred_runtime=preferred_runtime)
    return runtime_path is not None


def run_with_singularity(
    container_path: str,
    command: Sequence[str] | str,
    bind_paths: Optional[Sequence[str]] = None,
    runtime_path: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """
    Run a command using an Apptainer/Singularity container.
    """
    if runtime_path is None:
        _, runtime_path = detect_container_runtime()
    if not runtime_path:
        raise ValueError("No supported container runtime found (apptainer/singularity)")

    if not os.path.exists(container_path):
        raise ValueError(f"Container not found at {container_path}")

    if not verify_container(container_path, runtime_path):
        logger.warning(
            "Container verification failed but will attempt to run it anyway"
        )

    argv_command = command.split() if isinstance(command, str) else list(command)
    if not argv_command:
        raise ValueError("Container command cannot be empty")

    bind_targets = [
        Path(p).expanduser().resolve() for p in (bind_paths or [os.getcwd()])
    ]
    bind_args = []
    for target in bind_targets:
        if target.exists():
            bind_args.extend(["--bind", str(target)])

    cmd = [runtime_path, "exec", *bind_args, container_path, *argv_command]
    return subprocess.run(cmd, check=True)


def ensure_dependencies(
    use_container: Optional[bool] = None,
    required_tools: Optional[Iterable[str]] = None,
    container_path: Optional[str] = None,
    container_runtime: Optional[str] = None,
    container_search_paths: Optional[Iterable[str]] = None,
) -> dict:
    """
    Check dependencies and determine whether container execution should be used.

    Args:
        use_container: Explicit execution mode override.
        required_tools: Required tools for the current action.
            Defaults to ``("multiqc", "sierralocal")``.
        container_path: Explicit container path override.
        container_runtime: Preferred runtime binary name.
        container_search_paths: Additional search paths for container discovery.
    """
    runtime_name, runtime_path = detect_container_runtime(
        preferred_runtime=container_runtime
    )

    resolved_container_path = None
    if container_path:
        candidate = Path(container_path).expanduser().resolve()
        if candidate.exists():
            resolved_container_path = str(candidate)
    if resolved_container_path is None:
        resolved_container_path = find_singularity_container(container_search_paths)

    required = (
        tuple(required_tools)
        if required_tools is not None
        else ("multiqc", "sierralocal")
    )
    multiqc_available = check_command_available("multiqc")
    sierra_local_available = check_command_available("sierralocal")

    missing_dependencies = []
    if "multiqc" in required and not multiqc_available:
        missing_dependencies.append("multiqc")
    if "sierralocal" in required and not sierra_local_available:
        missing_dependencies.append("sierralocal")

    if use_container is True:
        resolved_use_container = True
    elif use_container is False:
        resolved_use_container = False
    else:
        resolved_use_container = bool(
            missing_dependencies and runtime_path and resolved_container_path
        )

    return {
        "multiqc_available": multiqc_available,
        "sierra_local_available": sierra_local_available,
        "singularity_available": runtime_path is not None,
        "runtime_name": runtime_name,
        "runtime_path": runtime_path,
        "container_path": resolved_container_path,
        "use_container": resolved_use_container,
        "missing_dependencies": missing_dependencies,
    }
