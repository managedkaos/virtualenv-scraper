use std::fs;
use std::path::{Path, PathBuf};
use std::time::SystemTime;

/// Holds the raw contents of virtualenv configuration files.
pub struct ConfigFiles {
    /// Raw text of pyvenv.cfg, or None if the file is missing or unreadable.
    pub pyvenv_cfg: Option<String>,
    /// Raw text of bin/postactivate, or None if the file is missing or unreadable.
    pub postactivate: Option<String>,
    /// Expected path to the postactivate file (used by the editor launcher).
    pub postactivate_path: PathBuf,
    /// Modification time of the postactivate file, if it was successfully read.
    #[allow(dead_code)]
    pub postactivate_mtime: Option<SystemTime>,
}

/// Reads virtualenv configuration files from the given virtualenv path.
///
/// Missing or unreadable files are silently skipped (returned as `None`).
pub fn read_configs(venv_path: &Path) -> ConfigFiles {
    let pyvenv_cfg_path = venv_path.join("pyvenv.cfg");
    let postactivate_path = venv_path.join("bin").join("postactivate");

    let pyvenv_cfg = fs::read_to_string(&pyvenv_cfg_path).ok();

    let postactivate = fs::read_to_string(&postactivate_path).ok();

    let postactivate_mtime = if postactivate.is_some() {
        fs::metadata(&postactivate_path)
            .ok()
            .and_then(|m| m.modified().ok())
    } else {
        None
    };

    ConfigFiles {
        pyvenv_cfg,
        postactivate,
        postactivate_path,
        postactivate_mtime,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::TempDir;

    #[test]
    fn test_read_configs_both_files_present() {
        let tmp = TempDir::new().unwrap();
        let venv = tmp.path().join("myvenv");
        fs::create_dir_all(venv.join("bin")).unwrap();
        fs::write(venv.join("pyvenv.cfg"), "home = /usr/bin\n").unwrap();
        fs::write(venv.join("bin/postactivate"), "export FOO=bar\n").unwrap();

        let configs = read_configs(&venv);

        assert_eq!(configs.pyvenv_cfg, Some("home = /usr/bin\n".to_string()));
        assert_eq!(configs.postactivate, Some("export FOO=bar\n".to_string()));
        assert_eq!(configs.postactivate_path, venv.join("bin/postactivate"));
        assert!(configs.postactivate_mtime.is_some());
    }

    #[test]
    fn test_read_configs_missing_postactivate() {
        let tmp = TempDir::new().unwrap();
        let venv = tmp.path().join("myvenv");
        fs::create_dir_all(venv.join("bin")).unwrap();
        fs::write(venv.join("pyvenv.cfg"), "home = /usr/bin\n").unwrap();

        let configs = read_configs(&venv);

        assert_eq!(configs.pyvenv_cfg, Some("home = /usr/bin\n".to_string()));
        assert_eq!(configs.postactivate, None);
        assert_eq!(configs.postactivate_path, venv.join("bin/postactivate"));
        assert_eq!(configs.postactivate_mtime, None);
    }

    #[test]
    fn test_read_configs_missing_pyvenv_cfg() {
        let tmp = TempDir::new().unwrap();
        let venv = tmp.path().join("myvenv");
        fs::create_dir_all(venv.join("bin")).unwrap();
        fs::write(venv.join("bin/postactivate"), "export BAZ=qux\n").unwrap();

        let configs = read_configs(&venv);

        assert_eq!(configs.pyvenv_cfg, None);
        assert_eq!(configs.postactivate, Some("export BAZ=qux\n".to_string()));
        assert!(configs.postactivate_mtime.is_some());
    }

    #[test]
    fn test_read_configs_both_missing() {
        let tmp = TempDir::new().unwrap();
        let venv = tmp.path().join("myvenv");
        fs::create_dir_all(&venv).unwrap();

        let configs = read_configs(&venv);

        assert_eq!(configs.pyvenv_cfg, None);
        assert_eq!(configs.postactivate, None);
        assert_eq!(configs.postactivate_path, venv.join("bin/postactivate"));
        assert_eq!(configs.postactivate_mtime, None);
    }

    #[test]
    fn test_read_configs_nonexistent_venv_path() {
        let path = PathBuf::from("/nonexistent/path/to/venv");

        let configs = read_configs(&path);

        assert_eq!(configs.pyvenv_cfg, None);
        assert_eq!(configs.postactivate, None);
        assert_eq!(configs.postactivate_path, path.join("bin/postactivate"));
        assert_eq!(configs.postactivate_mtime, None);
    }
}
