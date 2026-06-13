use std::env;
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;

use proptest::prelude::*;
use tempfile::TempDir;
use virtualenv_viewer::detector::{detect_virtualenv, is_valid_virtualenv, DetectionError};

// Global mutex to serialize tests that manipulate env vars and cwd.
// We use `lock().unwrap_or_else(|e| e.into_inner())` to recover from poisoned state.
static ENV_MUTEX: Mutex<()> = Mutex::new(());

fn lock_env() -> std::sync::MutexGuard<'static, ()> {
    ENV_MUTEX.lock().unwrap_or_else(|e| e.into_inner())
}

/// Helper to create a valid virtualenv directory (with pyvenv.cfg).
fn create_valid_venv(path: &std::path::Path) {
    fs::create_dir_all(path).unwrap();
    fs::write(path.join("pyvenv.cfg"), "home = /usr/bin\n").unwrap();
}

/// Canonicalize a path (resolves symlinks like /var -> /private/var on macOS).
fn canon(path: &std::path::Path) -> PathBuf {
    path.canonicalize().unwrap_or_else(|_| path.to_path_buf())
}

// ─────────────────────────────────────────────────────────────────────────────
// Unit Tests: Detection Priority Chain
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn test_virtual_env_var_takes_highest_priority() {
    let _lock = lock_env();

    let tmp = TempDir::new().unwrap();
    let venv_path = tmp.path().join("my_venv");
    create_valid_venv(&venv_path);

    // Also create .venv in current dir to ensure VIRTUAL_ENV wins
    let cwd = tmp.path().join("project");
    fs::create_dir_all(&cwd).unwrap();
    create_valid_venv(&cwd.join(".venv"));

    env::set_var("VIRTUAL_ENV", venv_path.to_str().unwrap());
    env::set_current_dir(&cwd).unwrap();

    let result = detect_virtualenv();
    assert_eq!(result.unwrap(), venv_path);

    env::remove_var("VIRTUAL_ENV");
}

#[test]
fn test_dot_env_has_second_priority() {
    let _lock = lock_env();

    let tmp = TempDir::new().unwrap();
    let cwd = tmp.path().join("project");
    fs::create_dir_all(&cwd).unwrap();

    // Create .env, .venv, venv, env — all valid
    create_valid_venv(&cwd.join(".env"));
    create_valid_venv(&cwd.join(".venv"));
    create_valid_venv(&cwd.join("venv"));
    create_valid_venv(&cwd.join("env"));

    env::remove_var("VIRTUAL_ENV");
    env::set_current_dir(&cwd).unwrap();

    let result = detect_virtualenv();
    // Use canonicalize because macOS resolves /var -> /private/var in current_dir()
    let expected = canon(&cwd.join(".env"));
    assert_eq!(canon(&result.unwrap()), expected);
}

#[test]
fn test_dot_venv_has_third_priority() {
    let _lock = lock_env();

    let tmp = TempDir::new().unwrap();
    let cwd = tmp.path().join("project");
    fs::create_dir_all(&cwd).unwrap();

    // Create .venv, venv, env — all valid (no .env)
    create_valid_venv(&cwd.join(".venv"));
    create_valid_venv(&cwd.join("venv"));
    create_valid_venv(&cwd.join("env"));

    env::remove_var("VIRTUAL_ENV");
    env::set_current_dir(&cwd).unwrap();

    let result = detect_virtualenv();
    let expected = canon(&cwd.join(".venv"));
    assert_eq!(canon(&result.unwrap()), expected);
}

#[test]
fn test_venv_has_fourth_priority() {
    let _lock = lock_env();

    let tmp = TempDir::new().unwrap();
    let cwd = tmp.path().join("project");
    fs::create_dir_all(&cwd).unwrap();

    // Create venv and env — both valid (no .env or .venv)
    create_valid_venv(&cwd.join("venv"));
    create_valid_venv(&cwd.join("env"));

    env::remove_var("VIRTUAL_ENV");
    env::set_current_dir(&cwd).unwrap();

    let result = detect_virtualenv();
    let expected = canon(&cwd.join("venv"));
    assert_eq!(canon(&result.unwrap()), expected);
}

#[test]
fn test_env_has_lowest_priority() {
    let _lock = lock_env();

    let tmp = TempDir::new().unwrap();
    let cwd = tmp.path().join("project");
    fs::create_dir_all(&cwd).unwrap();

    // Create only env — valid
    create_valid_venv(&cwd.join("env"));

    env::remove_var("VIRTUAL_ENV");
    env::set_current_dir(&cwd).unwrap();

    let result = detect_virtualenv();
    let expected = canon(&cwd.join("env"));
    assert_eq!(canon(&result.unwrap()), expected);
}

// ─────────────────────────────────────────────────────────────────────────────
// Unit Tests: Error Cases
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn test_virtual_env_set_but_invalid_returns_error() {
    let _lock = lock_env();

    let tmp = TempDir::new().unwrap();
    // Directory exists but no pyvenv.cfg
    let invalid_path = tmp.path().join("not_a_venv");
    fs::create_dir_all(&invalid_path).unwrap();

    env::set_var("VIRTUAL_ENV", invalid_path.to_str().unwrap());

    let result = detect_virtualenv();
    match result {
        Err(DetectionError::InvalidVirtualEnv(path)) => {
            assert_eq!(path, invalid_path.to_str().unwrap());
        }
        other => panic!("Expected InvalidVirtualEnv error, got {:?}", other),
    }

    env::remove_var("VIRTUAL_ENV");
}

#[test]
fn test_virtual_env_set_to_nonexistent_path_returns_error() {
    let _lock = lock_env();

    env::set_var("VIRTUAL_ENV", "/nonexistent/path/to/nowhere");

    let result = detect_virtualenv();
    match result {
        Err(DetectionError::InvalidVirtualEnv(path)) => {
            assert_eq!(path, "/nonexistent/path/to/nowhere");
        }
        other => panic!("Expected InvalidVirtualEnv error, got {:?}", other),
    }

    env::remove_var("VIRTUAL_ENV");
}

#[test]
fn test_no_virtualenv_found_returns_not_found_error() {
    let _lock = lock_env();

    let tmp = TempDir::new().unwrap();
    let cwd = tmp.path().join("empty_project");
    fs::create_dir_all(&cwd).unwrap();

    env::remove_var("VIRTUAL_ENV");
    env::set_current_dir(&cwd).unwrap();

    let result = detect_virtualenv();
    match result {
        Err(DetectionError::NotFound(paths)) => {
            assert_eq!(paths.len(), 4);
            assert!(paths[0].contains(".env"));
            assert!(paths[1].contains(".venv"));
            assert!(paths[2].ends_with("venv"));
            assert!(paths[3].ends_with("env"));
        }
        other => panic!("Expected NotFound error, got {:?}", other),
    }
}

#[test]
fn test_empty_virtual_env_var_is_ignored() {
    let _lock = lock_env();

    let tmp = TempDir::new().unwrap();
    let cwd = tmp.path().join("project");
    fs::create_dir_all(&cwd).unwrap();
    create_valid_venv(&cwd.join(".venv"));

    env::set_var("VIRTUAL_ENV", "");
    env::set_current_dir(&cwd).unwrap();

    let result = detect_virtualenv();
    let expected = canon(&cwd.join(".venv"));
    assert_eq!(canon(&result.unwrap()), expected);

    env::remove_var("VIRTUAL_ENV");
}

// ─────────────────────────────────────────────────────────────────────────────
// Unit Tests: Virtualenv Validation
// ─────────────────────────────────────────────────────────────────────────────

#[test]
fn test_is_valid_virtualenv_with_pyvenv_cfg() {
    let tmp = TempDir::new().unwrap();
    let venv = tmp.path().join("valid_venv");
    create_valid_venv(&venv);
    assert!(is_valid_virtualenv(&venv));
}

#[test]
fn test_is_valid_virtualenv_without_pyvenv_cfg() {
    let tmp = TempDir::new().unwrap();
    let venv = tmp.path().join("invalid_venv");
    fs::create_dir_all(&venv).unwrap();
    assert!(!is_valid_virtualenv(&venv));
}

#[test]
fn test_is_valid_virtualenv_nonexistent_directory() {
    let path = PathBuf::from("/definitely/does/not/exist");
    assert!(!is_valid_virtualenv(&path));
}

#[test]
fn test_detection_stops_at_first_valid_match() {
    let _lock = lock_env();

    let tmp = TempDir::new().unwrap();
    let cwd = tmp.path().join("project");
    fs::create_dir_all(&cwd).unwrap();

    // Only .venv is valid, .env exists but is not valid (no pyvenv.cfg)
    fs::create_dir_all(cwd.join(".env")).unwrap();
    create_valid_venv(&cwd.join(".venv"));

    env::remove_var("VIRTUAL_ENV");
    env::set_current_dir(&cwd).unwrap();

    let result = detect_virtualenv();
    let expected = canon(&cwd.join(".venv"));
    assert_eq!(canon(&result.unwrap()), expected);
}

// ─────────────────────────────────────────────────────────────────────────────
// Property-Based Tests
// ─────────────────────────────────────────────────────────────────────────────

/// Generate a subset of candidate directories as a bitmask.
/// Bits: 0 = .env, 1 = .venv, 2 = venv, 3 = env
fn candidate_subset() -> impl Strategy<Value = u8> {
    // At least one candidate must be valid (1..=15 covers all non-empty subsets)
    1u8..=15u8
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(100))]

    /// **Feature: virtualenv-config-viewer, Property 1: Detection Priority Ordering**
    ///
    /// For any set of candidate directories that contain a valid pyvenv.cfg file,
    /// detect_virtualenv() SHALL return the directory with the highest priority
    /// according to the defined order, regardless of which other valid directories exist.
    ///
    /// **Validates: Requirements 1.3, 1.5**
    #[test]
    fn prop_detection_priority_ordering(subset in candidate_subset()) {
        let _lock = lock_env();

        let tmp = TempDir::new().unwrap();
        let cwd = tmp.path().join("project");
        fs::create_dir_all(&cwd).unwrap();

        let candidates = [".env", ".venv", "venv", "env"];

        // Create valid virtualenvs for each bit that is set
        for (i, name) in candidates.iter().enumerate() {
            if subset & (1 << i) != 0 {
                create_valid_venv(&cwd.join(name));
            }
        }

        env::remove_var("VIRTUAL_ENV");
        env::set_current_dir(&cwd).unwrap();

        let result = detect_virtualenv();

        // The expected winner is the lowest index bit that is set
        let expected_idx = (0..4).find(|&i| subset & (1 << i) != 0).unwrap();
        let expected_path = canon(&cwd.join(candidates[expected_idx]));

        prop_assert_eq!(canon(&result.unwrap()), expected_path);
    }

    /// **Feature: virtualenv-config-viewer, Property 2: Virtualenv Validation**
    ///
    /// For any directory path, is_valid_virtualenv(path) SHALL return true if and only if
    /// the file {path}/pyvenv.cfg exists. Directories without pyvenv.cfg must always
    /// return false; directories with pyvenv.cfg must always return true.
    ///
    /// **Validates: Requirements 1.6**
    #[test]
    fn prop_virtualenv_validation_with_cfg(
        dir_name in "[a-z][a-z0-9_]{0,10}"
    ) {
        let tmp = TempDir::new().unwrap();
        let dir_path = tmp.path().join(&dir_name);
        fs::create_dir_all(&dir_path).unwrap();

        // Without pyvenv.cfg → must be false
        prop_assert!(!is_valid_virtualenv(&dir_path));

        // With pyvenv.cfg → must be true
        fs::write(dir_path.join("pyvenv.cfg"), "home = /usr/bin\n").unwrap();
        prop_assert!(is_valid_virtualenv(&dir_path));
    }

    /// **Feature: virtualenv-config-viewer, Property 2: Virtualenv Validation (nonexistent)**
    ///
    /// For any nonexistent path, is_valid_virtualenv(path) SHALL return false.
    ///
    /// **Validates: Requirements 1.6**
    #[test]
    fn prop_virtualenv_validation_nonexistent(
        dir_name in "[a-z][a-z0-9_]{0,10}"
    ) {
        let tmp = TempDir::new().unwrap();
        // Don't create the directory — it shouldn't exist
        let dir_path = tmp.path().join("nonexistent").join(&dir_name);
        prop_assert!(!is_valid_virtualenv(&dir_path));
    }
}
