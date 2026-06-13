"""App options / configuration module.

Parses and merges configuration from multiple sources with precedence:
CLI flag > environment variable > config file > default (disabled).
"""

import argparse
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppOptions:
    """Application options resolved from all configuration sources."""

    restart_on_edit: bool = False


def _parse_bool_env(value: str) -> bool | None:
    """Parse a boolean-like environment variable value.

    Accepts: 1, 0, true, false (case-insensitive).
    Returns None if the value is not recognized.
    """
    normalized = value.strip().lower()
    if normalized in ("1", "true"):
        return True
    if normalized in ("0", "false"):
        return False
    return None


def _read_config_file(path: Path | None = None) -> dict[str, object]:
    """Read the TOML config file from the given path or default location.

    Returns an empty dict if the file doesn't exist or can't be parsed.
    """
    if path is None:
        path = Path.home() / ".virtualenv-viewer.toml"

    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (FileNotFoundError, PermissionError, OSError, tomllib.TOMLDecodeError):
        return {}


def parse_options(args: list[str] | None = None) -> AppOptions:
    """Parse application options from CLI, environment, and config file.

    Precedence: CLI > env var > config file > default (disabled).

    Args:
        args: CLI arguments to parse. If None, uses sys.argv[1:].

    Returns:
        Resolved AppOptions instance.
    """
    # --- CLI parsing ---
    parser = argparse.ArgumentParser(
        prog="virtualenv-viewer",
        description="Interactive terminal UI for viewing virtualenv configuration",
    )
    parser.add_argument(
        "--restart-on-edit",
        action="store_true",
        default=None,
        dest="restart_on_edit",
        help="Restart virtualenv after editing postactivate",
    )
    parser.add_argument(
        "--no-restart-on-edit",
        action="store_true",
        default=None,
        dest="no_restart_on_edit",
        help="Do not restart virtualenv after editing postactivate",
    )

    parsed = parser.parse_args(args)

    # Determine CLI value (None means not specified)
    cli_value: bool | None = None
    if parsed.restart_on_edit:
        cli_value = True
    elif parsed.no_restart_on_edit:
        cli_value = False

    # --- Environment variable ---
    env_value: bool | None = None
    env_raw = os.environ.get("VENV_VIEWER_RESTART_ON_EDIT")
    if env_raw is not None:
        env_value = _parse_bool_env(env_raw)

    # --- Config file ---
    config_value: bool | None = None
    config_data = _read_config_file()
    raw_config = config_data.get("restart_on_edit")
    if isinstance(raw_config, bool):
        config_value = raw_config

    # --- Precedence resolution: CLI > env > config > default ---
    if cli_value is not None:
        restart_on_edit = cli_value
    elif env_value is not None:
        restart_on_edit = env_value
    elif config_value is not None:
        restart_on_edit = config_value
    else:
        restart_on_edit = False

    return AppOptions(restart_on_edit=restart_on_edit)
