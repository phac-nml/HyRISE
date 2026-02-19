"""Top-level package for HyRISE.

This module is intentionally lightweight and side-effect free.
It exposes only stable top-level metadata for importers.
"""

# Single source of truth for package version.
# `pyproject.toml` reads this via: [tool.setuptools.dynamic] version.attr.
__version__ = "0.2.3"

# Keep the public top-level Python API intentionally minimal.
__all__ = ["__version__"]
