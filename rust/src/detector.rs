use std::env;
use std::fmt;
use std::fs;
use std::path::{Path, PathBuf};

/// Errors that can occur during virtualenv detection.
#[derive(Debug, PartialEq)]
pub enum DetectionError {
    /// The VIRTUAL_ENV environment variable is set but does not point to a valid virtualenv.
    InvalidVirtualEnv(String),
    /// No valid virtualenv was found after exhausting all detection strategies.
    NotFound(Vec<String>),
}

impl fmt::Display for DetectionError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            DetectionError::InvalidVirtualEnv(path) => {
                write!(
                    f,
                    "Error: VIRTUAL_ENV is set but is not a valid virtualenv\n  Path: {}",
                    path
                )
            }
            DetectionError::NotFound(paths) => {
                write!(
                    f,
                    "Error: No valid virtualenv found\n  Attempted paths:\n{}",
                    paths
                        .iter()
                        .map(|p| format!("    - {}", p))
                        .collect::<Vec<_>>()
                        .join("\n")
                )
            }
        }
    }
}

/// Checks whether a directory is a valid virtualenv by looking for a `pyvenv.cfg` file.
pub fn is_valid_virtualenv(path: &Path) -> bool {
    let pyvenv_cfg = path.join("pyvenv.cfg");
    fs::metadata(&pyvenv_cfg).is_ok()
}

/// Detects the active virtualenv using the following priority order:
///
/// 1. `$VIRTUAL_ENV` environment variable (must contain `pyvenv.cfg`)
/// 2. `$PWD/.env` directory
/// 3. `$PWD/.venv` directory
/// 4. `$PWD/venv` directory
/// 5. `$PWD/env` directory
///
/// Returns the path to the detected virtualenv, or an error describing what went wrong.
pub fn detect_virtualenv() -> Result<PathBuf, DetectionError> {
    // Check VIRTUAL_ENV environment variable first
    if let Ok(virtual_env) = env::var("VIRTUAL_ENV") {
        if !virtual_env.is_empty() {
            let path = PathBuf::from(&virtual_env);
            if is_valid_virtualenv(&path) {
                return Ok(path);
            } else {
                return Err(DetectionError::InvalidVirtualEnv(virtual_env));
            }
        }
    }

    // Get the current working directory
    let cwd = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));

    // Candidate directories relative to $PWD in priority order
    let candidates = [".env", ".venv", "venv", "env"];

    let mut attempted_paths: Vec<String> = Vec::new();

    // If VIRTUAL_ENV was not set/empty, we don't add it to attempted paths
    // (only add it if it was set but invalid, which is handled above as a specific error)

    for candidate in &candidates {
        let path = cwd.join(candidate);
        attempted_paths.push(path.display().to_string());
        if is_valid_virtualenv(&path) {
            return Ok(path);
        }
    }

    Err(DetectionError::NotFound(attempted_paths))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::TempDir;

    /// Helper to create a valid virtualenv directory (with pyvenv.cfg).
    fn create_valid_venv(path: &std::path::Path) {
        fs::create_dir_all(path).unwrap();
        fs::write(path.join("pyvenv.cfg"), "home = /usr/bin\n").unwrap();
    }

    #[test]
    fn test_is_valid_virtualenv_with_pyvenv_cfg() {
        let tmp = TempDir::new().unwrap();
        let venv_path = tmp.path().join("myvenv");
        create_valid_venv(&venv_path);
        assert!(is_valid_virtualenv(&venv_path));
    }

    #[test]
    fn test_is_valid_virtualenv_without_pyvenv_cfg() {
        let tmp = TempDir::new().unwrap();
        let venv_path = tmp.path().join("myvenv");
        fs::create_dir_all(&venv_path).unwrap();
        assert!(!is_valid_virtualenv(&venv_path));
    }

    #[test]
    fn test_is_valid_virtualenv_nonexistent_dir() {
        let path = PathBuf::from("/nonexistent/path/to/venv");
        assert!(!is_valid_virtualenv(&path));
    }

    #[test]
    fn test_detection_error_display_invalid_virtual_env() {
        let err = DetectionError::InvalidVirtualEnv("/some/path".to_string());
        let msg = format!("{}", err);
        assert!(msg.contains("VIRTUAL_ENV is set but is not a valid virtualenv"));
        assert!(msg.contains("/some/path"));
    }

    #[test]
    fn test_detection_error_display_not_found() {
        let err = DetectionError::NotFound(vec![
            "/home/user/.env".to_string(),
            "/home/user/.venv".to_string(),
        ]);
        let msg = format!("{}", err);
        assert!(msg.contains("No valid virtualenv found"));
        assert!(msg.contains("/home/user/.env"));
        assert!(msg.contains("/home/user/.venv"));
    }
}
