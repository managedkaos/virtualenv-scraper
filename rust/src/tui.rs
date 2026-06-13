use std::io::{self, stdout, Stdout};
use std::path::Path;

use crossterm::{
    event::{self, Event, KeyCode, KeyEventKind},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph},
    Frame, Terminal,
};

use crate::config_reader::ConfigFiles;
use crate::editor::{self, EditorResult};
use crate::options::AppOptions;
use crate::restart::{self, RestartResult};
use crate::shell_analyzer::ShellExports;

/// Application state for the TUI.
struct App {
    /// Pre-rendered content lines.
    content_lines: Vec<String>,
    /// Current page index (0-based internally, displayed as 1-based).
    current_page: usize,
    /// Total number of pages.
    total_pages: usize,
    /// Number of content lines per page.
    page_size: usize,
    /// Name of the virtualenv (for status bar display).
    venv_name: String,
    /// Whether the user has requested to quit.
    should_quit: bool,
    /// Status message to show (e.g., editor errors).
    status_message: Option<String>,
}

impl App {
    /// Create a new App from config files and shell exports.
    fn new(config_files: &ConfigFiles, exports: &ShellExports, venv_name: &str) -> Self {
        let content_lines = render_content(config_files, exports);
        App {
            content_lines,
            current_page: 0,
            total_pages: 1,
            page_size: 1,
            venv_name: venv_name.to_string(),
            should_quit: false,
            status_message: None,
        }
    }

    /// Recalculate paging based on terminal height.
    fn recalculate_pages(&mut self, terminal_height: u16) {
        // page_size = terminal_rows - 2 (status bar + key hints)
        let height = terminal_height as usize;
        self.page_size = if height > 2 { height - 2 } else { 1 };
        self.total_pages = if self.content_lines.is_empty() {
            1
        } else {
            (self.content_lines.len()).div_ceil(self.page_size)
        };
        // Clamp current page
        if self.current_page >= self.total_pages {
            self.current_page = self.total_pages - 1;
        }
    }

    /// Advance to the next page (clamped at last page).
    fn next_page(&mut self) {
        if self.current_page < self.total_pages - 1 {
            self.current_page += 1;
        }
    }

    /// Go to the previous page (clamped at first page).
    fn prev_page(&mut self) {
        if self.current_page > 0 {
            self.current_page -= 1;
        }
    }

    /// Get the content lines for the current page.
    fn current_page_lines(&self) -> &[String] {
        let start = self.current_page * self.page_size;
        let end = std::cmp::min(start + self.page_size, self.content_lines.len());
        if start >= self.content_lines.len() {
            &[]
        } else {
            &self.content_lines[start..end]
        }
    }
}

/// Pre-render all content into a flat list of display lines.
fn render_content(config_files: &ConfigFiles, exports: &ShellExports) -> Vec<String> {
    let mut lines = Vec::new();

    // Section 1: pyvenv.cfg
    if let Some(ref cfg) = config_files.pyvenv_cfg {
        lines.push("═══ pyvenv.cfg ═══".to_string());
        for line in cfg.lines() {
            lines.push(line.to_string());
        }
        lines.push(String::new());
    }

    // Section 2: postactivate (raw)
    if let Some(ref post) = config_files.postactivate {
        lines.push("═══ postactivate (raw) ═══".to_string());
        for line in post.lines() {
            lines.push(line.to_string());
        }
        lines.push(String::new());
    }

    // Section 3: Shell Exports
    let has_exports = !exports.variables.is_empty()
        || !exports.aliases.is_empty()
        || !exports.functions.is_empty();

    if has_exports {
        lines.push("═══ Shell Exports ═══".to_string());

        if !exports.variables.is_empty() {
            lines.push("── Variables ──".to_string());
            for var in &exports.variables {
                lines.push(format!("  {} = {}", var.name, var.value));
            }
        }

        if !exports.aliases.is_empty() {
            lines.push("── Aliases ──".to_string());
            for alias in &exports.aliases {
                lines.push(format!("  {} = {}", alias.name, alias.definition));
            }
        }

        if !exports.functions.is_empty() {
            lines.push("── Functions ──".to_string());
            for func in &exports.functions {
                lines.push(format!("  {}()", func.name));
                for body_line in func.body.lines() {
                    lines.push(format!("    {}", body_line));
                }
            }
        }
    } else if config_files.postactivate.is_some() {
        lines.push("═══ Shell Exports ═══".to_string());
        lines.push("  No shell exports detected.".to_string());
    }

    // If nothing at all was rendered
    if lines.is_empty() {
        lines.push("No configuration files found.".to_string());
    }

    lines
}

/// Initialize the terminal for TUI rendering.
fn setup_terminal() -> io::Result<Terminal<CrosstermBackend<Stdout>>> {
    enable_raw_mode()?;
    let mut stdout = stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let terminal = Terminal::new(backend)?;
    Ok(terminal)
}

/// Restore the terminal to its pre-launch state.
fn restore_terminal(terminal: &mut Terminal<CrosstermBackend<Stdout>>) -> io::Result<()> {
    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
    terminal.show_cursor()?;
    Ok(())
}

/// Draw the UI frame.
fn ui(frame: &mut Frame, app: &App) {
    let size = frame.area();

    // Split into content area and status bar (2 lines at bottom)
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Min(1),    // Content area
            Constraint::Length(2), // Status bar (2 lines)
        ])
        .split(size);

    // Render content area
    let page_lines = app.current_page_lines();
    let text_lines: Vec<Line> = page_lines
        .iter()
        .map(|l| {
            if l.starts_with("═══") {
                Line::from(Span::styled(
                    l.as_str(),
                    Style::default()
                        .fg(Color::Cyan)
                        .add_modifier(Modifier::BOLD),
                ))
            } else if l.starts_with("──") {
                Line::from(Span::styled(l.as_str(), Style::default().fg(Color::Yellow)))
            } else {
                Line::from(l.as_str())
            }
        })
        .collect();

    let content = Paragraph::new(text_lines);
    frame.render_widget(content, chunks[0]);

    // Render status bar (2 lines)
    let page_display = format!(
        " {} | Page {}/{}",
        app.venv_name,
        app.current_page + 1,
        app.total_pages
    );
    let status_line = if let Some(ref msg) = app.status_message {
        format!(" Status: {} | {}", msg, page_display.trim())
    } else {
        format!(" Status:{}", page_display)
    };
    let keys_line = " Keys: ↑/↓ navigate | e edit | q quit";

    let status_text = vec![
        Line::from(Span::styled(
            status_line,
            Style::default()
                .fg(Color::White)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        )),
        Line::from(Span::styled(
            keys_line,
            Style::default().fg(Color::White).bg(Color::DarkGray),
        )),
    ];

    let status_bar = Paragraph::new(status_text).block(Block::default().borders(Borders::NONE));
    frame.render_widget(status_bar, chunks[1]);
}

/// Run the TUI application.
///
/// Enters alternate screen, renders content with paging, handles keyboard
/// navigation, and restores terminal on exit or panic.
///
/// Integrates the editor launcher (on `e` key) and the restart handler
/// (when restart-on-edit is enabled and the file was modified).
pub fn run_tui(
    config_files: &ConfigFiles,
    exports: &ShellExports,
    venv_name: &str,
    venv_path: &Path,
    options: &AppOptions,
) -> io::Result<()> {
    // Install a panic hook that restores terminal state
    let original_hook = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |panic_info| {
        let _ = disable_raw_mode();
        let _ = execute!(stdout(), LeaveAlternateScreen);
        original_hook(panic_info);
    }));

    let mut terminal = setup_terminal()?;
    let mut app = App::new(config_files, exports, venv_name);

    // Initial page size calculation
    let size = terminal.size()?;
    app.recalculate_pages(size.height);

    // Main event loop
    loop {
        terminal.draw(|frame| ui(frame, &app))?;

        if app.should_quit {
            break;
        }

        // Block until an event arrives
        match event::read()? {
            Event::Key(key) if key.kind == KeyEventKind::Press => match key.code {
                KeyCode::Char('q') => {
                    app.should_quit = true;
                }
                KeyCode::Char('e') => {
                    // Suspend TUI for editor
                    restore_terminal(&mut terminal)?;

                    // Launch editor
                    let editor_result = editor::launch_editor(&config_files.postactivate_path);

                    // Resume TUI
                    terminal = setup_terminal()?;
                    let size = terminal.size()?;
                    app.recalculate_pages(size.height);

                    match editor_result {
                        EditorResult::FileModified => {
                            // Refresh content from disk
                            let new_configs = crate::config_reader::read_configs(venv_path);
                            let new_exports = match &new_configs.postactivate {
                                Some(content) => crate::shell_analyzer::analyze_shell(content),
                                None => ShellExports {
                                    variables: vec![],
                                    aliases: vec![],
                                    functions: vec![],
                                },
                            };
                            app.content_lines = render_content(&new_configs, &new_exports);
                            app.recalculate_pages(size.height);

                            // Handle restart-on-edit
                            if options.restart_on_edit {
                                match restart::restart_virtualenv(venv_path) {
                                    RestartResult::Success(msg) => {
                                        app.status_message = Some(msg);
                                    }
                                    RestartResult::Failure(msg) => {
                                        app.status_message = Some(msg);
                                    }
                                }
                            } else {
                                app.status_message =
                                    Some("File modified, content refreshed".to_string());
                            }
                        }
                        EditorResult::FileUnchanged => {
                            app.status_message = Some("No changes detected".to_string());
                        }
                        EditorResult::Error(msg) => {
                            app.status_message = Some(msg);
                        }
                    }
                }
                KeyCode::Down => {
                    app.next_page();
                }
                KeyCode::Up => {
                    app.prev_page();
                }
                _ => {}
            },
            Event::Resize(_width, height) => {
                app.recalculate_pages(height);
            }
            _ => {}
        }
    }

    restore_terminal(&mut terminal)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config_reader::ConfigFiles;
    use crate::shell_analyzer::{ShellAlias, ShellExports, ShellFunction, ShellVariable};
    use std::path::PathBuf;

    fn make_config_files(pyvenv: Option<&str>, postactivate: Option<&str>) -> ConfigFiles {
        ConfigFiles {
            pyvenv_cfg: pyvenv.map(|s| s.to_string()),
            postactivate: postactivate.map(|s| s.to_string()),
            postactivate_path: PathBuf::from("/tmp/test/bin/postactivate"),
            postactivate_mtime: None,
        }
    }

    fn make_exports() -> ShellExports {
        ShellExports {
            variables: vec![ShellVariable {
                name: "FOO".to_string(),
                value: "bar".to_string(),
            }],
            aliases: vec![ShellAlias {
                name: "ll".to_string(),
                definition: "ls -la".to_string(),
            }],
            functions: vec![ShellFunction {
                name: "greet".to_string(),
                body: "echo hello".to_string(),
            }],
        }
    }

    #[test]
    fn test_render_content_with_all_sections() {
        let configs = make_config_files(
            Some("home = /usr/bin\nversion = 3.11"),
            Some("export FOO=bar\nalias ll='ls -la'"),
        );
        let exports = make_exports();

        let lines = render_content(&configs, &exports);

        assert!(lines.contains(&"═══ pyvenv.cfg ═══".to_string()));
        assert!(lines.contains(&"home = /usr/bin".to_string()));
        assert!(lines.contains(&"═══ postactivate (raw) ═══".to_string()));
        assert!(lines.contains(&"export FOO=bar".to_string()));
        assert!(lines.contains(&"═══ Shell Exports ═══".to_string()));
        assert!(lines.contains(&"── Variables ──".to_string()));
        assert!(lines.contains(&"  FOO = bar".to_string()));
        assert!(lines.contains(&"── Aliases ──".to_string()));
        assert!(lines.contains(&"  ll = ls -la".to_string()));
        assert!(lines.contains(&"── Functions ──".to_string()));
        assert!(lines.contains(&"  greet()".to_string()));
        assert!(lines.contains(&"    echo hello".to_string()));
    }

    #[test]
    fn test_render_content_no_files() {
        let configs = make_config_files(None, None);
        let exports = ShellExports {
            variables: vec![],
            aliases: vec![],
            functions: vec![],
        };

        let lines = render_content(&configs, &exports);

        assert_eq!(lines, vec!["No configuration files found.".to_string()]);
    }

    #[test]
    fn test_render_content_no_exports() {
        let configs = make_config_files(None, Some("# just a comment"));
        let exports = ShellExports {
            variables: vec![],
            aliases: vec![],
            functions: vec![],
        };

        let lines = render_content(&configs, &exports);

        assert!(lines.contains(&"═══ postactivate (raw) ═══".to_string()));
        assert!(lines.contains(&"  No shell exports detected.".to_string()));
    }

    #[test]
    fn test_app_paging_calculation() {
        let configs = make_config_files(Some("line1\nline2\nline3\nline4\nline5"), None);
        let exports = ShellExports {
            variables: vec![],
            aliases: vec![],
            functions: vec![],
        };

        let mut app = App::new(&configs, &exports, "testvenv");

        // Simulate a terminal with 5 rows: page_size = 5 - 2 = 3
        app.recalculate_pages(5);

        // Content: header + 5 lines + blank separator = 7 lines, page_size = 3 → 3 pages
        assert_eq!(app.page_size, 3);
        assert_eq!(app.total_pages, 3);
        assert_eq!(app.current_page, 0);
    }

    #[test]
    fn test_app_next_page_clamps_at_end() {
        let configs = make_config_files(Some("line1\nline2"), None);
        let exports = ShellExports {
            variables: vec![],
            aliases: vec![],
            functions: vec![],
        };

        let mut app = App::new(&configs, &exports, "testvenv");
        app.recalculate_pages(100); // Large terminal → 1 page

        assert_eq!(app.total_pages, 1);
        app.next_page();
        assert_eq!(app.current_page, 0); // Stays at 0
    }

    #[test]
    fn test_app_prev_page_clamps_at_start() {
        let configs = make_config_files(Some("line1"), None);
        let exports = ShellExports {
            variables: vec![],
            aliases: vec![],
            functions: vec![],
        };

        let mut app = App::new(&configs, &exports, "testvenv");
        app.recalculate_pages(10);

        app.prev_page();
        assert_eq!(app.current_page, 0); // Stays at 0
    }

    #[test]
    fn test_app_navigation_multi_page() {
        let configs = make_config_files(Some("l1\nl2\nl3\nl4\nl5\nl6\nl7\nl8\nl9\nl10"), None);
        let exports = ShellExports {
            variables: vec![],
            aliases: vec![],
            functions: vec![],
        };

        let mut app = App::new(&configs, &exports, "testvenv");
        // page_size = 5 - 2 = 3; content = header + 10 lines = 11 lines → 4 pages
        app.recalculate_pages(5);

        assert_eq!(app.page_size, 3);
        assert_eq!(app.current_page, 0);

        app.next_page();
        assert_eq!(app.current_page, 1);

        app.next_page();
        assert_eq!(app.current_page, 2);

        app.next_page();
        assert_eq!(app.current_page, 3);

        // Clamp at last page
        app.next_page();
        assert_eq!(app.current_page, 3);

        app.prev_page();
        assert_eq!(app.current_page, 2);
    }

    #[test]
    fn test_app_resize_recalculates() {
        let configs = make_config_files(Some("l1\nl2\nl3\nl4\nl5\nl6\nl7\nl8\nl9\nl10"), None);
        let exports = ShellExports {
            variables: vec![],
            aliases: vec![],
            functions: vec![],
        };

        let mut app = App::new(&configs, &exports, "testvenv");

        // Start with small terminal
        app.recalculate_pages(5); // page_size = 3
        assert_eq!(app.page_size, 3);
        let small_pages = app.total_pages;

        // Navigate to last page
        for _ in 0..small_pages {
            app.next_page();
        }

        // Resize to large terminal
        app.recalculate_pages(50); // page_size = 48
        assert_eq!(app.page_size, 48);
        assert_eq!(app.total_pages, 1);
        // current_page should be clamped to 0
        assert_eq!(app.current_page, 0);
    }

    #[test]
    fn test_page_size_minimum() {
        let configs = make_config_files(Some("line1"), None);
        let exports = ShellExports {
            variables: vec![],
            aliases: vec![],
            functions: vec![],
        };

        let mut app = App::new(&configs, &exports, "testvenv");

        // Very small terminal (height 2 or less)
        app.recalculate_pages(2);
        assert_eq!(app.page_size, 1); // Minimum page size is 1

        app.recalculate_pages(1);
        assert_eq!(app.page_size, 1);
    }

    #[test]
    fn test_current_page_lines() {
        let configs = make_config_files(Some("l1\nl2\nl3\nl4"), None);
        let exports = ShellExports {
            variables: vec![],
            aliases: vec![],
            functions: vec![],
        };

        let mut app = App::new(&configs, &exports, "testvenv");
        // Content: header + 4 lines + blank = 6 lines; page_size = 4 - 2 = 2
        app.recalculate_pages(4); // page_size = 2

        let first_page = app.current_page_lines();
        assert_eq!(first_page.len(), 2);

        app.next_page();
        let second_page = app.current_page_lines();
        assert_eq!(second_page.len(), 2);

        app.next_page();
        let third_page = app.current_page_lines();
        assert_eq!(third_page.len(), 2);
    }
}
