#!/usr/bin/env python3
"""
HyRISE Resource Updater

This module provides functionality to update HIVdb resources used by HyRISE and SierraLocal,
including the HIVdb XML algorithm file, APOBEC mutation files, and other reference data.
"""

import os
import sys
import argparse
import requests
import logging
import re
from pathlib import Path

from hyrise.config import load_config, resolve_resource_dir

# Set up logging
logger = logging.getLogger("hyrise-resources")
_HIVDB_XML_RE = re.compile(r"^HIVDB_(\d+(?:\.\d+)*)\.xml$")


def _safe_filename(filename: str) -> str:
    """
    Validate and normalize a leaf filename.

    Rejects absolute paths, traversal segments, and directory separators.
    """
    candidate = Path(str(filename).strip())
    if not candidate.name or candidate.name in {".", ".."}:
        raise ValueError("Invalid filename")
    if candidate.name != str(filename).strip():
        raise ValueError(f"Unsafe filename: {filename}")
    return candidate.name


def _safe_resource_path(resource_dir: Path, filename: str) -> Path:
    """
    Build a normalized path under ``resource_dir`` and ensure it cannot escape.
    """
    safe_name = _safe_filename(filename)
    root = resource_dir.resolve()
    target = (root / safe_name).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Unsafe resource path for filename: {filename}") from exc
    return target


def _hivdb_version_tuple(path: Path):
    """
    Parse `HIVDB_<version>.xml` into a comparable version tuple.

    Returns None for non-matching filenames.
    """
    match = _HIVDB_XML_RE.match(path.name)
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def select_latest_hivdb_xml(xml_paths):
    """
    Select the highest-version HIVDB XML path from an iterable of Paths.

    Version ordering is numeric (`10.1` > `9.9`), not lexical.
    """
    candidates = []
    for path in xml_paths:
        version = _hivdb_version_tuple(Path(path))
        if version is None:
            continue
        candidates.append((version, Path(path)))

    if not candidates:
        return None

    # Tie-break on filename for deterministic behavior if versions are equal.
    candidates.sort(key=lambda item: (item[0], item[1].name))
    return candidates[-1][1]


# Define resource directory
def get_resource_dir(resource_dir=None, config=None):
    """
    Resolve and create the writable resources directory.
    """
    resolved_dir = Path(
        resolve_resource_dir(config or {}, cli_resource_dir=resource_dir)
    )
    resolved_dir.mkdir(parents=True, exist_ok=True)
    return resolved_dir


def download_file(url, filename, resource_dir=None, config=None):
    """
    Download a file from a URL to the resources directory

    Args:
        url: URL to download from
        filename: Name to save the file as
        resource_dir: Optional directory override.
        config: Optional loaded HyRISE config dictionary.

    Returns:
        Path to downloaded file or None if download failed
    """
    if resource_dir is None:
        resource_dir = get_resource_dir(config=config)
    else:
        resource_dir = get_resource_dir(resource_dir=resource_dir, config=config)

    try:
        filepath = _safe_resource_path(resource_dir, filename)
    except ValueError as e:
        logger.error(str(e))
        return None

    try:
        logger.info(f"Downloading {filename} from {url}")
        response = requests.get(url, allow_redirects=True, timeout=60)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses

        with open(filepath, "wb") as file:
            file.write(response.content)

        logger.info(f"Successfully downloaded to {filepath}")
        return filepath

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download {filename}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error saving {filename}: {str(e)}")
        return None


def update_hivdb_xml(resource_dir=None, config=None):
    """
    Update the HIVdb algorithm XML file

    Returns:
        Path to the updated XML file or None if update failed
    """
    try:
        # First query for the latest filename
        url = "https://raw.githubusercontent.com/hivdb/hivfacts/main/data/algorithms/HIVDB_latest.xml"
        response = requests.get(url)
        response.raise_for_status()
        latest_filename = _safe_filename(response.text.strip())
        if not _HIVDB_XML_RE.match(latest_filename):
            raise ValueError(
                f"Unexpected HIVDB latest filename format: {latest_filename}"
            )

        # Now download the actual file
        download_url = f"https://raw.githubusercontent.com/hivdb/hivfacts/main/data/algorithms/{latest_filename}"
        return download_file(
            download_url, latest_filename, resource_dir=resource_dir, config=config
        )

    except Exception as e:
        logger.error(f"Error updating HIVdb XML: {str(e)}")
        return None


def update_apobec_drms(resource_dir=None, config=None):
    """
    Update the APOBEC DRMs JSON file

    Returns:
        Path to the updated JSON file or None if update failed
    """
    url = "https://raw.githubusercontent.com/hivdb/hivfacts/main/data/apobecs/apobec_drms.json"
    return download_file(
        url, "apobec_drms.json", resource_dir=resource_dir, config=config
    )


def update_apobec_data(resource_dir=None, config=None):
    """
    Update the APOBEC data CSV file

    Returns:
        Path to the updated CSV file or None if update failed
    """
    url = (
        "https://raw.githubusercontent.com/hivdb/hivfacts/main/data/apobecs/apobecs.csv"
    )
    return download_file(url, "apobecs.csv", resource_dir=resource_dir, config=config)


def update_mutation_data(resource_dir=None, config=None):
    """
    Update mutation type pairs CSV file

    Returns:
        Path to the updated CSV file or None if update failed
    """
    url = "https://raw.githubusercontent.com/hivdb/hivfacts/main/data/mutation-type-pairs_hiv1.csv"
    return download_file(
        url, "mutation-type-pairs_hiv1.csv", resource_dir=resource_dir, config=config
    )


def update_sdrm_data(resource_dir=None, config=None):
    """
    Update SDRM mutations CSV file

    Returns:
        Path to the updated CSV file or None if update failed
    """
    url = "https://raw.githubusercontent.com/hivdb/hivfacts/main/data/sdrms_hiv1.csv"
    return download_file(
        url, "sdrms_hiv1.csv", resource_dir=resource_dir, config=config
    )


def update_unusual_data(resource_dir=None, config=None):
    """
    Update unusual mutations data CSV file

    Returns:
        Path to the updated CSV file or None if update failed
    """
    url = "https://raw.githubusercontent.com/hivdb/hivfacts/2021.3/data/aapcnt/rx-all_subtype-all.csv"
    return download_file(
        url, "rx-all_subtype-all.csv", resource_dir=resource_dir, config=config
    )


def update_all_resources(resource_dir=None, config=None):
    """
    Update all HIVdb resources

    Returns:
        dict: Results with paths to successfully updated files and any errors
    """
    results = {"success": True, "updated_files": {}, "errors": []}

    # Define all update functions to run
    updates = [
        ("hivdb_xml", update_hivdb_xml),
        ("apobec_drms", update_apobec_drms),
        ("apobec_data", update_apobec_data),
        ("mutation_data", update_mutation_data),
        ("sdrm_data", update_sdrm_data),
        ("unusual_data", update_unusual_data),
    ]

    # Run each update function
    for name, func in updates:
        try:
            result = func(resource_dir=resource_dir, config=config)
            if result:
                results["updated_files"][name] = str(result)
            else:
                results["success"] = False
                results["errors"].append(f"Failed to update {name}")
        except Exception as e:
            results["success"] = False
            results["errors"].append(f"Error updating {name}: {str(e)}")

    return results


def get_latest_resource_path(resource_type, resource_dir=None, config=None):
    """
    Get the path to the latest version of a specific resource

    Args:
        resource_type: Type of resource to find (e.g., 'hivdb_xml', 'apobec_drms')

    Returns:
        Path to the resource or None if not found
    """
    resource_dir = get_resource_dir(resource_dir=resource_dir, config=config)

    if resource_type == "hivdb_xml":
        latest_xml = select_latest_hivdb_xml(resource_dir.glob("HIVDB_*.xml"))
        return str(latest_xml) if latest_xml else None

    elif resource_type == "apobec_drms":
        path = resource_dir / "apobec_drms.json"
        return str(path) if path.exists() else None

    elif resource_type == "apobec_data":
        path = resource_dir / "apobecs.csv"
        return str(path) if path.exists() else None

    elif resource_type == "mutation_data":
        path = resource_dir / "mutation-type-pairs_hiv1.csv"
        return str(path) if path.exists() else None

    elif resource_type == "sdrm_data":
        path = resource_dir / "sdrms_hiv1.csv"
        return str(path) if path.exists() else None

    elif resource_type == "unusual_data":
        path = resource_dir / "rx-all_subtype-all.csv"
        return str(path) if path.exists() else None

    return None


# Command-line interface functions
def add_resources_subparser(subparsers):
    """
    Add the resources subcommand to the main parser
    """
    resources_parser = subparsers.add_parser(
        "resources",
        help="Manage HIV database resources for HyRISE",
        description="Update and manage HIV database resources including HIVdb algorithm XML and other reference data",
    )

    resources_parser.add_argument(
        "--update-all", action="store_true", help="Update all HIV database resources"
    )

    resources_parser.add_argument(
        "--update-hivdb", action="store_true", help="Update HIVdb algorithm XML file"
    )

    resources_parser.add_argument(
        "--update-apobec", action="store_true", help="Update APOBEC data files"
    )

    resources_parser.add_argument(
        "--list", action="store_true", help="List all available resources"
    )

    resources_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    resources_parser.add_argument(
        "--resource-dir",
        help="Directory to store updated resource files",
    )

    resources_parser.add_argument(
        "--config",
        help="Path to HyRISE config TOML file",
    )

    resources_parser.set_defaults(func=run_resources_command)


def run_resources_command(args):
    """
    Run the resources command
    """
    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    config = load_config(getattr(args, "config", None))
    resource_dir = resolve_resource_dir(
        config=config,
        cli_resource_dir=getattr(args, "resource_dir", None),
    )

    # List resources if requested
    if args.list:
        list_resources(resource_dir=resource_dir, config=config)
        return 0

    # Update HIVdb XML if requested
    if args.update_hivdb:
        result = update_hivdb_xml(resource_dir=resource_dir, config=config)
        if result:
            logger.info(f"Successfully updated HIVdb XML to: {result}")
        else:
            logger.error("Failed to update HIVdb XML")
            return 1

    # Update APOBEC data if requested
    if args.update_apobec:
        drms_result = update_apobec_drms(resource_dir=resource_dir, config=config)
        data_result = update_apobec_data(resource_dir=resource_dir, config=config)

        if drms_result and data_result:
            logger.info(f"Successfully updated APOBEC data files")
        else:
            logger.error("Failed to update some APOBEC data files")
            return 1

    # Update all resources if requested
    if args.update_all:
        results = update_all_resources(resource_dir=resource_dir, config=config)

        if results["success"]:
            logger.info("Successfully updated all resources:")
            for name, path in results["updated_files"].items():
                logger.info(f"  - {name}: {path}")
        else:
            logger.error("Failed to update some resources:")
            for error in results["errors"]:
                logger.error(f"  - {error}")
            return 1

    # If no specific action was requested, show help
    if not any([args.list, args.update_hivdb, args.update_apobec, args.update_all]):
        logger.info("No action specified. Use --help to see available options.")

    return 0


def list_resources(resource_dir=None, config=None):
    """
    List all available resources and their status
    """
    resource_dir = get_resource_dir(resource_dir=resource_dir, config=config)
    logger.info(f"Resource directory: {resource_dir}")

    # Define all resource types to check
    resource_types = [
        "hivdb_xml",
        "apobec_drms",
        "apobec_data",
        "mutation_data",
        "sdrm_data",
        "unusual_data",
    ]

    # Check each resource type
    for resource_type in resource_types:
        path = get_latest_resource_path(
            resource_type, resource_dir=resource_dir, config=config
        )
        if path:
            file_size = os.path.getsize(path)
            modified_time = os.path.getmtime(path)
            from datetime import datetime

            modified_str = datetime.fromtimestamp(modified_time).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            logger.info(
                f"  - {resource_type}: {os.path.basename(path)} ({file_size/1024:.1f} KB, updated: {modified_str})"
            )
        else:
            logger.info(f"  - {resource_type}: Not available")


def main():
    """
    Main entry point for standalone execution
    """
    parser = argparse.ArgumentParser(description="HyRISE Resource Manager")

    parser.add_argument(
        "--update-all", action="store_true", help="Update all HIV database resources"
    )

    parser.add_argument(
        "--update-hivdb", action="store_true", help="Update HIVdb algorithm XML file"
    )

    parser.add_argument(
        "--update-apobec", action="store_true", help="Update APOBEC data files"
    )

    parser.add_argument(
        "--list", action="store_true", help="List all available resources"
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    parser.add_argument(
        "--resource-dir",
        help="Directory to store updated resource files",
    )

    parser.add_argument(
        "--config",
        help="Path to HyRISE config TOML file",
    )

    args = parser.parse_args()

    return run_resources_command(args)


if __name__ == "__main__":
    sys.exit(main())
