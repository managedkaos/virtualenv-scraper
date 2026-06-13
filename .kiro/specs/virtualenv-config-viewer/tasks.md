# Implementation Plan: virtualenv-config-viewer

## Overview

Implement an interactive terminal UI for viewing virtualenv configuration files in three languages (Python, Rust, Go) with a top-level Makefile for orchestration. Each implementation follows the same component architecture: Virtualenv Detector → Config Reader → Shell Analyzer → TUI Controller with Navigation, Editor Launcher, and Restart Handler.

The implementation proceeds by building shared infrastructure first (project scaffolding, build system), then implementing core components language-by-language, and finally wiring everything together with integration tests.

## Tasks

- [ ] 1. Set up project structure and build system
  - [ ] 1.1 Create top-level Makefile with lint, test, and build targets
    - Create `Makefile` at repository root that delegates to `python/Makefile`, `rust/Makefile`, and `go/Makefile`
    - Implement sequential execution with error propagation (halt on first failure, print failing subdirectory to stderr, exit non-zero)
    - `make lint` delegates to all three subdirectories
    - `make test` delegates to all three subdirectories
    - `make build` delegates to Rust and Go subdirectories only (Python is interpreted)
    - Exit with status 0 when all subdirectory targets succeed
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ] 1.2 Create Python project scaffolding
    - Create `python/` directory with `pyproject.toml`, `src/virtualenv_viewer/` package structure
    - Create `python/Makefile` with `lint` (ruff/mypy), `test` (pytest), and `build` (no-op or wheel) targets
    - Add `python/src/virtualenv_viewer/__init__.py` and `python/src/virtualenv_viewer/__main__.py` entry point stub
    - _Requirements: 8.1, 8.4, 8.5_

  - [ ] 1.3 Create Rust project scaffolding
    - Create `rust/` directory with `Cargo.toml` including dependencies: `clap`, `ratatui`, `crossterm`, `regex`
    - Create `rust/src/main.rs` entry point stub
    - Create `rust/Makefile` with `lint` (cargo clippy + cargo fmt --check), `test` (cargo test), and `build` (cargo build --release) targets
    - _Requirements: 8.2, 8.4, 8.5_

  - [ ] 1.4 Create Go project scaffolding
    - Create `go/` directory with `go.mod` module file
    - Add dependencies: `bubbletea`, `lipgloss`, `cobra`
    - Create `go/cmd/virtualenv-viewer/main.go` entry point stub
    - Create `go/Makefile` with `lint` (golangci-lint), `test` (go test ./...), and `build` (go build) targets
    - _Requirements: 8.3, 8.4, 8.5_

- [ ] 2. Implement Virtualenv Detector (all languages)
  - [ ] 2.1 Implement Virtualenv Detector in Python
    - Create `python/src/virtualenv_viewer/detector.py`
    - Implement `detect_virtualenv()` function using `os.environ` and `pathlib.Path`
    - Priority order: `$VIRTUAL_ENV` → `$PWD/.env` → `$PWD/.venv` → `$PWD/venv` → `$PWD/env`
    - Validate by checking for `pyvenv.cfg` file existence
    - Return path on success; print error and `sys.exit(1)` on failure
    - Handle case where `VIRTUAL_ENV` is set but invalid (specific error message)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [ ]* 2.2 Write unit tests for Python Virtualenv Detector
    - Test all detection priority paths using temp directories with `pyvenv.cfg`
    - Test error cases: VIRTUAL_ENV set but invalid, no virtualenv found
    - Test that detection stops at first valid match
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [ ] 2.3 Implement Virtualenv Detector in Rust
    - Create `rust/src/detector.rs` module
    - Implement `detect_virtualenv()` returning `Result<PathBuf, DetectionError>`
    - Use `std::env::var()`, `std::path::PathBuf`, `std::fs::metadata`
    - Same priority order and validation logic as Python
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [ ]* 2.4 Write unit tests for Rust Virtualenv Detector
    - Test detection priority chain with temp directories
    - Test error cases and validation logic
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [ ] 2.5 Implement Virtualenv Detector in Go
    - Create `go/internal/detector/detector.go`
    - Implement `DetectVirtualenv()` returning `(string, error)`
    - Use `os.Getenv()`, `filepath` package, `os.Stat`
    - Same priority order and validation logic as Python
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [ ]* 2.6 Write unit tests for Go Virtualenv Detector
    - Test detection priority chain with temp directories
    - Test error cases and validation logic
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

- [ ] 3. Implement Config Reader (all languages)
  - [ ] 3.1 Implement Config Reader in Python
    - Create `python/src/virtualenv_viewer/config_reader.py`
    - Implement `read_configs(venv_path)` returning a `ConfigFiles` dataclass
    - Read `{venv_path}/pyvenv.cfg` and `{venv_path}/bin/postactivate`
    - Return `None` for missing or unreadable files (no error displayed)
    - Track `postactivate_path` and `postactivate_mtime` for editor support
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 3.2 Write unit tests for Python Config Reader
    - Test reading valid config files
    - Test graceful handling of missing files and permission errors
    - Test "no config files found" message path
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ] 3.3 Implement Config Reader in Rust
    - Create `rust/src/config_reader.rs` module
    - Implement `read_configs(venv_path: &Path) -> ConfigFiles` struct
    - Use `std::fs::read_to_string` with graceful error handling via `Option`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 3.4 Write unit tests for Rust Config Reader
    - Test reading valid config files and graceful missing file handling
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ] 3.5 Implement Config Reader in Go
    - Create `go/internal/config/reader.go`
    - Implement `ReadConfigs(venvPath string) ConfigFiles` struct
    - Use `os.ReadFile` with graceful error handling
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 3.6 Write unit tests for Go Config Reader
    - Test reading valid config files and graceful missing file handling
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [ ] 4. Implement Shell Analyzer (all languages)
  - [ ] 4.1 Implement Shell Analyzer in Python
    - Create `python/src/virtualenv_viewer/shell_analyzer.py`
    - Implement `analyze_shell(content)` returning a `ShellExports` dataclass
    - Use `re` module for regex-based parsing of exports, aliases, and functions
    - Support both bash and zsh syntax conventions
    - Implement last-write-wins for duplicate definitions
    - Display literal unresolved variable references (no expansion)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ]* 4.2 Write unit tests for Python Shell Analyzer
    - Test parsing of export statements, aliases, and function definitions
    - Test last-write-wins behavior for duplicates
    - Test bash and zsh syntax variants
    - Test empty script (no exports detected message path)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ] 4.3 Implement Shell Analyzer in Rust
    - Create `rust/src/shell_analyzer.rs` module
    - Implement `analyze_shell(content: &str) -> ShellExports` using the `regex` crate
    - Same parsing logic and last-write-wins semantics as Python
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ]* 4.4 Write unit tests for Rust Shell Analyzer
    - Test parsing of exports, aliases, functions, duplicates, and empty input
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ] 4.5 Implement Shell Analyzer in Go
    - Create `go/internal/analyzer/analyzer.go`
    - Implement `AnalyzeShell(content string) ShellExports` using `regexp` package
    - Same parsing logic and last-write-wins semantics as Python
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ]* 4.6 Write unit tests for Go Shell Analyzer
    - Test parsing of exports, aliases, functions, duplicates, and empty input
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [ ] 5. Checkpoint - Core logic validation
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement App Options / Configuration (all languages)
  - [ ] 6.1 Implement App Options in Python
    - Create `python/src/virtualenv_viewer/options.py`
    - Use `argparse` for CLI flag `--restart-on-edit` / `--no-restart-on-edit`
    - Read `VENV_VIEWER_RESTART_ON_EDIT` environment variable
    - Read `~/.virtualenv-viewer.toml` config file (use `tomllib` or `tomli`)
    - Implement precedence: CLI > env var > config file > default (disabled)
    - _Requirements: 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 6.2 Write unit tests for Python App Options
    - Test precedence logic with various combinations of CLI, env, and config
    - Test default value when no source specifies the option
    - _Requirements: 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ] 6.3 Implement App Options in Rust
    - Create `rust/src/options.rs` module
    - Use `clap` for CLI parsing, `std::env` for env var, `toml` crate for config file
    - Implement same precedence logic
    - _Requirements: 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 6.4 Write unit tests for Rust App Options
    - Test precedence logic
    - _Requirements: 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ] 6.5 Implement App Options in Go
    - Create `go/internal/options/options.go`
    - Use `cobra` or `flag` for CLI parsing, `os.Getenv` for env var, TOML library for config file
    - Implement same precedence logic
    - _Requirements: 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 6.6 Write unit tests for Go App Options
    - Test precedence logic
    - _Requirements: 6.2, 6.3, 6.4, 6.5, 6.6_

- [ ] 7. Implement TUI Controller and Navigation (all languages)
  - [ ] 7.1 Implement TUI Controller and Navigation in Python
    - Create `python/src/virtualenv_viewer/tui.py`
    - Use `curses` module for terminal control (alternate screen, raw mode)
    - Implement content rendering pipeline: pre-render all sections into flat line list
    - Implement paging logic: `page_size = terminal_rows - 2`, display page indicator and status bar
    - Handle `↑`/`↓` for page navigation with clamping at boundaries
    - Handle terminal resize (`SIGWINCH`) to recalculate page size and re-render
    - Handle `q` to quit (restore terminal state within 100ms)
    - Restore terminal state on unhandled errors
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 7.1, 7.2, 7.3_

  - [ ] 7.2 Implement TUI Controller and Navigation in Rust
    - Create `rust/src/tui.rs` module
    - Use `ratatui` + `crossterm` for immediate-mode rendering
    - Implement same content rendering pipeline, paging logic, and key bindings
    - Handle terminal resize events via crossterm
    - Implement clean shutdown on `q` and on panic (restore terminal)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 7.1, 7.2, 7.3_

  - [ ] 7.3 Implement TUI Controller and Navigation in Go
    - Create `go/internal/tui/tui.go`
    - Use `bubbletea` (Elm Architecture) + `lipgloss` for styling
    - Implement Model-View-Update pattern with same paging logic and key bindings
    - Handle terminal resize via bubbletea's `WindowSizeMsg`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 7.1, 7.2, 7.3_

- [ ] 8. Implement Editor Launcher (all languages)
  - [ ] 8.1 Implement Editor Launcher in Python
    - Create `python/src/virtualenv_viewer/editor.py`
    - Check `$EDITOR` is set and non-empty; display error if not
    - Check postactivate file exists; display error if not
    - Record file mtime, suspend TUI, spawn editor via `subprocess.run()`
    - Handle editor launch failure (command not found); display error
    - On editor exit, resume TUI, compare mtime, refresh content if changed
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ] 8.2 Implement Editor Launcher in Rust
    - Create `rust/src/editor.rs` module
    - Use `std::process::Command` to spawn editor
    - Same logic: check EDITOR, check file exists, record mtime, suspend/resume TUI, compare mtime
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ] 8.3 Implement Editor Launcher in Go
    - Create `go/internal/editor/editor.go`
    - Use `os/exec` to spawn editor
    - Same logic: check EDITOR, check file exists, record mtime, suspend/resume TUI, compare mtime
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [ ] 9. Implement Restart Handler (all languages)
  - [ ] 9.1 Implement Restart Handler in Python
    - Create `python/src/virtualenv_viewer/restart.py`
    - Execute deactivate/reactivate sequence when restart-on-edit is enabled and file was modified
    - Display confirmation message on success
    - Display error message on failure, leave virtualenv deactivated
    - _Requirements: 6.1, 6.7_

  - [ ] 9.2 Implement Restart Handler in Rust
    - Create `rust/src/restart.rs` module
    - Same deactivate/reactivate logic with success/failure messages
    - _Requirements: 6.1, 6.7_

  - [ ] 9.3 Implement Restart Handler in Go
    - Create `go/internal/restart/restart.go`
    - Same deactivate/reactivate logic with success/failure messages
    - _Requirements: 6.1, 6.7_

- [ ] 10. Checkpoint - Full feature validation
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Wire entry points and integrate all components
  - [ ] 11.1 Wire Python entry point
    - Update `python/src/virtualenv_viewer/__main__.py` to orchestrate full flow:
    - Parse options → detect virtualenv → read configs → analyze shell → run TUI
    - Connect editor launcher and restart handler to TUI event loop
    - _Requirements: 1.1, 2.5, 4.1, 5.1, 6.1, 7.1_

  - [ ] 11.2 Wire Rust entry point
    - Update `rust/src/main.rs` to orchestrate full flow
    - Wire all modules together: options → detector → config_reader → shell_analyzer → tui
    - Connect editor and restart handler to TUI event loop
    - _Requirements: 1.1, 2.5, 4.1, 5.1, 6.1, 7.1_

  - [ ] 11.3 Wire Go entry point
    - Update `go/cmd/virtualenv-viewer/main.go` to orchestrate full flow
    - Wire all packages together: options → detector → config → analyzer → tui
    - Connect editor and restart handler to TUI event loop
    - _Requirements: 1.1, 2.5, 4.1, 5.1, 6.1, 7.1_

- [ ] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- The three language implementations share identical logic but use idiomatic libraries and patterns
- No property-based tests are included since the design does not define correctness properties
- Unit tests validate specific examples and edge cases for core parsing and detection logic

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3", "1.4"] },
    { "id": 1, "tasks": ["2.1", "2.3", "2.5"] },
    { "id": 2, "tasks": ["2.2", "2.4", "2.6", "3.1", "3.3", "3.5"] },
    { "id": 3, "tasks": ["3.2", "3.4", "3.6", "4.1", "4.3", "4.5"] },
    { "id": 4, "tasks": ["4.2", "4.4", "4.6", "6.1", "6.3", "6.5"] },
    { "id": 5, "tasks": ["6.2", "6.4", "6.6", "7.1", "7.2", "7.3"] },
    { "id": 6, "tasks": ["8.1", "8.2", "8.3", "9.1", "9.2", "9.3"] },
    { "id": 7, "tasks": ["11.1", "11.2", "11.3"] }
  ]
}
```
