"""Unit tests for the Config Reader module."""

from pathlib import Path

import pytest

from virtualenv_viewer.config_reader import ConfigFiles, read_configs


@pytest.fixture
def venv_dir(tmp_path: Path) -> Path:
    """Create a minimal virtualenv directory structure."""
    (tmp_path / "bin").mkdir()
    return tmp_path


class TestReadConfigs:
    """Tests for read_configs function."""

    def test_reads_pyvenv_cfg(self, venv_dir: Path) -> None:
        """Should read pyvenv.cfg content from virtualenv root."""
        content = "home = /usr/bin\nversion = 3.11.5\n"
        (venv_dir / "pyvenv.cfg").write_text(content)

        result = read_configs(venv_dir)

        assert result.pyvenv_cfg == content

    def test_reads_postactivate(self, venv_dir: Path) -> None:
        """Should read postactivate content from bin/ directory."""
        content = "export FOO=bar\nalias ll='ls -la'\n"
        (venv_dir / "bin" / "postactivate").write_text(content)

        result = read_configs(venv_dir)

        assert result.postactivate == content

    def test_reads_both_files(self, venv_dir: Path) -> None:
        """Should read both files when both exist."""
        cfg_content = "home = /usr/bin\n"
        post_content = "export PATH=$HOME/bin:$PATH\n"
        (venv_dir / "pyvenv.cfg").write_text(cfg_content)
        (venv_dir / "bin" / "postactivate").write_text(post_content)

        result = read_configs(venv_dir)

        assert result.pyvenv_cfg == cfg_content
        assert result.postactivate == post_content

    def test_missing_pyvenv_cfg_returns_none(self, venv_dir: Path) -> None:
        """Should return None for pyvenv_cfg when file is missing."""
        result = read_configs(venv_dir)

        assert result.pyvenv_cfg is None

    def test_missing_postactivate_returns_none(self, venv_dir: Path) -> None:
        """Should return None for postactivate when file is missing."""
        result = read_configs(venv_dir)

        assert result.postactivate is None

    def test_both_files_missing(self, venv_dir: Path) -> None:
        """Should return None for both when neither file exists."""
        result = read_configs(venv_dir)

        assert result.pyvenv_cfg is None
        assert result.postactivate is None

    def test_unreadable_pyvenv_cfg_returns_none(self, venv_dir: Path) -> None:
        """Should return None when pyvenv.cfg has no read permission."""
        cfg_path = venv_dir / "pyvenv.cfg"
        cfg_path.write_text("content")
        cfg_path.chmod(0o000)

        try:
            result = read_configs(venv_dir)
            assert result.pyvenv_cfg is None
        finally:
            cfg_path.chmod(0o644)

    def test_unreadable_postactivate_returns_none(self, venv_dir: Path) -> None:
        """Should return None when postactivate has no read permission."""
        post_path = venv_dir / "bin" / "postactivate"
        post_path.write_text("content")
        post_path.chmod(0o000)

        try:
            result = read_configs(venv_dir)
            assert result.postactivate is None
        finally:
            post_path.chmod(0o644)

    def test_postactivate_path_is_set(self, venv_dir: Path) -> None:
        """Should always set postactivate_path to expected location."""
        result = read_configs(venv_dir)

        assert result.postactivate_path == venv_dir / "bin" / "postactivate"

    def test_postactivate_mtime_when_file_exists(self, venv_dir: Path) -> None:
        """Should capture mtime when postactivate exists."""
        post_path = venv_dir / "bin" / "postactivate"
        post_path.write_text("export X=1\n")

        result = read_configs(venv_dir)

        assert result.postactivate_mtime is not None
        assert result.postactivate_mtime == post_path.stat().st_mtime

    def test_postactivate_mtime_none_when_missing(self, venv_dir: Path) -> None:
        """Should return None for mtime when postactivate is missing."""
        result = read_configs(venv_dir)

        assert result.postactivate_mtime is None

    def test_nonexistent_venv_directory(self, tmp_path: Path) -> None:
        """Should handle non-existent virtualenv directory gracefully."""
        fake_path = tmp_path / "nonexistent"

        result = read_configs(fake_path)

        assert result.pyvenv_cfg is None
        assert result.postactivate is None
        assert result.postactivate_path == fake_path / "bin" / "postactivate"
        assert result.postactivate_mtime is None

    def test_returns_config_files_dataclass(self, venv_dir: Path) -> None:
        """Should return a ConfigFiles instance."""
        result = read_configs(venv_dir)

        assert isinstance(result, ConfigFiles)

    def test_no_config_files_found_condition(self, venv_dir: Path) -> None:
        """When no files are readable, both fields are None (requirement 2.6).

        The consumer can detect this condition to display an informative message.
        """
        result = read_configs(venv_dir)

        # This is the condition the TUI checks to show "no configuration files found"
        assert result.pyvenv_cfg is None and result.postactivate is None

    def test_missing_bin_directory(self, tmp_path: Path) -> None:
        """Should handle missing bin/ directory gracefully (postactivate path unreachable)."""
        # Don't create bin/ directory at all
        result = read_configs(tmp_path)

        assert result.postactivate is None
        assert result.postactivate_mtime is None
        assert result.postactivate_path == tmp_path / "bin" / "postactivate"

    def test_preserves_file_content_exactly(self, venv_dir: Path) -> None:
        """Should return raw text contents without modification (requirement 2.5)."""
        # Content with special characters, multiple lines, trailing whitespace
        cfg_content = (
            "home = /usr/local/bin\ninclude-system-site-packages = false\nversion = 3.11.5\n"
        )
        post_content = '#!/bin/bash\nexport FOO="bar baz"\nexport PATH=$HOME/bin:$PATH\n'
        (venv_dir / "pyvenv.cfg").write_text(cfg_content)
        (venv_dir / "bin" / "postactivate").write_text(post_content)

        result = read_configs(venv_dir)

        assert result.pyvenv_cfg == cfg_content
        assert result.postactivate == post_content
