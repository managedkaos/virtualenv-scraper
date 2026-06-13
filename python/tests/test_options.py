"""Unit and property-based tests for the app options module.

Tests configuration precedence logic: CLI > env var > config file > default (false).
"""

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from virtualenv_viewer.options import AppOptions, _parse_bool_env, _read_config_file, parse_options

# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestParseBoolEnv:
    """Tests for _parse_bool_env helper."""

    def test_true_values(self) -> None:
        assert _parse_bool_env("1") is True
        assert _parse_bool_env("true") is True
        assert _parse_bool_env("True") is True
        assert _parse_bool_env("TRUE") is True

    def test_false_values(self) -> None:
        assert _parse_bool_env("0") is False
        assert _parse_bool_env("false") is False
        assert _parse_bool_env("False") is False
        assert _parse_bool_env("FALSE") is False

    def test_whitespace_stripped(self) -> None:
        assert _parse_bool_env("  true  ") is True
        assert _parse_bool_env("  0  ") is False

    def test_unrecognized_returns_none(self) -> None:
        assert _parse_bool_env("yes") is None
        assert _parse_bool_env("no") is None
        assert _parse_bool_env("") is None
        assert _parse_bool_env("2") is None


class TestReadConfigFile:
    """Tests for _read_config_file helper."""

    def test_reads_valid_toml(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text("restart_on_edit = true\n")
        result = _read_config_file(config_file)
        assert result == {"restart_on_edit": True}

    def test_returns_empty_dict_for_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.toml"
        result = _read_config_file(missing)
        assert result == {}

    def test_returns_empty_dict_for_invalid_toml(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.toml"
        bad_file.write_text("this is not [valid toml {{{")
        result = _read_config_file(bad_file)
        assert result == {}


class TestParseOptionsDefault:
    """Tests for default behavior when no source specifies the option."""

    def test_default_restart_on_edit_is_false(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When no CLI, env, or config is set, restart_on_edit defaults to False."""
        monkeypatch.delenv("VENV_VIEWER_RESTART_ON_EDIT", raising=False)
        # Point home to a temp dir so no real config file is found
        monkeypatch.setenv("HOME", str(tmp_path))
        result = parse_options([])
        assert result.restart_on_edit is False

    def test_returns_app_options_dataclass(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("VENV_VIEWER_RESTART_ON_EDIT", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        result = parse_options([])
        assert isinstance(result, AppOptions)


class TestParseOptionsCLI:
    """Tests for CLI flag precedence."""

    def test_cli_restart_on_edit_flag(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("VENV_VIEWER_RESTART_ON_EDIT", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        result = parse_options(["--restart-on-edit"])
        assert result.restart_on_edit is True

    def test_cli_no_restart_on_edit_flag(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("VENV_VIEWER_RESTART_ON_EDIT", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        result = parse_options(["--no-restart-on-edit"])
        assert result.restart_on_edit is False

    def test_cli_overrides_env_true(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """CLI --no-restart-on-edit overrides env var set to true."""
        monkeypatch.setenv("VENV_VIEWER_RESTART_ON_EDIT", "true")
        monkeypatch.setenv("HOME", str(tmp_path))
        result = parse_options(["--no-restart-on-edit"])
        assert result.restart_on_edit is False

    def test_cli_overrides_env_false(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """CLI --restart-on-edit overrides env var set to false."""
        monkeypatch.setenv("VENV_VIEWER_RESTART_ON_EDIT", "false")
        monkeypatch.setenv("HOME", str(tmp_path))
        result = parse_options(["--restart-on-edit"])
        assert result.restart_on_edit is True

    def test_cli_overrides_config_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """CLI --no-restart-on-edit overrides config file set to true."""
        config_file = tmp_path / ".virtualenv-viewer.toml"
        config_file.write_text("restart_on_edit = true\n")
        monkeypatch.delenv("VENV_VIEWER_RESTART_ON_EDIT", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        result = parse_options(["--no-restart-on-edit"])
        assert result.restart_on_edit is False


class TestParseOptionsEnv:
    """Tests for environment variable precedence."""

    def test_env_true_enables_restart(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("VENV_VIEWER_RESTART_ON_EDIT", "1")
        monkeypatch.setenv("HOME", str(tmp_path))
        result = parse_options([])
        assert result.restart_on_edit is True

    def test_env_false_disables_restart(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("VENV_VIEWER_RESTART_ON_EDIT", "0")
        monkeypatch.setenv("HOME", str(tmp_path))
        result = parse_options([])
        assert result.restart_on_edit is False

    def test_env_overrides_config_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Env var overrides config file value."""
        config_file = tmp_path / ".virtualenv-viewer.toml"
        config_file.write_text("restart_on_edit = true\n")
        monkeypatch.setenv("VENV_VIEWER_RESTART_ON_EDIT", "0")
        monkeypatch.setenv("HOME", str(tmp_path))
        result = parse_options([])
        assert result.restart_on_edit is False

    def test_env_invalid_value_falls_through(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Unrecognized env value is treated as not set (falls to config/default)."""
        monkeypatch.setenv("VENV_VIEWER_RESTART_ON_EDIT", "maybe")
        monkeypatch.setenv("HOME", str(tmp_path))
        result = parse_options([])
        assert result.restart_on_edit is False


class TestParseOptionsConfigFile:
    """Tests for config file as lowest-precedence source."""

    def test_config_file_true(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        config_file = tmp_path / ".virtualenv-viewer.toml"
        config_file.write_text("restart_on_edit = true\n")
        monkeypatch.delenv("VENV_VIEWER_RESTART_ON_EDIT", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        result = parse_options([])
        assert result.restart_on_edit is True

    def test_config_file_false(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        config_file = tmp_path / ".virtualenv-viewer.toml"
        config_file.write_text("restart_on_edit = false\n")
        monkeypatch.delenv("VENV_VIEWER_RESTART_ON_EDIT", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        result = parse_options([])
        assert result.restart_on_edit is False

    def test_config_file_non_bool_ignored(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Non-boolean value in config file is ignored (falls to default)."""
        config_file = tmp_path / ".virtualenv-viewer.toml"
        config_file.write_text('restart_on_edit = "yes"\n')
        monkeypatch.delenv("VENV_VIEWER_RESTART_ON_EDIT", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        result = parse_options([])
        assert result.restart_on_edit is False


# ─────────────────────────────────────────────────────────────────────────────
# Property-Based Tests
# ─────────────────────────────────────────────────────────────────────────────


# Strategy for optional boolean values (None means "not specified")
optional_bool = st.one_of(st.none(), st.booleans())

# Strategy for env var string representations of booleans
env_bool_strings = st.sampled_from(["1", "0", "true", "false", "True", "False", "TRUE", "FALSE"])


class TestPropertyConfigurationPrecedence:
    """Feature: virtualenv-config-viewer, Property 10: Configuration Precedence

    For any combination of configuration sources (CLI flag, environment variable,
    config file) that specify conflicting restart_on_edit values, the resolved
    value SHALL always equal the value from the highest-precedence source that
    is present (CLI > env > config file > default false).

    **Validates: Requirements 6.2, 6.3, 6.4, 6.5, 6.6**
    """

    @settings(max_examples=200)
    @given(
        cli_value=optional_bool,
        env_value=optional_bool,
        config_value=optional_bool,
    )
    def test_precedence_cli_over_env_over_config_over_default(
        self,
        cli_value: bool | None,
        env_value: bool | None,
        config_value: bool | None,
    ) -> None:
        """For any combination of CLI, env, and config values, the resolved value
        equals the highest-precedence source present."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Build CLI args
            cli_args: list[str] = []
            if cli_value is True:
                cli_args = ["--restart-on-edit"]
            elif cli_value is False:
                cli_args = ["--no-restart-on-edit"]

            # Set up environment
            import os

            old_env = os.environ.get("VENV_VIEWER_RESTART_ON_EDIT")
            old_home = os.environ.get("HOME")
            try:
                # Set HOME so config file lookup uses our temp dir
                os.environ["HOME"] = str(tmp_path)

                # Set or clear env var
                if env_value is not None:
                    os.environ["VENV_VIEWER_RESTART_ON_EDIT"] = "1" if env_value else "0"
                else:
                    os.environ.pop("VENV_VIEWER_RESTART_ON_EDIT", None)

                # Write or skip config file
                if config_value is not None:
                    config_file = tmp_path / ".virtualenv-viewer.toml"
                    config_file.write_text(
                        f"restart_on_edit = {'true' if config_value else 'false'}\n"
                    )

                # Parse options
                result = parse_options(cli_args)

                # Compute expected value using precedence rules
                if cli_value is not None:
                    expected = cli_value
                elif env_value is not None:
                    expected = env_value
                elif config_value is not None:
                    expected = config_value
                else:
                    expected = False

                assert result.restart_on_edit == expected, (
                    f"cli={cli_value}, env={env_value}, config={config_value} "
                    f"→ expected {expected}, got {result.restart_on_edit}"
                )
            finally:
                # Restore environment
                if old_env is not None:
                    os.environ["VENV_VIEWER_RESTART_ON_EDIT"] = old_env
                else:
                    os.environ.pop("VENV_VIEWER_RESTART_ON_EDIT", None)
                if old_home is not None:
                    os.environ["HOME"] = old_home
                else:
                    os.environ.pop("HOME", None)

    @settings(max_examples=100)
    @given(
        env_value=optional_bool,
        config_value=optional_bool,
    )
    def test_cli_always_wins_when_present(
        self,
        env_value: bool | None,
        config_value: bool | None,
    ) -> None:
        """When CLI is specified, it always overrides env and config regardless of their values."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            import os

            old_env = os.environ.get("VENV_VIEWER_RESTART_ON_EDIT")
            old_home = os.environ.get("HOME")
            try:
                os.environ["HOME"] = str(tmp_path)

                if env_value is not None:
                    os.environ["VENV_VIEWER_RESTART_ON_EDIT"] = "1" if env_value else "0"
                else:
                    os.environ.pop("VENV_VIEWER_RESTART_ON_EDIT", None)

                if config_value is not None:
                    config_file = tmp_path / ".virtualenv-viewer.toml"
                    config_file.write_text(
                        f"restart_on_edit = {'true' if config_value else 'false'}\n"
                    )

                # CLI True
                result_true = parse_options(["--restart-on-edit"])
                assert result_true.restart_on_edit is True

                # CLI False
                result_false = parse_options(["--no-restart-on-edit"])
                assert result_false.restart_on_edit is False
            finally:
                if old_env is not None:
                    os.environ["VENV_VIEWER_RESTART_ON_EDIT"] = old_env
                else:
                    os.environ.pop("VENV_VIEWER_RESTART_ON_EDIT", None)
                if old_home is not None:
                    os.environ["HOME"] = old_home
                else:
                    os.environ.pop("HOME", None)

    @settings(max_examples=100)
    @given(config_value=optional_bool)
    def test_env_wins_over_config_when_cli_absent(
        self,
        config_value: bool | None,
    ) -> None:
        """When CLI is absent but env is present, env overrides config
        regardless of config value."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            import os

            old_env = os.environ.get("VENV_VIEWER_RESTART_ON_EDIT")
            old_home = os.environ.get("HOME")
            try:
                os.environ["HOME"] = str(tmp_path)

                if config_value is not None:
                    config_file = tmp_path / ".virtualenv-viewer.toml"
                    config_file.write_text(
                        f"restart_on_edit = {'true' if config_value else 'false'}\n"
                    )

                # Env True
                os.environ["VENV_VIEWER_RESTART_ON_EDIT"] = "true"
                result_true = parse_options([])
                assert result_true.restart_on_edit is True

                # Env False
                os.environ["VENV_VIEWER_RESTART_ON_EDIT"] = "false"
                result_false = parse_options([])
                assert result_false.restart_on_edit is False
            finally:
                if old_env is not None:
                    os.environ["VENV_VIEWER_RESTART_ON_EDIT"] = old_env
                else:
                    os.environ.pop("VENV_VIEWER_RESTART_ON_EDIT", None)
                if old_home is not None:
                    os.environ["HOME"] = old_home
                else:
                    os.environ.pop("HOME", None)

    @settings(max_examples=100)
    @given(config_value=st.booleans())
    def test_config_used_when_cli_and_env_absent(
        self,
        config_value: bool,
    ) -> None:
        """When both CLI and env are absent, config file value is used."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            import os

            old_env = os.environ.get("VENV_VIEWER_RESTART_ON_EDIT")
            old_home = os.environ.get("HOME")
            try:
                os.environ["HOME"] = str(tmp_path)
                os.environ.pop("VENV_VIEWER_RESTART_ON_EDIT", None)

                config_file = tmp_path / ".virtualenv-viewer.toml"
                config_file.write_text(f"restart_on_edit = {'true' if config_value else 'false'}\n")

                result = parse_options([])
                assert result.restart_on_edit == config_value
            finally:
                if old_env is not None:
                    os.environ["VENV_VIEWER_RESTART_ON_EDIT"] = old_env
                else:
                    os.environ.pop("VENV_VIEWER_RESTART_ON_EDIT", None)
                if old_home is not None:
                    os.environ["HOME"] = old_home
                else:
                    os.environ.pop("HOME", None)

    @settings(max_examples=100)
    @given(data=st.data())
    def test_default_false_when_all_sources_absent(self, data: st.DataObject) -> None:
        """When no source is present, the default is always False."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            import os

            old_env = os.environ.get("VENV_VIEWER_RESTART_ON_EDIT")
            old_home = os.environ.get("HOME")
            try:
                os.environ["HOME"] = str(tmp_path)
                os.environ.pop("VENV_VIEWER_RESTART_ON_EDIT", None)
                # No config file created

                result = parse_options([])
                assert result.restart_on_edit is False
            finally:
                if old_env is not None:
                    os.environ["VENV_VIEWER_RESTART_ON_EDIT"] = old_env
                else:
                    os.environ.pop("VENV_VIEWER_RESTART_ON_EDIT", None)
                if old_home is not None:
                    os.environ["HOME"] = old_home
                else:
                    os.environ.pop("HOME", None)
