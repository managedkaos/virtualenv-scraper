use std::fs;
use std::path::PathBuf;

use tempfile::TempDir;
use virtualenv_viewer::config_reader::read_configs;

// ─────────────────────────────────────────────────────────────────────────────
// Integration Tests: Config Reader
// Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
// ─────────────────────────────────────────────────────────────────────────────

/// Requirement 2.1: Reads pyvenv.cfg from the virtualenv root directory.
#[test]
fn test_reads_pyvenv_cfg_from_venv_root() {
    let tmp = TempDir::new().unwrap();
    let venv = tmp.path().join("myvenv");
    fs::create_dir_all(&venv).unwrap();

    let cfg_content =
        "home = /usr/local/bin\nversion = 3.11.5\ninclude-system-site-packages = false\n";
    fs::write(venv.join("pyvenv.cfg"), cfg_content).unwrap();

    let configs = read_configs(&venv);

    assert_eq!(configs.pyvenv_cfg, Some(cfg_content.to_string()));
}

/// Requirement 2.2: Reads postactivate from the virtualenv's bin/ directory.
#[test]
fn test_reads_postactivate_from_bin_directory() {
    let tmp = TempDir::new().unwrap();
    let venv = tmp.path().join("myvenv");
    fs::create_dir_all(venv.join("bin")).unwrap();

    let postactivate_content = "#!/bin/bash\nexport PROJECT_HOME=/workspace\nexport DEBUG=1\n";
    fs::write(venv.join("bin/postactivate"), postactivate_content).unwrap();

    let configs = read_configs(&venv);

    assert_eq!(configs.postactivate, Some(postactivate_content.to_string()));
    assert_eq!(configs.postactivate_path, venv.join("bin/postactivate"));
}

/// Requirement 2.3: Missing files are skipped without error.
#[test]
fn test_missing_pyvenv_cfg_returns_none() {
    let tmp = TempDir::new().unwrap();
    let venv = tmp.path().join("myvenv");
    fs::create_dir_all(venv.join("bin")).unwrap();
    // No pyvenv.cfg created

    let configs = read_configs(&venv);

    assert_eq!(configs.pyvenv_cfg, None);
}

#[test]
fn test_missing_postactivate_returns_none() {
    let tmp = TempDir::new().unwrap();
    let venv = tmp.path().join("myvenv");
    fs::create_dir_all(venv.join("bin")).unwrap();
    fs::write(venv.join("pyvenv.cfg"), "home = /usr/bin\n").unwrap();
    // No postactivate created

    let configs = read_configs(&venv);

    assert_eq!(configs.postactivate, None);
    assert_eq!(configs.postactivate_mtime, None);
}

/// Requirement 2.4: Permission/IO errors are skipped without error.
#[cfg(unix)]
#[test]
fn test_unreadable_pyvenv_cfg_returns_none() {
    use std::os::unix::fs::PermissionsExt;

    let tmp = TempDir::new().unwrap();
    let venv = tmp.path().join("myvenv");
    fs::create_dir_all(&venv).unwrap();

    let cfg_path = venv.join("pyvenv.cfg");
    fs::write(&cfg_path, "home = /usr/bin\n").unwrap();
    fs::set_permissions(&cfg_path, fs::Permissions::from_mode(0o000)).unwrap();

    let configs = read_configs(&venv);

    // Should gracefully return None instead of panicking
    assert_eq!(configs.pyvenv_cfg, None);

    // Restore permissions for cleanup
    fs::set_permissions(&cfg_path, fs::Permissions::from_mode(0o644)).unwrap();
}

#[cfg(unix)]
#[test]
fn test_unreadable_postactivate_returns_none() {
    use std::os::unix::fs::PermissionsExt;

    let tmp = TempDir::new().unwrap();
    let venv = tmp.path().join("myvenv");
    fs::create_dir_all(venv.join("bin")).unwrap();

    let pa_path = venv.join("bin/postactivate");
    fs::write(&pa_path, "export FOO=bar\n").unwrap();
    fs::set_permissions(&pa_path, fs::Permissions::from_mode(0o000)).unwrap();

    let configs = read_configs(&venv);

    // Should gracefully return None instead of panicking
    assert_eq!(configs.postactivate, None);
    assert_eq!(configs.postactivate_mtime, None);

    // Restore permissions for cleanup
    fs::set_permissions(&pa_path, fs::Permissions::from_mode(0o644)).unwrap();
}

/// Requirement 2.5: Both files can be read and their contents preserved.
/// Verifies that pyvenv_cfg and postactivate contents are both available
/// when both files exist (display ordering is handled by the TUI layer).
#[test]
fn test_both_files_present_preserves_contents() {
    let tmp = TempDir::new().unwrap();
    let venv = tmp.path().join("myvenv");
    fs::create_dir_all(venv.join("bin")).unwrap();

    let cfg_content = "home = /usr/bin\nversion = 3.12.0\n";
    let pa_content = "#!/bin/bash\nexport MYVAR=hello\nalias ll='ls -la'\n";

    fs::write(venv.join("pyvenv.cfg"), cfg_content).unwrap();
    fs::write(venv.join("bin/postactivate"), pa_content).unwrap();

    let configs = read_configs(&venv);

    assert_eq!(configs.pyvenv_cfg, Some(cfg_content.to_string()));
    assert_eq!(configs.postactivate, Some(pa_content.to_string()));
    assert!(configs.postactivate_mtime.is_some());
}

/// Requirement 2.6: When no config files are readable, both fields are None.
/// The caller should display an informative "no config files found" message.
#[test]
fn test_no_config_files_found_returns_all_none() {
    let tmp = TempDir::new().unwrap();
    let venv = tmp.path().join("empty_venv");
    fs::create_dir_all(&venv).unwrap();

    let configs = read_configs(&venv);

    assert_eq!(configs.pyvenv_cfg, None);
    assert_eq!(configs.postactivate, None);
    // The caller can check both are None to show "no config files found"
    assert!(configs.pyvenv_cfg.is_none() && configs.postactivate.is_none());
}

/// Requirement 2.6: Nonexistent virtualenv path still returns gracefully.
#[test]
fn test_nonexistent_venv_path_returns_all_none() {
    let path = PathBuf::from("/nonexistent/venv/path");

    let configs = read_configs(&path);

    assert_eq!(configs.pyvenv_cfg, None);
    assert_eq!(configs.postactivate, None);
    assert_eq!(configs.postactivate_path, path.join("bin/postactivate"));
    assert_eq!(configs.postactivate_mtime, None);
}

/// Verify that postactivate_path is always set correctly regardless of file existence.
#[test]
fn test_postactivate_path_always_set() {
    let tmp = TempDir::new().unwrap();
    let venv = tmp.path().join("myvenv");
    fs::create_dir_all(&venv).unwrap();

    let configs = read_configs(&venv);

    assert_eq!(configs.postactivate_path, venv.join("bin/postactivate"));
}

/// Verify mtime is populated when postactivate exists.
#[test]
fn test_postactivate_mtime_set_when_file_exists() {
    let tmp = TempDir::new().unwrap();
    let venv = tmp.path().join("myvenv");
    fs::create_dir_all(venv.join("bin")).unwrap();
    fs::write(venv.join("bin/postactivate"), "export X=1\n").unwrap();

    let configs = read_configs(&venv);

    assert!(configs.postactivate.is_some());
    assert!(configs.postactivate_mtime.is_some());
}

/// Verify that multiline config files are read correctly (content fidelity).
#[test]
fn test_multiline_pyvenv_cfg_preserved() {
    let tmp = TempDir::new().unwrap();
    let venv = tmp.path().join("myvenv");
    fs::create_dir_all(&venv).unwrap();

    let cfg_content = "\
home = /usr/local/opt/python@3.11/bin
include-system-site-packages = false
version = 3.11.5
executable = /usr/local/opt/python@3.11/bin/python3.11
command = /usr/local/opt/python@3.11/bin/python3.11 -m venv /path/to/venv
";
    fs::write(venv.join("pyvenv.cfg"), cfg_content).unwrap();

    let configs = read_configs(&venv);

    assert_eq!(configs.pyvenv_cfg, Some(cfg_content.to_string()));
}
