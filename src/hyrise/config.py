"""Centralized configuration helpers for HyRISE."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - exercised on py<3.11
    import tomli as tomllib  # type: ignore[no-redef]


def get_xdg_config_home() -> Path:
    """Return the XDG config home directory."""
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def get_xdg_data_home() -> Path:
    """Return the XDG data home directory."""
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def get_default_config_path() -> Path:
    """Return the default config file path."""
    return get_xdg_config_home() / "hyrise" / "config.toml"


def get_default_data_dir() -> Path:
    """Return the default persistent data directory."""
    return get_xdg_data_home() / "hyrise"


def _coerce_path(path_value: Optional[str]) -> Optional[Path]:
    if not path_value:
        return None
    return Path(path_value).expanduser().resolve()


def _get_nested(config: Dict[str, Any], dotted_key: str, default: Any = None) -> Any:
    current: Any = config
    for key in dotted_key.split("."):
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load HyRISE TOML config.

    Precedence for selecting the config file location:
    1) explicit ``config_path`` argument
    2) ``HYRISE_CONFIG`` environment variable
    3) XDG default location (``~/.config/hyrise/config.toml``)
    """
    explicit_path = config_path or os.environ.get("HYRISE_CONFIG")
    resolved_path = _coerce_path(explicit_path) or get_default_config_path()

    if not resolved_path.exists():
        return {}

    with resolved_path.open("rb") as handle:
        loaded = tomllib.load(handle)
    return loaded if isinstance(loaded, dict) else {}


def resolve_option(
    cli_value: Any,
    config_value: Any,
    env_var: Optional[str] = None,
    default: Any = None,
) -> Any:
    """
    Resolve a value with precedence:
    CLI > config file > env var > default.
    """
    if cli_value is not None:
        return cli_value
    if config_value is not None:
        return config_value
    if env_var:
        env_value = os.environ.get(env_var)
        if env_value not in (None, ""):
            return env_value
    return default


def resolve_container_path(
    config: Dict[str, Any],
    cli_container_path: Optional[str] = None,
) -> Optional[str]:
    """Resolve container path from CLI/config/env."""
    value = resolve_option(
        cli_container_path,
        _get_nested(config, "container.path"),
        env_var="HYRISE_CONTAINER_PATH",
        default=None,
    )
    resolved = _coerce_path(value)
    return str(resolved) if resolved else None


def resolve_container_runtime(
    config: Dict[str, Any],
    cli_runtime: Optional[str] = None,
) -> Optional[str]:
    """Resolve preferred container runtime binary name."""
    return resolve_option(
        cli_runtime,
        _get_nested(config, "container.runtime"),
        env_var="HYRISE_CONTAINER_RUNTIME",
        default=None,
    )


def resolve_resource_dir(
    config: Dict[str, Any],
    cli_resource_dir: Optional[str] = None,
) -> str:
    """Resolve writable resource directory for downloaded algorithm data."""
    default_dir = str(get_default_data_dir() / "resources")
    value = resolve_option(
        cli_resource_dir,
        _get_nested(config, "resources.dir"),
        env_var="HYRISE_RESOURCES_DIR",
        default=default_dir,
    )
    resolved = _coerce_path(value)
    return str(resolved) if resolved else default_dir


def get_container_search_paths(
    config: Dict[str, Any],
    cli_container_path: Optional[str] = None,
) -> Iterable[str]:
    """
    Return deterministic container search paths.

    Search order:
    1) explicit CLI/config/env container path
    2) current working directory `hyrise.sif`
    3) XDG data directory `~/.local/share/hyrise/hyrise.sif`
    4) optional additional configured paths `container.search_paths`
    """
    seen = set()

    explicit = resolve_container_path(
        config=config, cli_container_path=cli_container_path
    )
    if explicit:
        seen.add(explicit)
        yield explicit

    cwd_candidate = str((Path.cwd() / "hyrise.sif").resolve())
    if cwd_candidate not in seen:
        seen.add(cwd_candidate)
        yield cwd_candidate

    data_candidate = str((get_default_data_dir() / "hyrise.sif").resolve())
    if data_candidate not in seen:
        seen.add(data_candidate)
        yield data_candidate

    extra_paths = _get_nested(config, "container.search_paths", default=[])
    if isinstance(extra_paths, list):
        for extra in extra_paths:
            path_obj = _coerce_path(str(extra))
            if not path_obj:
                continue
            resolved = str(path_obj)
            if resolved not in seen:
                seen.add(resolved)
                yield resolved
