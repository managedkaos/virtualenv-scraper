"""Unit tests for the Restart Handler module."""

from pathlib import Path
from unittest.mock import patch

from virtualenv_viewer.restart import RestartResult, handle_restart, restart_virtualenv


class TestRestartVirtualenv:
    """Tests for restart_virtualenv function."""

    def test_success_with_valid_activate_script(self, tmp_path: Path) -> None:
        """Restart succeeds when activate script exists and runs cleanly."""
        # Create a minimal activate script that succeeds
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        activate = bin_dir / "activate"
        activate.write_text("# activate script\n")

        result = restart_virtualenv(tmp_path)

        assert result.success is True
        assert tmp_path.name in result.message
        assert "restarted successfully" in result.message

    def test_failure_when_activate_missing(self, tmp_path: Path) -> None:
        """Restart fails when bin/activate does not exist."""
        # No bin/activate file
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        result = restart_virtualenv(tmp_path)

        assert result.success is False
        assert "activate script not found" in result.message

    def test_failure_when_bin_dir_missing(self, tmp_path: Path) -> None:
        """Restart fails when bin directory does not exist."""
        result = restart_virtualenv(tmp_path)

        assert result.success is False
        assert "activate script not found" in result.message

    def test_failure_when_activate_script_errors(self, tmp_path: Path) -> None:
        """Restart fails when the activate script returns non-zero."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        activate = bin_dir / "activate"
        # Write a script that fails
        activate.write_text("exit 1\n")

        result = restart_virtualenv(tmp_path)

        assert result.success is False
        assert "Restart failed" in result.message

    def test_failure_when_bash_not_found(self, tmp_path: Path) -> None:
        """Restart fails gracefully when bash is not available."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        activate = bin_dir / "activate"
        activate.write_text("# activate\n")

        with patch(
            "virtualenv_viewer.restart.subprocess.run",
            side_effect=FileNotFoundError("bash not found"),
        ):
            result = restart_virtualenv(tmp_path)

        assert result.success is False
        assert "bash not found" in result.message

    def test_failure_on_timeout(self, tmp_path: Path) -> None:
        """Restart fails gracefully on command timeout."""
        import subprocess

        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        activate = bin_dir / "activate"
        activate.write_text("# activate\n")

        with patch(
            "virtualenv_viewer.restart.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="bash", timeout=10),
        ):
            result = restart_virtualenv(tmp_path)

        assert result.success is False
        assert "timed out" in result.message

    def test_failure_on_os_error(self, tmp_path: Path) -> None:
        """Restart fails gracefully on generic OS error."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        activate = bin_dir / "activate"
        activate.write_text("# activate\n")

        with patch(
            "virtualenv_viewer.restart.subprocess.run",
            side_effect=OSError("permission denied"),
        ):
            result = restart_virtualenv(tmp_path)

        assert result.success is False
        assert "permission denied" in result.message

    def test_result_message_includes_venv_name(self, tmp_path: Path) -> None:
        """Confirmation message includes the virtualenv name on success."""
        venv_dir = tmp_path / "my-project-venv"
        venv_dir.mkdir()
        bin_dir = venv_dir / "bin"
        bin_dir.mkdir()
        activate = bin_dir / "activate"
        activate.write_text("# activate\n")

        result = restart_virtualenv(venv_dir)

        assert result.success is True
        assert "my-project-venv" in result.message


class TestHandleRestart:
    """Tests for handle_restart conditional logic."""

    def test_returns_none_when_restart_disabled(self, tmp_path: Path) -> None:
        """No restart attempt when restart_on_edit is False."""
        result = handle_restart(
            venv_path=tmp_path,
            restart_on_edit=False,
            file_was_modified=True,
        )
        assert result is None

    def test_returns_none_when_file_not_modified(self, tmp_path: Path) -> None:
        """No restart attempt when file was not modified."""
        result = handle_restart(
            venv_path=tmp_path,
            restart_on_edit=True,
            file_was_modified=False,
        )
        assert result is None

    def test_returns_none_when_both_disabled_and_unmodified(self, tmp_path: Path) -> None:
        """No restart attempt when both conditions are False."""
        result = handle_restart(
            venv_path=tmp_path,
            restart_on_edit=False,
            file_was_modified=False,
        )
        assert result is None

    def test_attempts_restart_when_enabled_and_modified(self, tmp_path: Path) -> None:
        """Restart is attempted when both conditions are True."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        activate = bin_dir / "activate"
        activate.write_text("# activate\n")

        result = handle_restart(
            venv_path=tmp_path,
            restart_on_edit=True,
            file_was_modified=True,
        )

        assert result is not None
        assert isinstance(result, RestartResult)
        assert result.success is True

    def test_returns_failure_result_on_error(self, tmp_path: Path) -> None:
        """Returns a failure RestartResult when restart fails."""
        # No bin/activate exists
        result = handle_restart(
            venv_path=tmp_path,
            restart_on_edit=True,
            file_was_modified=True,
        )

        assert result is not None
        assert result.success is False
        assert "Restart failed" in result.message
