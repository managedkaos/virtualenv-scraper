"""Virtualenv detection module.

Locates the active Python virtual environment using a prioritized detection strategy.
"""

import os
import sys
from pathlib import Path


def _is_valid_virtualenv(path: Path) -> bool:
    """Check if a directory is a valid virtualenv by verifying pyvenv.cfg exists."""
    return (path / "pyvenv.cfg").is_file()


def detect_virtualenv() -> Path:
    """Detect the active virtualenv using a prioritized search strategy.

    Priority order:
        1. $VIRTUAL_ENV environment variable
        2. $PWD/.env
        3. $PWD/.venv
        4. $PWD/venv
        5. $PWD/env

    Returns the path to the first valid virtualenv found.

    If VIRTUAL_ENV is set but invalid, prints a specific error and exits.
    If no virtualenv is found after all candidates, prints an error listing
    all attempted paths and exits.
    """
    # Check $VIRTUAL_ENV first
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        venv_path = Path(virtual_env)
        if _is_valid_virtualenv(venv_path):
            return venv_path
        # VIRTUAL_ENV is set but invalid — specific error message
        print(
            f"Error: VIRTUAL_ENV is set to '{virtual_env}' "
            "but it is not a valid virtualenv directory",
            file=sys.stderr,
        )
        sys.exit(1)

    # Candidate directories relative to CWD
    cwd = Path.cwd()
    candidates = [
        cwd / ".env",
        cwd / ".venv",
        cwd / "venv",
        cwd / "env",
    ]

    for candidate in candidates:
        if _is_valid_virtualenv(candidate):
            return candidate

    # No valid virtualenv found — error with attempted paths
    attempted = [str(c) for c in candidates]
    print(
        "Error: No valid virtualenv found. Attempted the following paths:\n"
        + "\n".join(f"  {p}" for p in attempted),
        file=sys.stderr,
    )
    sys.exit(1)
