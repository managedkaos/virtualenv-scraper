"""Restart handler for virtualenv-viewer.

Handles deactivating and reactivating the virtualenv after the postactivate
file has been modified, when the restart-on-edit option is enabled.

Note: The viewer runs in a child process, so the restart sequence executes
in a subshell. The parent shell's environment is not directly modified;
the confirmation message informs the user that the sequence completed
successfully in the subprocess context.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RestartResult:
    """Result of a virtualenv restart attempt.

    Attributes:
        success: Whether the deactivate/reactivate sequence completed successfully.
        message: Human-readable message describing the outcome.
    """

    success: bool
    message: str


def restart_virtualenv(venv_path: Path) -> RestartResult:
    """Execute the deactivate/reactivate sequence for the given virtualenv.

    Runs ``deactivate && source {venv_path}/bin/activate`` in a bash subshell.
    On success, returns a confirmation message. On failure, returns an error
    message; the virtualenv is left in its deactivated state.

    Args:
        venv_path: Absolute path to the virtualenv directory.

    Returns:
        A RestartResult indicating success or failure with a descriptive message.
    """
    activate_path = venv_path / "bin" / "activate"

    if not activate_path.is_file():
        return RestartResult(
            success=False,
            message=f"Restart failed: activate script not found at {activate_path}",
        )

    # Build the deactivate/reactivate command.
    # We use 'deactivate' (a shell function set by activate) followed by
    # re-sourcing the activate script.
    command = f"deactivate 2>/dev/null; source '{activate_path}'"

    try:
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        return RestartResult(
            success=False,
            message="Restart failed: bash not found",
        )
    except subprocess.TimeoutExpired:
        return RestartResult(
            success=False,
            message="Restart failed: command timed out",
        )
    except OSError as e:
        return RestartResult(
            success=False,
            message=f"Restart failed: {e}",
        )

    if result.returncode != 0:
        stderr_msg = result.stderr.strip() if result.stderr else "unknown error"
        return RestartResult(
            success=False,
            message=f"Restart failed: {stderr_msg}",
        )

    venv_name = venv_path.name
    return RestartResult(
        success=True,
        message=f"Virtualenv '{venv_name}' restarted successfully",
    )


def handle_restart(
    venv_path: Path,
    restart_on_edit: bool,
    file_was_modified: bool,
) -> RestartResult | None:
    """Conditionally restart the virtualenv after a file edit.

    This is the main entry point for the restart handler. It checks whether
    restart-on-edit is enabled and the file was actually modified before
    attempting the restart sequence.

    Args:
        venv_path: Absolute path to the virtualenv directory.
        restart_on_edit: Whether the restart-on-edit option is enabled.
        file_was_modified: Whether the postactivate file was modified during editing.

    Returns:
        A RestartResult if restart was attempted, or None if restart was skipped
        (either because restart-on-edit is disabled or the file wasn't modified).
    """
    if not restart_on_edit or not file_was_modified:
        return None

    return restart_virtualenv(venv_path)
