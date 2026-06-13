"""TUI Controller and Navigation for virtualenv-viewer.

Uses the curses module for terminal control (alternate screen, raw mode).
Renders paged content with navigation via arrow keys, and handles
terminal resize, quit, and unhandled error recovery.
"""

import contextlib
import curses
import math
import signal
from collections.abc import Callable
from dataclasses import dataclass, field

from virtualenv_viewer.config_reader import ConfigFiles
from virtualenv_viewer.shell_analyzer import ShellExports


@dataclass
class TuiCallbacks:
    """Callbacks for TUI event handling (editor, restart).

    Attributes:
        on_edit: Called when the user presses 'e'. Should return a tuple of
                 (success, file_modified, status_message).
        on_restart: Called after a successful edit if the file was modified.
                    Should return an optional status message.
        on_refresh: Called after edit if file was modified, to get updated
                    config_files and exports for re-rendering.
    """

    on_edit: Callable[[], tuple[bool, bool, str | None]] | None = None
    on_restart: Callable[[bool], str | None] | None = None
    on_refresh: Callable[[], tuple[ConfigFiles, ShellExports]] | None = None


@dataclass
class AppState:
    """Application state for the TUI controller.

    Attributes:
        venv_name: Display name of the virtualenv (basename).
        content_lines: Pre-rendered flat list of display lines.
        current_page: Current page number (1-indexed).
        total_pages: Total number of pages.
        page_size: Number of content lines per page.
        status_message: Optional status message to display.
    """

    venv_name: str
    content_lines: list[str] = field(default_factory=list)
    current_page: int = 1
    total_pages: int = 1
    page_size: int = 1
    status_message: str | None = None


def render_content(config_files: ConfigFiles, exports: ShellExports) -> list[str]:
    """Pre-render all sections into a flat list of display lines.

    Content rendering order:
    1. pyvenv.cfg header + content lines
    2. Blank separator
    3. postactivate (raw) header + content lines
    4. Blank separator
    5. Shell Exports header with subheaders for variables, aliases, functions

    Args:
        config_files: The configuration files read from the virtualenv.
        exports: Parsed shell exports from the postactivate file.

    Returns:
        A flat list of strings, one per display line.
    """
    lines: list[str] = []

    # Section 1: pyvenv.cfg
    lines.append("═══ pyvenv.cfg ═══")
    if config_files.pyvenv_cfg is not None:
        for line in config_files.pyvenv_cfg.splitlines():
            lines.append(line)
    else:
        lines.append("  (not found)")

    # Blank separator
    lines.append("")

    # Section 2: postactivate (raw)
    lines.append("═══ postactivate (raw) ═══")
    if config_files.postactivate is not None:
        for line in config_files.postactivate.splitlines():
            lines.append(line)
    else:
        lines.append("  (not found)")

    # Blank separator
    lines.append("")

    # Section 3: Shell Exports
    lines.append("═══ Shell Exports ═══")

    # Variables subheader
    lines.append("── Variables ──")
    if exports.variables:
        for var in exports.variables:
            lines.append(f"  {var.name} = {var.value}")
    else:
        lines.append("  (none)")

    # Aliases subheader
    lines.append("── Aliases ──")
    if exports.aliases:
        for alias in exports.aliases:
            lines.append(f"  {alias.name} = {alias.definition}")
    else:
        lines.append("  (none)")

    # Functions subheader
    lines.append("── Functions ──")
    if exports.functions:
        for func in exports.functions:
            lines.append(f"  {func.name}()")
            for body_line in func.body.splitlines():
                lines.append(f"    {body_line}")
    else:
        lines.append("  (none)")

    return lines


def _calculate_pages(total_lines: int, page_size: int) -> int:
    """Calculate total number of pages.

    Args:
        total_lines: Total number of content lines.
        page_size: Number of lines per page.

    Returns:
        Total number of pages (minimum 1).
    """
    if page_size <= 0:
        return 1
    return max(1, math.ceil(total_lines / page_size))


def _clamp_page(page: int, total_pages: int) -> int:
    """Clamp a page number to valid bounds [1, total_pages].

    Args:
        page: Desired page number.
        total_pages: Maximum valid page number.

    Returns:
        Clamped page number.
    """
    return max(1, min(page, total_pages))


def _get_page_lines(content_lines: list[str], page: int, page_size: int) -> list[str]:
    """Get the content lines for a specific page.

    Args:
        content_lines: Full list of pre-rendered content lines.
        page: Page number (1-indexed).
        page_size: Number of lines per page.

    Returns:
        Slice of content lines for the requested page.
    """
    start = (page - 1) * page_size
    end = start + page_size
    return content_lines[start:end]


def _render_screen(stdscr: "curses.window", state: AppState) -> None:
    """Render the current page to the terminal screen.

    Layout:
    - Content area: terminal_rows - 2 lines
    - Status bar (row terminal_rows - 2): virtualenv name | Page X/Y
    - Key help (row terminal_rows - 1): key bindings

    Args:
        stdscr: The curses window.
        state: Current application state.
    """
    stdscr.clear()
    max_y, max_x = stdscr.getmaxyx()

    # Get page lines for current page
    page_lines = _get_page_lines(state.content_lines, state.current_page, state.page_size)

    # Render content area
    for i, line in enumerate(page_lines):
        if i >= max_y - 2:
            break
        # Truncate line to terminal width to avoid curses errors
        display_line = line[: max_x - 1] if max_x > 1 else ""
        with contextlib.suppress(curses.error):
            stdscr.addstr(i, 0, display_line)

    # Status bar (second-to-last row)
    status_row = max_y - 2
    if status_row >= 0:
        status_text = f" Status: {state.venv_name} | Page {state.current_page}/{state.total_pages}"
        if state.status_message:
            status_text += f"  [{state.status_message}]"
        status_text = status_text[: max_x - 1] if max_x > 1 else ""
        try:
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(status_row, 0, status_text.ljust(max_x - 1))
            stdscr.attroff(curses.A_REVERSE)
        except curses.error:
            pass

    # Key help bar (last row)
    help_row = max_y - 1
    if help_row >= 0:
        help_text = " Keys: ↑/↓ navigate | e edit | q quit"
        help_text = help_text[: max_x - 1] if max_x > 1 else ""
        try:
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(help_row, 0, help_text.ljust(max_x - 1))
            stdscr.attroff(curses.A_REVERSE)
        except curses.error:
            pass

    stdscr.refresh()


def _recalculate_state(stdscr: "curses.window", state: AppState) -> None:
    """Recalculate page size and total pages based on current terminal size.

    Preserves the current page position, clamping if necessary.

    Args:
        stdscr: The curses window.
        state: Application state to update in place.
    """
    max_y, _ = stdscr.getmaxyx()
    state.page_size = max(1, max_y - 2)
    state.total_pages = _calculate_pages(len(state.content_lines), state.page_size)
    state.current_page = _clamp_page(state.current_page, state.total_pages)


def _handle_resize(stdscr: "curses.window", state: AppState) -> None:
    """Handle terminal resize event.

    Recalculates page size and re-renders the screen.

    Args:
        stdscr: The curses window.
        state: Application state to update.
    """
    curses.update_lines_cols()
    _recalculate_state(stdscr, state)
    _render_screen(stdscr, state)


def _curses_main(
    stdscr: "curses.window",
    config_files: ConfigFiles,
    exports: ShellExports,
    venv_name: str,
    callbacks: TuiCallbacks | None = None,
) -> None:
    """Main curses event loop.

    Args:
        stdscr: The curses window provided by curses.wrapper.
        config_files: Configuration files to display.
        exports: Parsed shell exports to display.
        venv_name: Display name of the virtualenv.
        callbacks: Optional callbacks for editor and restart integration.
    """
    # Hide cursor
    curses.curs_set(0)

    # Set up non-blocking resize handling
    stdscr.keypad(True)

    # Pre-render content
    content_lines = render_content(config_files, exports)

    # Initialize state
    max_y, _ = stdscr.getmaxyx()
    page_size = max(1, max_y - 2)
    total_pages = _calculate_pages(len(content_lines), page_size)

    state = AppState(
        venv_name=venv_name,
        content_lines=content_lines,
        current_page=1,
        total_pages=total_pages,
        page_size=page_size,
    )

    # Set up SIGWINCH handler for terminal resize
    resize_flag = [False]

    def _on_resize(signum: int, frame: object) -> None:
        resize_flag[0] = True

    old_handler = signal.signal(signal.SIGWINCH, _on_resize)

    try:
        # Initial render
        _render_screen(stdscr, state)

        # Event loop
        while True:
            # Check for resize
            if resize_flag[0]:
                resize_flag[0] = False
                _handle_resize(stdscr, state)

            try:
                key = stdscr.getch()
            except curses.error:
                continue

            if key == -1:
                continue

            if key == curses.KEY_RESIZE:
                _handle_resize(stdscr, state)
            elif key == curses.KEY_DOWN:
                # Next page
                new_page = _clamp_page(state.current_page + 1, state.total_pages)
                if new_page != state.current_page:
                    state.current_page = new_page
                    _render_screen(stdscr, state)
            elif key == curses.KEY_UP:
                # Previous page
                new_page = _clamp_page(state.current_page - 1, state.total_pages)
                if new_page != state.current_page:
                    state.current_page = new_page
                    _render_screen(stdscr, state)
            elif key == ord("q") or key == ord("Q"):
                # Quit
                break
            elif key == ord("e") or key == ord("E"):
                # Edit handler
                if callbacks and callbacks.on_edit:
                    success, file_modified, error_msg = callbacks.on_edit()
                    if not success:
                        state.status_message = error_msg or "Edit failed"
                    elif file_modified:
                        # Refresh content if file was modified
                        if callbacks.on_refresh:
                            new_configs, new_exports = callbacks.on_refresh()
                            state.content_lines = render_content(new_configs, new_exports)
                            _recalculate_state(stdscr, state)

                        # Trigger restart if enabled
                        if callbacks.on_restart:
                            restart_msg = callbacks.on_restart(file_modified)
                            if restart_msg:
                                state.status_message = restart_msg
                            else:
                                state.status_message = "File updated"
                        else:
                            state.status_message = "File updated"
                    else:
                        state.status_message = "No changes detected"
                else:
                    state.status_message = "Edit not configured"
                _render_screen(stdscr, state)
    finally:
        # Restore previous SIGWINCH handler
        signal.signal(signal.SIGWINCH, old_handler)


def run_tui(
    config_files: ConfigFiles,
    exports: ShellExports,
    venv_name: str,
    callbacks: TuiCallbacks | None = None,
) -> None:
    """Run the TUI viewer.

    Enters the curses alternate screen, renders content, handles navigation,
    and restores terminal state on exit or error.

    Args:
        config_files: Configuration files read from the virtualenv.
        exports: Parsed shell exports from the postactivate file.
        venv_name: Display name of the virtualenv (basename of venv path).
        callbacks: Optional callbacks for editor and restart integration.
    """
    curses.wrapper(lambda stdscr: _curses_main(stdscr, config_files, exports, venv_name, callbacks))
