"""Module entrypoint for ``python -m hyrise``."""

from hyrise.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
