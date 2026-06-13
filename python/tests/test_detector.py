"""Unit and property-based tests for the virtualenv detector module."""

import contextlib
import os
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from virtualenv_viewer.detector import _is_valid_virtualenv, detect_virtualenv


class TestIsValidVirtualenv:
    """Tests for the _is_valid_virtualenv helper."""

    def test_valid_when_pyvenv_cfg_exists(self, tmp_path: Path) -> None:
        (tmp_path / "pyvenv.cfg").write_text("home = /usr/bin\n")
        assert _is_valid_virtualenv(tmp_path) is True

    def test_invalid_when_pyvenv_cfg_missing(self, tmp_path: Path) -> None:
        assert _is_valid_virtualenv(tmp_path) is False

    def test_invalid_when_pyvenv_cfg_is_directory(self, tmp_path: Path) -> None:
        (tmp_path / "pyvenv.cfg").mkdir()
        assert _is_valid_virtualenv(tmp_path) is False

    def test_invalid_when_path_does_not_exist(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent"
        assert _is_valid_virtualenv(nonexistent) is False


class TestDetectVirtualenv:
    """Tests for the detect_virtualenv function."""

    def test_detects_virtual_env_variable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VIRTUAL_ENV set and valid → returns that path."""
        venv_dir = tmp_path / "my_venv"
        venv_dir.mkdir()
        (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin\n")

        monkeypatch.setenv("VIRTUAL_ENV", str(venv_dir))
        monkeypatch.chdir(tmp_path)

        result = detect_virtualenv()
        assert result == venv_dir

    def test_virtual_env_set_but_invalid_exits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VIRTUAL_ENV set but no pyvenv.cfg → exits with code 1."""
        invalid_dir = tmp_path / "not_a_venv"
        invalid_dir.mkdir()

        monkeypatch.setenv("VIRTUAL_ENV", str(invalid_dir))
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            detect_virtualenv()
        assert exc_info.value.code == 1

    def test_virtual_env_set_but_invalid_prints_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """VIRTUAL_ENV set but invalid → prints specific error message."""
        invalid_dir = tmp_path / "bad_venv"
        invalid_dir.mkdir()

        monkeypatch.setenv("VIRTUAL_ENV", str(invalid_dir))
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit):
            detect_virtualenv()

        captured = capsys.readouterr()
        assert "VIRTUAL_ENV is set to" in captured.err
        assert str(invalid_dir) in captured.err
        assert "not a valid virtualenv" in captured.err

    def test_detects_dot_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """$PWD/.env is valid → returns it."""
        dot_env = tmp_path / ".env"
        dot_env.mkdir()
        (dot_env / "pyvenv.cfg").write_text("home = /usr/bin\n")

        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.chdir(tmp_path)

        result = detect_virtualenv()
        assert result == dot_env

    def test_detects_dot_venv(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """$PWD/.venv is valid (and .env is not) → returns .venv."""
        dot_venv = tmp_path / ".venv"
        dot_venv.mkdir()
        (dot_venv / "pyvenv.cfg").write_text("home = /usr/bin\n")

        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.chdir(tmp_path)

        result = detect_virtualenv()
        assert result == dot_venv

    def test_detects_venv(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """$PWD/venv is valid (and .env, .venv are not) → returns venv."""
        venv = tmp_path / "venv"
        venv.mkdir()
        (venv / "pyvenv.cfg").write_text("home = /usr/bin\n")

        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.chdir(tmp_path)

        result = detect_virtualenv()
        assert result == venv

    def test_detects_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """$PWD/env is valid (and .env, .venv, venv are not) → returns env."""
        env = tmp_path / "env"
        env.mkdir()
        (env / "pyvenv.cfg").write_text("home = /usr/bin\n")

        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.chdir(tmp_path)

        result = detect_virtualenv()
        assert result == env

    def test_priority_order_first_match_wins(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When multiple candidates are valid, the highest-priority one wins."""
        # Create both .env and .venv as valid
        dot_env = tmp_path / ".env"
        dot_env.mkdir()
        (dot_env / "pyvenv.cfg").write_text("home = /usr/bin\n")

        dot_venv = tmp_path / ".venv"
        dot_venv.mkdir()
        (dot_venv / "pyvenv.cfg").write_text("home = /usr/bin\n")

        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.chdir(tmp_path)

        result = detect_virtualenv()
        assert result == dot_env

    def test_virtual_env_takes_priority_over_cwd_candidates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """$VIRTUAL_ENV takes priority over CWD-based candidates."""
        # Create a valid .venv in CWD
        dot_venv = tmp_path / ".venv"
        dot_venv.mkdir()
        (dot_venv / "pyvenv.cfg").write_text("home = /usr/bin\n")

        # And a valid VIRTUAL_ENV elsewhere
        other_venv = tmp_path / "other_venv"
        other_venv.mkdir()
        (other_venv / "pyvenv.cfg").write_text("home = /usr/bin\n")

        monkeypatch.setenv("VIRTUAL_ENV", str(other_venv))
        monkeypatch.chdir(tmp_path)

        result = detect_virtualenv()
        assert result == other_venv

    def test_no_virtualenv_found_exits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No valid virtualenv anywhere → exits with code 1."""
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            detect_virtualenv()
        assert exc_info.value.code == 1

    def test_no_virtualenv_found_prints_attempted_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """No valid virtualenv → error lists all attempted paths."""
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit):
            detect_virtualenv()

        captured = capsys.readouterr()
        assert "No valid virtualenv found" in captured.err
        assert ".env" in captured.err
        assert ".venv" in captured.err
        assert "venv" in captured.err
        assert "env" in captured.err

    def test_skips_invalid_candidates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Directories without pyvenv.cfg are skipped."""
        # .env exists but has no pyvenv.cfg
        dot_env = tmp_path / ".env"
        dot_env.mkdir()

        # .venv is valid
        dot_venv = tmp_path / ".venv"
        dot_venv.mkdir()
        (dot_venv / "pyvenv.cfg").write_text("home = /usr/bin\n")

        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.chdir(tmp_path)

        result = detect_virtualenv()
        assert result == dot_venv


# ─────────────────────────────────────────────────────────────────────────────
# Property-Based Tests
# ─────────────────────────────────────────────────────────────────────────────

# The candidate directories in priority order (after $VIRTUAL_ENV)
CANDIDATE_NAMES = [".env", ".venv", "venv", "env"]


class TestPropertyDetectionPriorityOrdering:
    """Feature: virtualenv-config-viewer, Property 1: Detection Priority Ordering

    For any set of candidate directories (subset of {.env, .venv, venv, env})
    that contain a valid pyvenv.cfg file, the Virtualenv Detector SHALL return
    the directory with the highest priority according to the defined order,
    regardless of which other valid directories exist.

    **Validates: Requirements 1.3, 1.5**
    """

    @settings(max_examples=100)
    @given(valid_mask=st.lists(st.booleans(), min_size=4, max_size=4))
    def test_returns_highest_priority_candidate(self, valid_mask: list[bool]) -> None:
        """For any non-empty subset of valid candidates, detection returns
        the highest-priority one."""
        # Skip the case where no candidates are valid (that's an error path)
        if not any(valid_mask):
            return

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir).resolve()

            # Save and restore env/cwd
            old_virtual_env = os.environ.pop("VIRTUAL_ENV", None)
            old_cwd = os.getcwd()
            try:
                os.chdir(tmp_path)

                # Create candidate directories; mark some as valid (with pyvenv.cfg)
                for i, name in enumerate(CANDIDATE_NAMES):
                    candidate_dir = tmp_path / name
                    candidate_dir.mkdir()
                    if valid_mask[i]:
                        (candidate_dir / "pyvenv.cfg").write_text("home = /usr/bin\n")

                result = detect_virtualenv()

                # The expected result is the first candidate marked valid
                expected_index = next(i for i, v in enumerate(valid_mask) if v)
                expected_path = tmp_path / CANDIDATE_NAMES[expected_index]
                assert result == expected_path
            finally:
                os.chdir(old_cwd)
                if old_virtual_env is not None:
                    os.environ["VIRTUAL_ENV"] = old_virtual_env

    @settings(max_examples=100)
    @given(valid_mask=st.lists(st.booleans(), min_size=4, max_size=4))
    def test_virtual_env_always_wins_over_candidates(self, valid_mask: list[bool]) -> None:
        """$VIRTUAL_ENV always takes priority over any CWD candidates."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir).resolve()

            # Create a valid VIRTUAL_ENV directory
            venv_dir = tmp_path / "explicit_venv"
            venv_dir.mkdir()
            (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin\n")

            old_virtual_env = os.environ.get("VIRTUAL_ENV")
            old_cwd = os.getcwd()
            try:
                os.environ["VIRTUAL_ENV"] = str(venv_dir)
                os.chdir(tmp_path)

                # Create some candidate directories (valid or not)
                for i, name in enumerate(CANDIDATE_NAMES):
                    candidate_dir = tmp_path / name
                    candidate_dir.mkdir()
                    if valid_mask[i]:
                        (candidate_dir / "pyvenv.cfg").write_text("home = /usr/bin\n")

                result = detect_virtualenv()
                assert result == venv_dir
            finally:
                os.chdir(old_cwd)
                if old_virtual_env is not None:
                    os.environ["VIRTUAL_ENV"] = old_virtual_env
                else:
                    os.environ.pop("VIRTUAL_ENV", None)


class TestPropertyVirtualenvValidation:
    """Feature: virtualenv-config-viewer, Property 2: Virtualenv Validation

    For any directory path, `_is_valid_virtualenv(path)` SHALL return `true`
    if and only if the file `{path}/pyvenv.cfg` exists. Directories without
    `pyvenv.cfg` must always return `false`; directories with `pyvenv.cfg`
    must always return `true`.

    **Validates: Requirements 1.6**
    """

    @settings(max_examples=100)
    @given(has_cfg=st.booleans())
    def test_validation_iff_pyvenv_cfg_exists(self, has_cfg: bool) -> None:
        """A directory is valid iff it contains a pyvenv.cfg file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "test_dir"
            target.mkdir()

            if has_cfg:
                (target / "pyvenv.cfg").write_text("home = /usr/bin\n")

            assert _is_valid_virtualenv(target) == has_cfg

    @settings(max_examples=100)
    @given(
        dir_name=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
            min_size=1,
            max_size=20,
        )
    )
    def test_nonexistent_directory_always_invalid(self, dir_name: str) -> None:
        """A non-existent path is never valid, regardless of its name."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            nonexistent = Path(tmp_dir) / dir_name / "nested"
            assert _is_valid_virtualenv(nonexistent) is False

    @settings(max_examples=100)
    @given(
        extra_files=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-."),
                min_size=1,
                max_size=15,
            ),
            min_size=0,
            max_size=5,
        )
    )
    def test_other_files_dont_affect_validation(self, extra_files: list[str]) -> None:
        """Only pyvenv.cfg matters for validation; other files are irrelevant."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "venv_dir"
            target.mkdir()

            # Create pyvenv.cfg to make it valid
            (target / "pyvenv.cfg").write_text("home = /usr/bin\n")

            # Add extra files — should not change the validation result
            for fname in extra_files:
                # Avoid overwriting pyvenv.cfg itself
                if fname != "pyvenv.cfg":
                    with contextlib.suppress(OSError):
                        (target / fname).write_text("content")

            assert _is_valid_virtualenv(target) is True
