use clap::Parser;
use serde::Deserialize;
use std::env;
use std::fs;
use std::path::PathBuf;

/// Application options resolved from multiple configuration sources.
///
/// Precedence (highest to lowest):
///   CLI flag > Environment variable > Config file > Default (disabled)
#[derive(Debug, Clone, Default, PartialEq)]
pub struct AppOptions {
    pub restart_on_edit: bool,
}

/// CLI argument definition using clap derive.
#[derive(Parser, Debug)]
#[command(name = "virtualenv-viewer")]
#[command(about = "Interactive terminal UI for viewing virtualenv configuration")]
pub struct CliArgs {
    /// Enable restart-on-edit: restart virtualenv after editing postactivate
    #[arg(long = "restart-on-edit", conflicts_with = "no_restart_on_edit")]
    pub restart_on_edit: bool,

    /// Disable restart-on-edit (explicit override)
    #[arg(long = "no-restart-on-edit", conflicts_with = "restart_on_edit")]
    pub no_restart_on_edit: bool,
}

/// Represents the CLI's contribution to restart_on_edit.
/// `None` means CLI did not specify either flag.
fn cli_restart_on_edit(args: &CliArgs) -> Option<bool> {
    if args.restart_on_edit {
        Some(true)
    } else if args.no_restart_on_edit {
        Some(false)
    } else {
        None
    }
}

/// TOML config file structure for `~/.virtualenv-viewer.toml`.
#[derive(Deserialize, Debug)]
struct ConfigFile {
    restart_on_edit: Option<bool>,
}

/// Parse the environment variable `VENV_VIEWER_RESTART_ON_EDIT`.
/// Accepts: "1", "true" (case-insensitive) → Some(true)
///          "0", "false" (case-insensitive) → Some(false)
///          Anything else or unset → None
fn env_restart_on_edit() -> Option<bool> {
    env_restart_on_edit_from(env::var("VENV_VIEWER_RESTART_ON_EDIT").ok())
}

/// Testable version that takes the env var value directly.
fn env_restart_on_edit_from(value: Option<String>) -> Option<bool> {
    match value {
        Some(v) => match v.to_lowercase().as_str() {
            "1" | "true" => Some(true),
            "0" | "false" => Some(false),
            _ => None,
        },
        None => None,
    }
}

/// Read the config file at `~/.virtualenv-viewer.toml`.
/// Returns `None` if the file doesn't exist or can't be parsed.
fn config_file_restart_on_edit() -> Option<bool> {
    config_file_restart_on_edit_from(config_file_path())
}

/// Testable version that accepts an explicit path.
fn config_file_restart_on_edit_from(path: Option<PathBuf>) -> Option<bool> {
    let path = path?;
    let content = fs::read_to_string(path).ok()?;
    let config: ConfigFile = toml::from_str(&content).ok()?;
    config.restart_on_edit
}

/// Returns the default config file path: `~/.virtualenv-viewer.toml`
fn config_file_path() -> Option<PathBuf> {
    dirs_home().map(|home| home.join(".virtualenv-viewer.toml"))
}

/// Get the user's home directory.
fn dirs_home() -> Option<PathBuf> {
    env::var("HOME").ok().map(PathBuf::from)
}

/// Resolve `AppOptions` from all configuration sources using precedence:
/// CLI > env var > config file > default (disabled).
pub fn resolve_options() -> AppOptions {
    let args = CliArgs::parse();
    resolve_options_from_sources(
        cli_restart_on_edit(&args),
        env_restart_on_edit(),
        config_file_restart_on_edit(),
    )
}

/// Testable core resolution logic. Takes pre-extracted option values from each source.
pub fn resolve_options_from_sources(
    cli: Option<bool>,
    env: Option<bool>,
    config: Option<bool>,
) -> AppOptions {
    let restart_on_edit = cli.or(env).or(config).unwrap_or(false);

    AppOptions { restart_on_edit }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_is_disabled() {
        let opts = resolve_options_from_sources(None, None, None);
        assert!(!opts.restart_on_edit);
    }

    #[test]
    fn test_config_file_sets_value() {
        let opts = resolve_options_from_sources(None, None, Some(true));
        assert!(opts.restart_on_edit);
    }

    #[test]
    fn test_env_overrides_config() {
        let opts = resolve_options_from_sources(None, Some(false), Some(true));
        assert!(!opts.restart_on_edit);
    }

    #[test]
    fn test_cli_overrides_env_and_config() {
        let opts = resolve_options_from_sources(Some(true), Some(false), Some(false));
        assert!(opts.restart_on_edit);
    }

    #[test]
    fn test_cli_false_overrides_env_true() {
        let opts = resolve_options_from_sources(Some(false), Some(true), Some(true));
        assert!(!opts.restart_on_edit);
    }

    #[test]
    fn test_env_overrides_default() {
        let opts = resolve_options_from_sources(None, Some(true), None);
        assert!(opts.restart_on_edit);
    }

    #[test]
    fn test_env_parsing_true_values() {
        assert_eq!(env_restart_on_edit_from(Some("1".to_string())), Some(true));
        assert_eq!(
            env_restart_on_edit_from(Some("true".to_string())),
            Some(true)
        );
        assert_eq!(
            env_restart_on_edit_from(Some("TRUE".to_string())),
            Some(true)
        );
        assert_eq!(
            env_restart_on_edit_from(Some("True".to_string())),
            Some(true)
        );
    }

    #[test]
    fn test_env_parsing_false_values() {
        assert_eq!(env_restart_on_edit_from(Some("0".to_string())), Some(false));
        assert_eq!(
            env_restart_on_edit_from(Some("false".to_string())),
            Some(false)
        );
        assert_eq!(
            env_restart_on_edit_from(Some("FALSE".to_string())),
            Some(false)
        );
        assert_eq!(
            env_restart_on_edit_from(Some("False".to_string())),
            Some(false)
        );
    }

    #[test]
    fn test_env_parsing_invalid_values() {
        assert_eq!(env_restart_on_edit_from(Some("yes".to_string())), None);
        assert_eq!(env_restart_on_edit_from(Some("no".to_string())), None);
        assert_eq!(env_restart_on_edit_from(Some("".to_string())), None);
        assert_eq!(env_restart_on_edit_from(Some("2".to_string())), None);
    }

    #[test]
    fn test_env_parsing_unset() {
        assert_eq!(env_restart_on_edit_from(None), None);
    }

    #[test]
    fn test_config_file_parsing_valid() {
        let dir = tempfile::tempdir().unwrap();
        let config_path = dir.path().join(".virtualenv-viewer.toml");
        fs::write(&config_path, "restart_on_edit = true\n").unwrap();

        let result = config_file_restart_on_edit_from(Some(config_path));
        assert_eq!(result, Some(true));
    }

    #[test]
    fn test_config_file_parsing_false() {
        let dir = tempfile::tempdir().unwrap();
        let config_path = dir.path().join(".virtualenv-viewer.toml");
        fs::write(&config_path, "restart_on_edit = false\n").unwrap();

        let result = config_file_restart_on_edit_from(Some(config_path));
        assert_eq!(result, Some(false));
    }

    #[test]
    fn test_config_file_missing() {
        let result =
            config_file_restart_on_edit_from(Some(PathBuf::from("/nonexistent/path.toml")));
        assert_eq!(result, None);
    }

    #[test]
    fn test_config_file_no_path() {
        let result = config_file_restart_on_edit_from(None);
        assert_eq!(result, None);
    }

    #[test]
    fn test_config_file_invalid_toml() {
        let dir = tempfile::tempdir().unwrap();
        let config_path = dir.path().join(".virtualenv-viewer.toml");
        fs::write(&config_path, "this is not valid toml {{{{").unwrap();

        let result = config_file_restart_on_edit_from(Some(config_path));
        assert_eq!(result, None);
    }

    #[test]
    fn test_config_file_missing_field() {
        let dir = tempfile::tempdir().unwrap();
        let config_path = dir.path().join(".virtualenv-viewer.toml");
        fs::write(&config_path, "other_field = true\n").unwrap();

        let result = config_file_restart_on_edit_from(Some(config_path));
        assert_eq!(result, None);
    }

    #[test]
    fn test_cli_args_restart_on_edit() {
        let args = CliArgs {
            restart_on_edit: true,
            no_restart_on_edit: false,
        };
        assert_eq!(cli_restart_on_edit(&args), Some(true));
    }

    #[test]
    fn test_cli_args_no_restart_on_edit() {
        let args = CliArgs {
            restart_on_edit: false,
            no_restart_on_edit: true,
        };
        assert_eq!(cli_restart_on_edit(&args), Some(false));
    }

    #[test]
    fn test_cli_args_neither() {
        let args = CliArgs {
            restart_on_edit: false,
            no_restart_on_edit: false,
        };
        assert_eq!(cli_restart_on_edit(&args), None);
    }
}
