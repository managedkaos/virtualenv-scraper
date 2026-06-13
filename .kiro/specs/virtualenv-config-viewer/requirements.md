# Requirements Document

## Introduction

An interactive terminal UI application that displays the contents of configuration files associated with the currently active Python virtual environment. The application detects the active virtualenv, reads relevant config files (`pyvenv.cfg`, `postactivate`), and presents shell exports (variables, aliases, functions) in a navigable paged view. The user can edit the `postactivate` file inline and optionally restart the virtualenv on changes. The application is implemented in three languages (Python, Rust, Go) within a mono-repo structure, orchestrated by a top-level Makefile delegating to per-language sub-Makefiles.

Target platforms: Linux and macOS.

## Glossary

- **Viewer**: The interactive terminal UI application that displays virtualenv configuration details
- **Active_Virtualenv**: The Python virtual environment currently active in the user's shell, resolved by detection order
- **Virtualenv_Detector**: The component that locates the active virtualenv directory using a prioritized detection strategy
- **Config_Reader**: The component responsible for reading and parsing virtualenv configuration files
- **Shell_Analyzer**: The component that extracts exported variables, aliases, and functions from shell activation scripts
- **Postactivate_File**: A shell script executed after virtualenv activation, located inside the virtualenv directory
- **Pyvenv_Cfg**: The `pyvenv.cfg` configuration file located at the root of a virtualenv directory
- **Navigation_Controller**: The component handling keyboard input for paging, editing, and quitting
- **Editor_Launcher**: The component that invokes the user's preferred editor via the `$EDITOR` environment variable
- **Build_System**: The top-level Makefile and per-language sub-Makefiles that orchestrate lint, test, and build tasks

## Requirements

### Requirement 1: Virtualenv Detection

**User Story:** As a developer, I want the viewer to automatically detect my active virtualenv, so that I do not need to manually specify its path.

#### Acceptance Criteria

1. WHEN the `VIRTUAL_ENV` environment variable is set and its value points to a valid virtualenv directory, THE Virtualenv_Detector SHALL use its value as the active virtualenv path
2. IF the `VIRTUAL_ENV` environment variable is not set, THEN THE Virtualenv_Detector SHALL check for a `.env` directory relative to the current working directory (`$PWD/.env`)
3. IF neither `VIRTUAL_ENV` nor `$PWD/.env` yields a valid virtualenv directory, THEN THE Virtualenv_Detector SHALL search the following directories relative to `$PWD` in order: `.venv`, `venv`, `env`
4. IF no valid virtualenv directory is found after exhausting all detection strategies, THEN THE Virtualenv_Detector SHALL display an error message indicating the detection paths that were attempted and exit with a non-zero status code
5. THE Virtualenv_Detector SHALL use the first matching valid virtualenv found in priority order and stop searching
6. THE Virtualenv_Detector SHALL consider a directory a valid virtualenv if and only if it contains a `pyvenv.cfg` file
7. IF the `VIRTUAL_ENV` environment variable is set but its value does not point to a valid virtualenv directory, THEN THE Virtualenv_Detector SHALL display an error message indicating that the path in `VIRTUAL_ENV` is not a valid virtualenv and exit with a non-zero status code

### Requirement 2: Configuration File Reading

**User Story:** As a developer, I want to view the contents of my virtualenv's config files, so that I can understand how my environment is configured.

#### Acceptance Criteria

1. WHEN an active virtualenv is detected, THE Config_Reader SHALL read the `pyvenv.cfg` file from the virtualenv root directory
2. WHEN an active virtualenv is detected, THE Config_Reader SHALL read the `postactivate` file from the virtualenv's `bin/` directory
3. IF a configuration file does not exist at its expected location, THEN THE Config_Reader SHALL skip that file without displaying an error to the user
4. IF a configuration file exists but cannot be read due to insufficient permissions or an I/O error, THEN THE Config_Reader SHALL skip that file without displaying an error to the user
5. WHEN one or more configuration files are successfully read, THE Config_Reader SHALL display their raw text contents in the Viewer in the following order: `pyvenv.cfg` first, then `postactivate`
6. IF no configuration files are successfully read, THEN THE Config_Reader SHALL display an informative message indicating that no configuration files were found

### Requirement 3: Shell Export Analysis

**User Story:** As a developer, I want to see the final resolved values of variables, aliases, and functions exported during virtualenv activation, so that I can understand what my shell session inherits.

#### Acceptance Criteria

1. WHEN the `postactivate` shell script is present, THE Shell_Analyzer SHALL extract the name and final value of each variable exported to the shell via `export` statements
2. WHEN the `postactivate` shell script is present, THE Shell_Analyzer SHALL extract the name and final value of each alias defined via `alias` statements
3. WHEN the `postactivate` shell script is present, THE Shell_Analyzer SHALL extract the name and body of each function defined in the script
4. WHEN a variable, alias, or function is defined multiple times in the script, THE Shell_Analyzer SHALL report only the final assigned value
5. THE Shell_Analyzer SHALL support both bash and zsh syntax conventions for variable exports, alias definitions, and function definitions
6. WHEN a variable's value references another variable (e.g., `export PATH="$HOME/bin:$PATH"`), THE Shell_Analyzer SHALL display the literal unresolved text as written in the script
7. IF no exported variables, aliases, or functions are found in the activation scripts, THEN THE Shell_Analyzer SHALL display a message indicating no shell exports were detected

### Requirement 4: Interactive Navigation

**User Story:** As a developer, I want to navigate paged output with arrow keys, so that I can browse long configuration details without scrolling past content.

#### Acceptance Criteria

1. WHILE the Viewer is displaying content, WHEN the user presses the down arrow key, THE Navigation_Controller SHALL advance to the next page
2. WHILE the Viewer is displaying content, WHEN the user presses the up arrow key, THE Navigation_Controller SHALL return to the previous page
3. WHILE the Viewer is on the first page, WHEN the user presses the up arrow key, THE Navigation_Controller SHALL remain on the first page without error
4. WHILE the Viewer is on the last page, WHEN the user presses the down arrow key, THE Navigation_Controller SHALL remain on the last page without error
5. THE Viewer SHALL calculate page size as the terminal's current row count minus 2 rows reserved for the status bar and page indicator
6. WHEN the terminal is resized, THE Viewer SHALL recalculate the page size and re-render the current content accordingly
7. THE Viewer SHALL display a page position indicator showing the current page number and total page count

### Requirement 5: Inline Editing of Postactivate File

**User Story:** As a developer, I want to edit the postactivate file directly from the viewer, so that I can adjust my virtualenv activation settings without switching contexts.

#### Acceptance Criteria

1. WHEN the user presses `e` and the postactivate file exists, THE Editor_Launcher SHALL open the postactivate file in the editor specified by the `EDITOR` environment variable
2. WHEN the editor process exits, THE Viewer SHALL return to displaying the virtualenv configuration on the same page the user was viewing before editing
3. IF the `EDITOR` environment variable is not set or is empty, THEN THE Editor_Launcher SHALL display an error message indicating that no editor is configured and remain in the Viewer
4. WHEN the postactivate file has been modified after editing (determined by file modification timestamp change), THE Viewer SHALL refresh its displayed content to reflect the changes
5. IF the user presses `e` and the postactivate file does not exist, THEN THE Editor_Launcher SHALL display an error message indicating the file was not found and remain in the Viewer
6. IF the `EDITOR` environment variable is set but the specified editor command fails to launch, THEN THE Editor_Launcher SHALL display an error message indicating the editor could not be started and remain in the Viewer

### Requirement 6: Optional Virtualenv Restart After Edit

**User Story:** As a developer, I want the option to automatically restart my virtualenv after editing the postactivate file, so that my changes take effect immediately.

#### Acceptance Criteria

1. WHERE the restart-on-edit option is enabled, WHEN the postactivate file is modified, THE Viewer SHALL restart the active virtualenv by deactivating and reactivating it and SHALL display a confirmation message indicating the virtualenv was restarted
2. THE Viewer SHALL support enabling the restart-on-edit option via a command-line flag
3. THE Viewer SHALL support enabling the restart-on-edit option via an environment variable
4. THE Viewer SHALL support enabling the restart-on-edit option via a configuration file
5. WHEN multiple configuration sources specify conflicting restart-on-edit values, THE Viewer SHALL use the following precedence: command-line flag overrides environment variable, which overrides configuration file
6. IF no configuration source specifies the restart-on-edit option, THEN THE Viewer SHALL default to restart-on-edit disabled
7. IF the virtualenv restart fails during deactivation or reactivation, THEN THE Viewer SHALL display an error message indicating the restart failure and SHALL leave the virtualenv in its deactivated state

### Requirement 7: Quit Command

**User Story:** As a developer, I want to quit the viewer by pressing `q`, so that I can return to my shell session.

#### Acceptance Criteria

1. WHEN the user presses `q` on any page, THE Viewer SHALL exit and return control to the shell within 100 milliseconds
2. WHEN the Viewer exits, THE Viewer SHALL leave the alternate screen buffer, restore cursor visibility, and restore the terminal input mode to its pre-launch state
3. IF the Viewer terminates due to an unhandled error, THEN THE Viewer SHALL attempt to restore the terminal to its pre-launch state before exiting

### Requirement 8: Multi-Language Implementation Structure

**User Story:** As a project maintainer, I want the application implemented in Python, Rust, and Go in separate subdirectories, so that each implementation is self-contained and independently buildable.

#### Acceptance Criteria

1. THE Build_System SHALL contain a Python implementation in a `python/` subdirectory with a valid Python project configuration file (e.g., `pyproject.toml` or `setup.py`)
2. THE Build_System SHALL contain a Rust implementation in a `rust/` subdirectory with a valid `Cargo.toml` manifest
3. THE Build_System SHALL contain a Go implementation in a `go/` subdirectory with a valid `go.mod` module file
4. THE Build_System SHALL provide a Makefile in each language subdirectory that supports at minimum the `lint`, `test`, and `build` targets
5. THE Build_System SHALL ensure each language subdirectory is independently buildable without requiring files or build artifacts from sibling language subdirectories

### Requirement 9: Top-Level Build Orchestration

**User Story:** As a project maintainer, I want a top-level Makefile that delegates tasks to each language's sub-Makefile, so that I can lint, test, and build all implementations with a single command.

#### Acceptance Criteria

1. THE Build_System SHALL provide a top-level Makefile at the repository root that delegates to sub-Makefiles in the Python, Rust, and Go subdirectories
2. WHEN the user invokes `make lint`, THE Build_System SHALL execute the lint target in each language subdirectory's sub-Makefile, running formatting checks and static analysis for Python, Rust, and Go
3. WHEN the user invokes `make test`, THE Build_System SHALL execute the test target in each language subdirectory's sub-Makefile, running the test suite for Python, Rust, and Go
4. WHEN the user invokes `make build`, THE Build_System SHALL execute the build target in the Rust and Go subdirectories, producing compiled binary artifacts for each
5. IF a sub-Makefile target fails, THEN THE Build_System SHALL halt execution of remaining subdirectory targets, print an error message to stderr indicating the name of the language subdirectory that failed, and exit with a non-zero status code
6. WHEN the user invokes `make lint`, `make test`, or `make build`, THE Build_System SHALL execute each language subdirectory's target sequentially and exit with status code 0 if all subdirectory targets complete successfully
