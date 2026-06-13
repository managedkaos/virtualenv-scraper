"""Unit tests for the TUI controller and navigation logic."""

from pathlib import Path

from virtualenv_viewer.config_reader import ConfigFiles
from virtualenv_viewer.shell_analyzer import (
    ShellAlias,
    ShellExports,
    ShellFunction,
    ShellVariable,
)
from virtualenv_viewer.tui import (
    _calculate_pages,
    _clamp_page,
    _get_page_lines,
    render_content,
)


def _make_config_files(
    pyvenv_cfg: str | None = None, postactivate: str | None = None
) -> ConfigFiles:
    """Helper to create a ConfigFiles instance for testing."""
    return ConfigFiles(
        pyvenv_cfg=pyvenv_cfg,
        postactivate=postactivate,
        postactivate_path=Path("/fake/bin/postactivate"),
        postactivate_mtime=None,
    )


def _make_exports(
    variables: list[ShellVariable] | None = None,
    aliases: list[ShellAlias] | None = None,
    functions: list[ShellFunction] | None = None,
) -> ShellExports:
    """Helper to create a ShellExports instance for testing."""
    return ShellExports(
        variables=variables or [],
        aliases=aliases or [],
        functions=functions or [],
    )


class TestRenderContent:
    """Tests for the content rendering pipeline."""

    def test_renders_pyvenv_cfg_header(self) -> None:
        config = _make_config_files(pyvenv_cfg="home = /usr/bin\nversion = 3.11")
        exports = _make_exports()
        lines = render_content(config, exports)
        assert lines[0] == "═══ pyvenv.cfg ═══"

    def test_renders_pyvenv_cfg_content(self) -> None:
        config = _make_config_files(pyvenv_cfg="home = /usr/bin\nversion = 3.11")
        exports = _make_exports()
        lines = render_content(config, exports)
        assert "home = /usr/bin" in lines
        assert "version = 3.11" in lines

    def test_renders_missing_pyvenv_cfg(self) -> None:
        config = _make_config_files(pyvenv_cfg=None)
        exports = _make_exports()
        lines = render_content(config, exports)
        assert "  (not found)" in lines

    def test_renders_postactivate_header(self) -> None:
        config = _make_config_files(postactivate="export FOO=bar")
        exports = _make_exports()
        lines = render_content(config, exports)
        assert "═══ postactivate (raw) ═══" in lines

    def test_renders_postactivate_content(self) -> None:
        config = _make_config_files(postactivate="export FOO=bar\nalias ll=ls")
        exports = _make_exports()
        lines = render_content(config, exports)
        assert "export FOO=bar" in lines
        assert "alias ll=ls" in lines

    def test_renders_missing_postactivate(self) -> None:
        config = _make_config_files(postactivate=None)
        exports = _make_exports()
        lines = render_content(config, exports)
        # Should have "(not found)" for postactivate section
        idx = lines.index("═══ postactivate (raw) ═══")
        assert lines[idx + 1] == "  (not found)"

    def test_renders_shell_exports_header(self) -> None:
        config = _make_config_files()
        exports = _make_exports()
        lines = render_content(config, exports)
        assert "═══ Shell Exports ═══" in lines

    def test_renders_variables(self) -> None:
        config = _make_config_files()
        exports = _make_exports(
            variables=[
                ShellVariable(name="PATH", value="/usr/bin"),
                ShellVariable(name="HOME", value="/home/user"),
            ]
        )
        lines = render_content(config, exports)
        assert "  PATH = /usr/bin" in lines
        assert "  HOME = /home/user" in lines

    def test_renders_aliases(self) -> None:
        config = _make_config_files()
        exports = _make_exports(aliases=[ShellAlias(name="ll", definition="ls -la")])
        lines = render_content(config, exports)
        assert "  ll = ls -la" in lines

    def test_renders_functions(self) -> None:
        config = _make_config_files()
        exports = _make_exports(functions=[ShellFunction(name="greet", body="echo hello")])
        lines = render_content(config, exports)
        assert "  greet()" in lines
        assert "    echo hello" in lines

    def test_renders_empty_exports_with_none_markers(self) -> None:
        config = _make_config_files()
        exports = _make_exports()
        lines = render_content(config, exports)
        # After each subheader, should have (none)
        var_idx = lines.index("── Variables ──")
        assert lines[var_idx + 1] == "  (none)"
        alias_idx = lines.index("── Aliases ──")
        assert lines[alias_idx + 1] == "  (none)"
        func_idx = lines.index("── Functions ──")
        assert lines[func_idx + 1] == "  (none)"

    def test_section_order(self) -> None:
        config = _make_config_files(pyvenv_cfg="cfg", postactivate="post")
        exports = _make_exports()
        lines = render_content(config, exports)
        cfg_idx = lines.index("═══ pyvenv.cfg ═══")
        post_idx = lines.index("═══ postactivate (raw) ═══")
        exports_idx = lines.index("═══ Shell Exports ═══")
        assert cfg_idx < post_idx < exports_idx

    def test_blank_separators_between_sections(self) -> None:
        config = _make_config_files(pyvenv_cfg="cfg", postactivate="post")
        exports = _make_exports()
        lines = render_content(config, exports)
        # Blank line before postactivate header
        post_idx = lines.index("═══ postactivate (raw) ═══")
        assert lines[post_idx - 1] == ""
        # Blank line before shell exports header
        exports_idx = lines.index("═══ Shell Exports ═══")
        assert lines[exports_idx - 1] == ""


class TestCalculatePages:
    """Tests for page calculation logic."""

    def test_single_page(self) -> None:
        assert _calculate_pages(5, 10) == 1

    def test_exact_pages(self) -> None:
        assert _calculate_pages(20, 10) == 2

    def test_partial_last_page(self) -> None:
        assert _calculate_pages(21, 10) == 3

    def test_zero_lines(self) -> None:
        assert _calculate_pages(0, 10) == 1

    def test_zero_page_size(self) -> None:
        assert _calculate_pages(10, 0) == 1

    def test_one_line_per_page(self) -> None:
        assert _calculate_pages(5, 1) == 5


class TestClampPage:
    """Tests for page clamping logic."""

    def test_clamp_within_bounds(self) -> None:
        assert _clamp_page(3, 5) == 3

    def test_clamp_below_minimum(self) -> None:
        assert _clamp_page(0, 5) == 1

    def test_clamp_negative(self) -> None:
        assert _clamp_page(-1, 5) == 1

    def test_clamp_above_maximum(self) -> None:
        assert _clamp_page(6, 5) == 5

    def test_clamp_at_boundaries(self) -> None:
        assert _clamp_page(1, 5) == 1
        assert _clamp_page(5, 5) == 5

    def test_single_page(self) -> None:
        assert _clamp_page(1, 1) == 1
        assert _clamp_page(2, 1) == 1
        assert _clamp_page(0, 1) == 1


class TestGetPageLines:
    """Tests for extracting page content from the flat line list."""

    def test_first_page(self) -> None:
        lines = ["a", "b", "c", "d", "e"]
        assert _get_page_lines(lines, 1, 2) == ["a", "b"]

    def test_second_page(self) -> None:
        lines = ["a", "b", "c", "d", "e"]
        assert _get_page_lines(lines, 2, 2) == ["c", "d"]

    def test_last_partial_page(self) -> None:
        lines = ["a", "b", "c", "d", "e"]
        assert _get_page_lines(lines, 3, 2) == ["e"]

    def test_full_page(self) -> None:
        lines = ["a", "b", "c", "d"]
        assert _get_page_lines(lines, 1, 4) == ["a", "b", "c", "d"]

    def test_empty_content(self) -> None:
        assert _get_page_lines([], 1, 10) == []
