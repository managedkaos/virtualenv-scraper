"""Editor Launcher for virtualenv-viewer.

Opens the postactivate file in the user's preferred editor ($EDITOR),
handling pre-launch validation, TUI suspension/resumption, and content
refresh on file modification.
"""

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EditorResult:
    """Result of an editor launch attempt.

    Attributes:
        success: Whether the editor was launched and exited successfully.
        file_modified: Whether the file's mtime changed after editing.
        error_message: Error description if the launch failed, or None on success.
    """

    success: bool
    file_modified: bool
    error_message: str | None = None


def _get_editor() -> str | None:
    """Get the editor command from the $EDITOR environment variable.

    Returns:
        The editor command string, or None if $EDITOR is not set or empty.
    """
    editor = os.environ.get("EDITOR", "")
    return editor if editor.strip() else None


def _get_mtime(path: Path) -> float | None:
    """Get the modification time of a file.

    Args:
        path: Path to the file.

    Returns:
        The modification time as a float, or None if the file cannot be stat'd.
    """
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def launch_editor(
    postactivate_path: Path,
    suspend_tui: Callable[[], None],
    resume_tui: Callable[[], None],
) -> EditorResult:
    """Launch the user's editor to edit the postactivate file.

    Performs pre-launch validation, suspends the TUI, spawns the editor
    process, and resumes the TUI afterward. Reports whether the file was
    modified based on mtime comparison.

    Args:
        postactivate_path: Path to the postactivate file to edit.
        suspend_tui: Callable that suspends the TUI (leaves alternate screen).
        resume_tui: Callable that resumes the TUI (re-enters alternate screen).

    Returns:
        An EditorResult indicating success/failure and whether the file changed.
    """
    # Check $EDITOR is set and non-empty
    editor = _get_editor()
    if editor is None:
        return EditorResult(
            success=False,
            file_modified=False,
            error_message="No editor configured. Set the $EDITOR environment variable.",
        )

    # Check postactivate file exists
    if not postactivate_path.exists():
        return EditorResult(
            success=False,
            file_modified=False,
            error_message=f"File not found: {postactivate_path}",
        )

    # Record file modification timestamp before editing
    mtime_before = _get_mtime(postactivate_path)

    # Suspend the TUI
    suspend_tui()

    try:
        # Spawn editor process
        subprocess.run(
            [editor, str(postactivate_path)],
            stdin=None,
            stdout=None,
            stderr=None,
        )
    except FileNotFoundError:
        # Editor command not found
        resume_tui()
        return EditorResult(
            success=False,
            file_modified=False,
            error_message=f"Editor could not be started: '{editor}' not found.",
        )
    except OSError as e:
        # Other OS-level error launching the editor
        resume_tui()
        return EditorResult(
            success=False,
            file_modified=False,
            error_message=f"Editor could not be started: {e}",
        )

    # Resume the TUI
    resume_tui()

    # Compare modification timestamp to detect changes
    mtime_after = _get_mtime(postactivate_path)
    file_modified = mtime_before != mtime_after

    # Non-zero exit code from editor is not treated as a failure —
    # the editor ran, the user just may have quit without saving.
    # We only report failure if we couldn't launch at all.
    return EditorResult(
        success=True,
        file_modified=file_modified,
    )
