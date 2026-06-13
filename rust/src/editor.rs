use std::env;
use std::fs;
use std::path::Path;
use std::process::Command;
use std::time::SystemTime;

/// Result of launching the editor.
pub enum EditorResult {
    /// Editor exited and the file was modified.
    FileModified,
    /// Editor exited and the file was not modified.
    FileUnchanged,
    /// An error occurred (message for the status bar).
    Error(String),
}

/// Check the EDITOR environment variable.
///
/// Returns the editor command string or an error message.
fn get_editor() -> Result<String, String> {
    match env::var("EDITOR") {
        Ok(editor) if !editor.is_empty() => Ok(editor),
        _ => Err("No editor configured: $EDITOR is not set".to_string()),
    }
}

/// Get the modification time of a file, if it exists.
fn get_mtime(path: &Path) -> Option<SystemTime> {
    fs::metadata(path).ok().and_then(|m| m.modified().ok())
}

/// Launch the user's editor to edit the postactivate file.
///
/// This function:
/// 1. Checks that `$EDITOR` is set and non-empty
/// 2. Checks that the postactivate file exists
/// 3. Records the file modification timestamp
/// 4. Spawns the editor process (the caller is responsible for suspending/resuming TUI)
/// 5. Compares the modification timestamp after the editor exits
///
/// The caller must suspend the TUI (leave alternate screen, disable raw mode)
/// before calling this function, and resume it after.
pub fn launch_editor(postactivate_path: &Path) -> EditorResult {
    // Step 1: Check EDITOR environment variable
    let editor = match get_editor() {
        Ok(e) => e,
        Err(msg) => return EditorResult::Error(msg),
    };

    // Step 2: Check postactivate file exists
    if !postactivate_path.exists() {
        return EditorResult::Error(format!("File not found: {}", postactivate_path.display()));
    }

    // Step 3: Record file modification timestamp
    let mtime_before = get_mtime(postactivate_path);

    // Step 4: Spawn editor process
    let path_str = postactivate_path.to_string_lossy();

    // Split the editor command to handle cases like "code --wait" or "vim"
    let parts: Vec<&str> = editor.split_whitespace().collect();
    let (cmd, args) = match parts.split_first() {
        Some((cmd, args)) => (*cmd, args),
        None => return EditorResult::Error("$EDITOR is empty".to_string()),
    };

    let result = Command::new(cmd).args(args).arg(path_str.as_ref()).status();

    match result {
        Ok(status) => {
            if !status.success() {
                return EditorResult::Error(format!(
                    "Editor exited with status: {}",
                    status.code().unwrap_or(-1)
                ));
            }
        }
        Err(e) => {
            return EditorResult::Error(format!("Could not start editor '{}': {}", editor, e));
        }
    }

    // Step 5: Compare modification timestamp
    let mtime_after = get_mtime(postactivate_path);

    match (mtime_before, mtime_after) {
        (Some(before), Some(after)) if after != before => EditorResult::FileModified,
        (None, Some(_)) => EditorResult::FileModified, // File was created during edit
        _ => EditorResult::FileUnchanged,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serial_test::serial;
    use std::fs;
    use std::path::PathBuf;
    use tempfile::TempDir;

    #[test]
    #[serial]
    fn test_get_editor_when_set() {
        env::set_var("EDITOR", "vim");
        let result = get_editor();
        assert_eq!(result, Ok("vim".to_string()));
    }

    #[test]
    #[serial]
    fn test_get_editor_when_empty() {
        env::set_var("EDITOR", "");
        let result = get_editor();
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("not set"));
    }

    #[test]
    #[serial]
    fn test_get_editor_when_unset() {
        env::remove_var("EDITOR");
        let result = get_editor();
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("not set"));
    }

    #[test]
    fn test_get_mtime_existing_file() {
        let tmp = TempDir::new().unwrap();
        let file_path = tmp.path().join("testfile");
        fs::write(&file_path, "content").unwrap();

        let mtime = get_mtime(&file_path);
        assert!(mtime.is_some());
    }

    #[test]
    fn test_get_mtime_nonexistent_file() {
        let path = PathBuf::from("/nonexistent/file/path");
        let mtime = get_mtime(&path);
        assert!(mtime.is_none());
    }

    #[test]
    #[serial]
    fn test_launch_editor_no_editor_set() {
        env::remove_var("EDITOR");
        let path = PathBuf::from("/tmp/some/postactivate");

        let result = launch_editor(&path);
        match result {
            EditorResult::Error(msg) => {
                assert!(msg.contains("not set"));
            }
            _ => panic!("Expected Error result"),
        }
    }

    #[test]
    #[serial]
    fn test_launch_editor_file_not_found() {
        env::set_var("EDITOR", "vim");
        let path = PathBuf::from("/nonexistent/path/postactivate");

        let result = launch_editor(&path);
        match result {
            EditorResult::Error(msg) => {
                assert!(msg.contains("File not found"));
            }
            _ => panic!("Expected Error result"),
        }
    }

    #[test]
    #[serial]
    fn test_launch_editor_command_not_found() {
        env::set_var("EDITOR", "nonexistent_editor_binary_xyz");
        let tmp = TempDir::new().unwrap();
        let file_path = tmp.path().join("postactivate");
        fs::write(&file_path, "export FOO=bar\n").unwrap();

        let result = launch_editor(&file_path);
        match result {
            EditorResult::Error(msg) => {
                assert!(msg.contains("Could not start editor"));
            }
            _ => panic!("Expected Error result"),
        }
    }

    #[test]
    #[serial]
    fn test_launch_editor_file_unchanged() {
        // Use 'true' as the editor (it does nothing and exits 0)
        env::set_var("EDITOR", "true");
        let tmp = TempDir::new().unwrap();
        let file_path = tmp.path().join("postactivate");
        fs::write(&file_path, "export FOO=bar\n").unwrap();

        let result = launch_editor(&file_path);
        match result {
            EditorResult::FileUnchanged => {} // Expected
            EditorResult::Error(msg) => panic!("Unexpected error: {}", msg),
            EditorResult::FileModified => panic!("File should not have been modified"),
        }
    }

    #[test]
    #[serial]
    fn test_launch_editor_file_modified() {
        // Use a script that modifies the file
        // We'll use 'bash -c' via the EDITOR env var to append to the file
        let tmp = TempDir::new().unwrap();
        let file_path = tmp.path().join("postactivate");
        fs::write(&file_path, "export FOO=bar\n").unwrap();

        // Create a small script that modifies the target file
        let script_path = tmp.path().join("modify_editor.sh");
        fs::write(&script_path, "#!/bin/sh\necho 'export BAZ=qux' >> \"$1\"\n").unwrap();

        // Make script executable
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let perms = fs::Permissions::from_mode(0o755);
            fs::set_permissions(&script_path, perms).unwrap();
        }

        env::set_var("EDITOR", script_path.to_string_lossy().to_string());

        let result = launch_editor(&file_path);
        match result {
            EditorResult::FileModified => {} // Expected
            EditorResult::FileUnchanged => panic!("File should have been modified"),
            EditorResult::Error(msg) => panic!("Unexpected error: {}", msg),
        }
    }

    #[test]
    #[serial]
    fn test_launch_editor_with_args_in_editor_var() {
        // Test that EDITOR="cmd --flag" is handled properly
        // Use 'true' which ignores args
        env::set_var("EDITOR", "true --some-flag");
        let tmp = TempDir::new().unwrap();
        let file_path = tmp.path().join("postactivate");
        fs::write(&file_path, "export FOO=bar\n").unwrap();

        let result = launch_editor(&file_path);
        match result {
            EditorResult::FileUnchanged => {} // Expected - 'true' doesn't modify
            EditorResult::Error(msg) => {
                // 'true' might not accept --some-flag on all platforms,
                // but it typically exits 0 anyway
                panic!("Unexpected error: {}", msg);
            }
            EditorResult::FileModified => panic!("File should not have been modified"),
        }
    }
}
