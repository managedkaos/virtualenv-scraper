"""Unit tests for the Editor Launcher module."""

from pathlib import Path

import pytest

from virtualenv_viewer.editor import (
    _get_editor,
    _get_mtime,
    launch_editor,
)


class TestGetEditor:
    """Tests for _get_editor helper."""

    def test_returns_editor_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EDITOR", "vim")
        assert _get_editor() == "vim"

    def test_returns_none_when_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EDITOR", raising=False)
        assert _get_editor() is None

    def test_returns_none_when_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EDITOR", "")
        assert _get_editor() is None

    def test_returns_none_when_whitespace_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EDITOR", "   ")
        assert _get_editor() is None

    def test_returns_editor_with_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EDITOR", "/usr/bin/nano")
        assert _get_editor() == "/usr/bin/nano"


class TestGetMtime:
    """Tests for _get_mtime helper."""

    def test_returns_mtime_for_existing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("content")
        mtime = _get_mtime(f)
        assert mtime is not None
        assert isinstance(mtime, float)

    def test_returns_none_for_nonexistent_file(self, tmp_path: Path) -> None:
        f = tmp_path / "nonexistent.txt"
        assert _get_mtime(f) is None


class TestLaunchEditorValidation:
    """Tests for editor launch pre-validation checks."""

    def test_error_when_editor_not_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("EDITOR", raising=False)
        f = tmp_path / "postactivate"
        f.write_text("export FOO=bar")

        suspend_called = []
        resume_called = []

        result = launch_editor(
            f,
            suspend_tui=lambda: suspend_called.append(True),
            resume_tui=lambda: resume_called.append(True),
        )

        assert result.success is False
        assert result.file_modified is False
        assert "EDITOR" in result.error_message
        # TUI should not be suspended/resumed on early validation error
        assert len(suspend_called) == 0
        assert len(resume_called) == 0

    def test_error_when_editor_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EDITOR", "")
        f = tmp_path / "postactivate"
        f.write_text("export FOO=bar")

        result = launch_editor(
            f,
            suspend_tui=lambda: None,
            resume_tui=lambda: None,
        )

        assert result.success is False
        assert "EDITOR" in result.error_message

    def test_error_when_file_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EDITOR", "vim")
        f = tmp_path / "nonexistent"

        suspend_called = []
        result = launch_editor(
            f,
            suspend_tui=lambda: suspend_called.append(True),
            resume_tui=lambda: None,
        )

        assert result.success is False
        assert result.file_modified is False
        assert (
            "not found" in result.error_message.lower() or "File not found" in result.error_message
        )
        # TUI should not be suspended on file-not-found
        assert len(suspend_called) == 0


class TestLaunchEditorExecution:
    """Tests for editor launch execution and mtime comparison."""

    def test_successful_edit_no_modification(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EDITOR", "true")  # 'true' exits immediately
        f = tmp_path / "postactivate"
        f.write_text("export FOO=bar")

        suspend_called = []
        resume_called = []

        result = launch_editor(
            f,
            suspend_tui=lambda: suspend_called.append(True),
            resume_tui=lambda: resume_called.append(True),
        )

        assert result.success is True
        assert result.file_modified is False
        assert result.error_message is None
        assert len(suspend_called) == 1
        assert len(resume_called) == 1

    def test_successful_edit_with_modification(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        f = tmp_path / "postactivate"
        f.write_text("export FOO=bar")

        # Use a script that modifies the file
        script = tmp_path / "editor.sh"
        script.write_text('#!/bin/sh\necho "modified" >> "$1"\n')
        script.chmod(0o755)

        monkeypatch.setenv("EDITOR", str(script))

        result = launch_editor(
            f,
            suspend_tui=lambda: None,
            resume_tui=lambda: None,
        )

        assert result.success is True
        assert result.file_modified is True
        assert result.error_message is None

    def test_error_when_editor_command_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EDITOR", "nonexistent_editor_xyz_12345")
        f = tmp_path / "postactivate"
        f.write_text("export FOO=bar")

        suspend_called = []
        resume_called = []

        result = launch_editor(
            f,
            suspend_tui=lambda: suspend_called.append(True),
            resume_tui=lambda: resume_called.append(True),
        )

        assert result.success is False
        assert result.file_modified is False
        assert "not found" in result.error_message.lower()
        # TUI was suspended but should be resumed on error
        assert len(suspend_called) == 1
        assert len(resume_called) == 1

    def test_suspend_called_before_editor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify TUI is suspended before editor runs and resumed after."""
        monkeypatch.setenv("EDITOR", "true")
        f = tmp_path / "postactivate"
        f.write_text("content")

        call_order = []

        result = launch_editor(
            f,
            suspend_tui=lambda: call_order.append("suspend"),
            resume_tui=lambda: call_order.append("resume"),
        )

        assert result.success is True
        assert call_order == ["suspend", "resume"]
