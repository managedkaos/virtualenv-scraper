use std::path::Path;
use std::process::Command;

/// Result of a virtualenv restart attempt.
#[derive(Debug, PartialEq)]
pub enum RestartResult {
    /// The virtualenv was successfully restarted.
    Success(String),
    /// The restart failed during deactivation or reactivation.
    Failure(String),
}

/// Attempts to restart the virtualenv by deactivating and reactivating it.
///
/// Executes `deactivate && source {venv_path}/bin/activate` in a subshell.
///
/// Note: Since the viewer runs in a child process, this cannot directly modify
/// the parent shell's environment. The restart emits the deactivate/activate
/// commands and reports success or failure.
///
/// # Arguments
///
/// * `venv_path` - Path to the virtualenv directory
///
/// # Returns
///
/// `RestartResult::Success` with a confirmation message if the restart command
/// executed successfully, or `RestartResult::Failure` with an error message if
/// deactivation or reactivation failed.
pub fn restart_virtualenv(venv_path: &Path) -> RestartResult {
    let activate_path = venv_path.join("bin").join("activate");

    if !activate_path.exists() {
        return RestartResult::Failure(format!(
            "Error: activate script not found\n  Path: {}",
            activate_path.display()
        ));
    }

    let command = format!(
        "deactivate 2>/dev/null; source '{}'",
        activate_path.display()
    );

    let result = Command::new("bash").arg("-c").arg(&command).output();

    match result {
        Ok(output) => {
            if output.status.success() {
                let venv_name = venv_path
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or("unknown");
                RestartResult::Success(format!("Virtualenv '{}' restarted successfully", venv_name))
            } else {
                let stderr = String::from_utf8_lossy(&output.stderr);
                RestartResult::Failure(format!(
                    "Error: virtualenv restart failed\n  {}",
                    stderr.trim()
                ))
            }
        }
        Err(e) => {
            RestartResult::Failure(format!("Error: failed to execute restart command\n  {}", e))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::TempDir;

    /// Helper to create a virtualenv directory with an activate script.
    fn create_venv_with_activate(tmp: &TempDir) -> std::path::PathBuf {
        let venv_path = tmp.path().join("testvenv");
        let bin_dir = venv_path.join("bin");
        fs::create_dir_all(&bin_dir).unwrap();
        // Create a minimal activate script that just exits successfully
        fs::write(
            bin_dir.join("activate"),
            "# minimal activate script\nexport VIRTUAL_ENV=\"${BASH_SOURCE%/*}/..\"\n",
        )
        .unwrap();
        venv_path
    }

    #[test]
    fn test_restart_success_with_valid_venv() {
        let tmp = TempDir::new().unwrap();
        let venv_path = create_venv_with_activate(&tmp);

        let result = restart_virtualenv(&venv_path);
        match result {
            RestartResult::Success(msg) => {
                assert!(msg.contains("testvenv"));
                assert!(msg.contains("restarted successfully"));
            }
            RestartResult::Failure(msg) => {
                panic!("Expected success but got failure: {}", msg);
            }
        }
    }

    #[test]
    fn test_restart_failure_missing_activate_script() {
        let tmp = TempDir::new().unwrap();
        let venv_path = tmp.path().join("novenv");
        fs::create_dir_all(&venv_path).unwrap();
        // No bin/activate file

        let result = restart_virtualenv(&venv_path);
        match result {
            RestartResult::Failure(msg) => {
                assert!(msg.contains("activate script not found"));
            }
            RestartResult::Success(_) => {
                panic!("Expected failure for missing activate script");
            }
        }
    }

    #[test]
    fn test_restart_failure_nonexistent_path() {
        let path = Path::new("/nonexistent/path/to/venv");

        let result = restart_virtualenv(path);
        match result {
            RestartResult::Failure(msg) => {
                assert!(msg.contains("activate script not found"));
            }
            RestartResult::Success(_) => {
                panic!("Expected failure for nonexistent path");
            }
        }
    }

    #[test]
    fn test_restart_result_success_contains_venv_name() {
        let tmp = TempDir::new().unwrap();
        let venv_path = create_venv_with_activate(&tmp);

        let result = restart_virtualenv(&venv_path);
        if let RestartResult::Success(msg) = result {
            assert!(msg.contains("testvenv"));
        }
    }

    #[test]
    fn test_restart_failure_invalid_activate_script() {
        let tmp = TempDir::new().unwrap();
        let venv_path = tmp.path().join("badvenv");
        let bin_dir = venv_path.join("bin");
        fs::create_dir_all(&bin_dir).unwrap();
        // Create an activate script that will fail
        fs::write(bin_dir.join("activate"), "exit 1\n").unwrap();

        let result = restart_virtualenv(&venv_path);
        match result {
            RestartResult::Failure(msg) => {
                assert!(msg.contains("restart failed"));
            }
            RestartResult::Success(_) => {
                panic!("Expected failure for invalid activate script");
            }
        }
    }
}
