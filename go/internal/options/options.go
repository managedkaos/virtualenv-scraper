// Package options handles parsing and merging configuration from multiple
// sources for the virtualenv-viewer application.
//
// Configuration precedence (highest to lowest):
//  1. CLI flags: --restart-on-edit / --no-restart-on-edit
//  2. Environment variable: VENV_VIEWER_RESTART_ON_EDIT=1|0|true|false
//  3. Config file: ~/.virtualenv-viewer.toml (restart_on_edit = true|false)
//  4. Default: disabled (false)
package options

import (
	"os"
	"path/filepath"
	"strings"

	"github.com/BurntSushi/toml"
)

// AppOptions holds the resolved application configuration.
type AppOptions struct {
	RestartOnEdit bool // default: false
}

// configFile represents the TOML configuration file structure.
type configFile struct {
	RestartOnEdit *bool `toml:"restart_on_edit"`
}

// CLIFlags represents the parsed CLI flag state. A nil pointer means
// the flag was not explicitly provided by the user.
type CLIFlags struct {
	RestartOnEdit *bool
}

// configFilePath returns the path to the configuration file.
// Defaults to ~/.virtualenv-viewer.toml.
func configFilePath() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	return filepath.Join(home, ".virtualenv-viewer.toml")
}

// readConfigFile reads and parses the TOML configuration file.
// Returns nil if the file does not exist or cannot be parsed.
func readConfigFile(path string) *configFile {
	if path == "" {
		return nil
	}

	var cfg configFile
	_, err := toml.DecodeFile(path, &cfg)
	if err != nil {
		return nil
	}
	return &cfg
}

// parseEnvVar reads and parses the VENV_VIEWER_RESTART_ON_EDIT environment
// variable. Returns nil if the variable is unset or has an unrecognized value.
func parseEnvVar() *bool {
	val := os.Getenv("VENV_VIEWER_RESTART_ON_EDIT")
	if val == "" {
		return nil
	}

	val = strings.ToLower(strings.TrimSpace(val))
	switch val {
	case "1", "true":
		result := true
		return &result
	case "0", "false":
		result := false
		return &result
	default:
		return nil
	}
}

// Resolve merges configuration from CLI flags, environment variable, config
// file, and defaults using the defined precedence order:
// CLI > env var > config file > default (disabled).
func Resolve(cli CLIFlags) AppOptions {
	return ResolveWithConfigPath(cli, configFilePath())
}

// ResolveWithConfigPath merges configuration using a specified config file path.
// This is useful for testing with custom config file locations.
func ResolveWithConfigPath(cli CLIFlags, cfgPath string) AppOptions {
	// Precedence 1: CLI flags
	if cli.RestartOnEdit != nil {
		return AppOptions{RestartOnEdit: *cli.RestartOnEdit}
	}

	// Precedence 2: Environment variable
	if envVal := parseEnvVar(); envVal != nil {
		return AppOptions{RestartOnEdit: *envVal}
	}

	// Precedence 3: Config file
	if cfg := readConfigFile(cfgPath); cfg != nil && cfg.RestartOnEdit != nil {
		return AppOptions{RestartOnEdit: *cfg.RestartOnEdit}
	}

	// Precedence 4: Default (disabled)
	return AppOptions{RestartOnEdit: false}
}
