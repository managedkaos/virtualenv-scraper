"""Entry point for virtualenv-viewer.

Orchestrates the full application flow:
1. Parse options (CLI, env, config file)
2. Detect active virtualenv
3. Read configuration files
4. Analyze shell exports from postactivate
5. Run the TUI with editor and restart handlers connected
"""

import curses

from virtualenv_viewer.config_reader import ConfigFiles, read_configs
from virtualenv_viewer.detector import detect_virtualenv
from virtualenv_viewer.editor import launch_editor
from virtualenv_viewer.options import AppOptions, parse_options
from virtualenv_viewer.restart import handle_restart
from virtualenv_viewer.shell_analyzer import ShellExports, analyze_shell
from virtualenv_viewer.tui import TuiCallbacks, run_tui


def main() -> None:
    """Main entry point for the virtualenv-viewer application."""
    # 1. Parse options
    options: AppOptions = parse_options()

    # 2. Detect virtualenv (exits on failure)
    venv_path = detect_virtualenv()
    venv_name = venv_path.name

    # 3. Read configuration files
    config_files: ConfigFiles = read_configs(venv_path)

    # 4. Analyze shell exports (if postactivate exists)
    exports: ShellExports
    if config_files.postactivate is not None:
        exports = analyze_shell(config_files.postactivate)
    else:
        exports = ShellExports()

    # 5. Build TUI callbacks for editor and restart integration
    # Capture postactivate_path for the editor (it doesn't change across refreshes)
    postactivate_path = config_files.postactivate_path

    def on_edit() -> tuple[bool, bool, str | None]:
        """Handle the 'e' key press: launch editor for postactivate file.

        Returns:
            Tuple of (success, file_modified, error_message).
        """

        def suspend_tui() -> None:
            curses.endwin()

        def resume_tui() -> None:
            stdscr = curses.initscr()
            stdscr.refresh()
            curses.doupdate()

        result = launch_editor(
            postactivate_path=postactivate_path,
            suspend_tui=suspend_tui,
            resume_tui=resume_tui,
        )
        return (result.success, result.file_modified, result.error_message)

    def on_restart(file_modified: bool) -> str | None:
        """Handle restart after edit if enabled.

        Args:
            file_modified: Whether the postactivate file was modified.

        Returns:
            Status message to display, or None if no restart was attempted.
        """
        restart_result = handle_restart(
            venv_path=venv_path,
            restart_on_edit=options.restart_on_edit,
            file_was_modified=file_modified,
        )
        if restart_result is not None:
            return restart_result.message
        return None

    def on_refresh() -> tuple[ConfigFiles, ShellExports]:
        """Refresh config files and shell exports after an edit.

        Returns:
            Updated ConfigFiles and ShellExports.
        """
        new_config_files = read_configs(venv_path)
        new_exports: ShellExports
        if new_config_files.postactivate is not None:
            new_exports = analyze_shell(new_config_files.postactivate)
        else:
            new_exports = ShellExports()
        return (new_config_files, new_exports)

    callbacks = TuiCallbacks(
        on_edit=on_edit,
        on_restart=on_restart,
        on_refresh=on_refresh,
    )

    # 6. Run the TUI
    run_tui(config_files, exports, venv_name, callbacks)


if __name__ == "__main__":
    main()
