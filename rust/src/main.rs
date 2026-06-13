mod config_reader;
mod detector;
mod editor;
mod options;
mod restart;
mod shell_analyzer;
mod tui;

use std::process;

fn main() {
    // Step 1: Resolve application options (CLI > env > config > default)
    let app_options = options::resolve_options();

    // Step 2: Detect the active virtualenv (exit on error)
    let venv_path = match detector::detect_virtualenv() {
        Ok(path) => path,
        Err(e) => {
            eprintln!("{}", e);
            process::exit(1);
        }
    };

    // Extract the virtualenv name from the path for display
    let venv_name = venv_path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("unknown")
        .to_string();

    // Step 3: Read configuration files from the virtualenv
    let config_files = config_reader::read_configs(&venv_path);

    // Step 4: Analyze shell exports from postactivate (if present)
    let exports = match &config_files.postactivate {
        Some(content) => shell_analyzer::analyze_shell(content),
        None => shell_analyzer::ShellExports {
            variables: vec![],
            aliases: vec![],
            functions: vec![],
        },
    };

    // Step 5: Run the TUI with editor and restart handler integration
    if let Err(e) = tui::run_tui(
        &config_files,
        &exports,
        &venv_name,
        &venv_path,
        &app_options,
    ) {
        eprintln!("Error: TUI failed\n  {}", e);
        process::exit(1);
    }
}
