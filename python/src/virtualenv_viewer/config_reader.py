"""Configuration file reader for virtualenv environments.

Reads pyvenv.cfg and postactivate files from a virtualenv directory,
returning their contents as raw text. Missing or unreadable files are
silently skipped (no error displayed to the user).
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ConfigFiles:
    """Container for virtualenv configuration file contents.

    Attributes:
        pyvenv_cfg: Raw text of pyvenv.cfg, or None if missing/unreadable.
        postactivate: Raw text of bin/postactivate, or None if missing/unreadable.
        postactivate_path: Expected path to the postactivate file (for editor support).
        postactivate_mtime: Modification timestamp of postactivate, or None if unavailable.
    """

    pyvenv_cfg: str | None
    postactivate: str | None
    postactivate_path: Path
    postactivate_mtime: float | None


def _read_file_safe(path: Path) -> str | None:
    """Read a file's text content, returning None on any failure.

    Silently handles missing files, permission errors, and I/O errors.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None


def _get_mtime_safe(path: Path) -> float | None:
    """Get a file's modification time, returning None on any failure."""
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def read_configs(venv_path: Path) -> ConfigFiles:
    """Read configuration files from a virtualenv directory.

    Reads pyvenv.cfg from the virtualenv root and postactivate from
    the bin/ directory. Missing or unreadable files result in None
    values without any error output.

    Args:
        venv_path: Path to the virtualenv root directory.

    Returns:
        A ConfigFiles dataclass with the raw file contents and metadata.
    """
    pyvenv_cfg_path = venv_path / "pyvenv.cfg"
    postactivate_path = venv_path / "bin" / "postactivate"

    pyvenv_cfg = _read_file_safe(pyvenv_cfg_path)
    postactivate = _read_file_safe(postactivate_path)
    postactivate_mtime = _get_mtime_safe(postactivate_path)

    return ConfigFiles(
        pyvenv_cfg=pyvenv_cfg,
        postactivate=postactivate,
        postactivate_path=postactivate_path,
        postactivate_mtime=postactivate_mtime,
    )
