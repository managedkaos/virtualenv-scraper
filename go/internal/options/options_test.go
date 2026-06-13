package options

import (
	"os"
	"path/filepath"
	"testing"

	"pgregory.net/rapid"
)

// helper: boolPtr returns a pointer to the given bool value.
func boolPtr(v bool) *bool {
	return &v
}

// helper: writeTOMLConfig creates a TOML config file at the given path with the
// specified restart_on_edit value.
func writeTOMLConfig(t *testing.T, dir string, value bool) string {
	t.Helper()
	path := filepath.Join(dir, ".virtualenv-viewer.toml")
	content := "restart_on_edit = false\n"
	if value {
		content = "restart_on_edit = true\n"
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("failed to write config file: %v", err)
	}
	return path
}

// --- Unit Tests ---

func TestResolve_DefaultValue_NoSourceSpecified(t *testing.T) {
	t.Setenv("VENV_VIEWER_RESTART_ON_EDIT", "")

	cli := CLIFlags{RestartOnEdit: nil}
	opts := ResolveWithConfigPath(cli, "/nonexistent/path/config.toml")

	if opts.RestartOnEdit != false {
		t.Errorf("expected default RestartOnEdit=false, got %v", opts.RestartOnEdit)
	}
}

func TestResolve_CLIOverridesEnvAndConfig(t *testing.T) {
	dir := t.TempDir()
	cfgPath := writeTOMLConfig(t, dir, true)
	t.Setenv("VENV_VIEWER_RESTART_ON_EDIT", "true")

	// CLI explicitly sets false → should override env (true) and config (true)
	cli := CLIFlags{RestartOnEdit: boolPtr(false)}
	opts := ResolveWithConfigPath(cli, cfgPath)

	if opts.RestartOnEdit != false {
		t.Errorf("expected CLI false to override env and config, got %v", opts.RestartOnEdit)
	}
}

func TestResolve_CLITrueOverridesEnvFalseAndConfigFalse(t *testing.T) {
	dir := t.TempDir()
	cfgPath := writeTOMLConfig(t, dir, false)
	t.Setenv("VENV_VIEWER_RESTART_ON_EDIT", "false")

	cli := CLIFlags{RestartOnEdit: boolPtr(true)}
	opts := ResolveWithConfigPath(cli, cfgPath)

	if opts.RestartOnEdit != true {
		t.Errorf("expected CLI true to override env and config, got %v", opts.RestartOnEdit)
	}
}

func TestResolve_EnvOverridesConfig(t *testing.T) {
	dir := t.TempDir()
	cfgPath := writeTOMLConfig(t, dir, false)
	t.Setenv("VENV_VIEWER_RESTART_ON_EDIT", "true")

	cli := CLIFlags{RestartOnEdit: nil}
	opts := ResolveWithConfigPath(cli, cfgPath)

	if opts.RestartOnEdit != true {
		t.Errorf("expected env true to override config false, got %v", opts.RestartOnEdit)
	}
}

func TestResolve_ConfigOverridesDefault(t *testing.T) {
	dir := t.TempDir()
	cfgPath := writeTOMLConfig(t, dir, true)
	t.Setenv("VENV_VIEWER_RESTART_ON_EDIT", "")

	cli := CLIFlags{RestartOnEdit: nil}
	opts := ResolveWithConfigPath(cli, cfgPath)

	if opts.RestartOnEdit != true {
		t.Errorf("expected config true to override default false, got %v", opts.RestartOnEdit)
	}
}

func TestResolve_CLIFalseOverridesEnvTrue(t *testing.T) {
	t.Setenv("VENV_VIEWER_RESTART_ON_EDIT", "true")

	cli := CLIFlags{RestartOnEdit: boolPtr(false)}
	opts := ResolveWithConfigPath(cli, "/nonexistent/config.toml")

	if opts.RestartOnEdit != false {
		t.Errorf("expected CLI false to override env true, got %v", opts.RestartOnEdit)
	}
}

func TestResolve_EnvVarParsing_1(t *testing.T) {
	t.Setenv("VENV_VIEWER_RESTART_ON_EDIT", "1")

	cli := CLIFlags{RestartOnEdit: nil}
	opts := ResolveWithConfigPath(cli, "/nonexistent/config.toml")

	if opts.RestartOnEdit != true {
		t.Errorf("expected env '1' to resolve to true, got %v", opts.RestartOnEdit)
	}
}

func TestResolve_EnvVarParsing_0(t *testing.T) {
	t.Setenv("VENV_VIEWER_RESTART_ON_EDIT", "0")

	cli := CLIFlags{RestartOnEdit: nil}
	opts := ResolveWithConfigPath(cli, "/nonexistent/config.toml")

	if opts.RestartOnEdit != false {
		t.Errorf("expected env '0' to resolve to false, got %v", opts.RestartOnEdit)
	}
}

func TestResolve_EnvVarParsing_True(t *testing.T) {
	t.Setenv("VENV_VIEWER_RESTART_ON_EDIT", "true")

	cli := CLIFlags{RestartOnEdit: nil}
	opts := ResolveWithConfigPath(cli, "/nonexistent/config.toml")

	if opts.RestartOnEdit != true {
		t.Errorf("expected env 'true' to resolve to true, got %v", opts.RestartOnEdit)
	}
}

func TestResolve_EnvVarParsing_False(t *testing.T) {
	t.Setenv("VENV_VIEWER_RESTART_ON_EDIT", "false")

	cli := CLIFlags{RestartOnEdit: nil}
	opts := ResolveWithConfigPath(cli, "/nonexistent/config.toml")

	if opts.RestartOnEdit != false {
		t.Errorf("expected env 'false' to resolve to false, got %v", opts.RestartOnEdit)
	}
}

func TestResolve_EnvVarParsing_Invalid(t *testing.T) {
	dir := t.TempDir()
	cfgPath := writeTOMLConfig(t, dir, true)
	t.Setenv("VENV_VIEWER_RESTART_ON_EDIT", "invalid")

	// Invalid env var should be ignored, falls through to config
	cli := CLIFlags{RestartOnEdit: nil}
	opts := ResolveWithConfigPath(cli, cfgPath)

	if opts.RestartOnEdit != true {
		t.Errorf("expected invalid env var to be ignored (config=true), got %v", opts.RestartOnEdit)
	}
}

func TestResolve_EnvVarParsing_InvalidFallsToDefault(t *testing.T) {
	t.Setenv("VENV_VIEWER_RESTART_ON_EDIT", "yes")

	// Invalid env var and no config → default (false)
	cli := CLIFlags{RestartOnEdit: nil}
	opts := ResolveWithConfigPath(cli, "/nonexistent/config.toml")

	if opts.RestartOnEdit != false {
		t.Errorf("expected invalid env var with no config to fall to default false, got %v", opts.RestartOnEdit)
	}
}

func TestResolve_ConfigFileParsing_ValidTOML(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, ".virtualenv-viewer.toml")
	if err := os.WriteFile(path, []byte("restart_on_edit = true\n"), 0o644); err != nil {
		t.Fatalf("failed to write config: %v", err)
	}
	t.Setenv("VENV_VIEWER_RESTART_ON_EDIT", "")

	cli := CLIFlags{RestartOnEdit: nil}
	opts := ResolveWithConfigPath(cli, path)

	if opts.RestartOnEdit != true {
		t.Errorf("expected valid TOML config true, got %v", opts.RestartOnEdit)
	}
}

func TestResolve_ConfigFileParsing_MissingFile(t *testing.T) {
	t.Setenv("VENV_VIEWER_RESTART_ON_EDIT", "")

	cli := CLIFlags{RestartOnEdit: nil}
	opts := ResolveWithConfigPath(cli, "/nonexistent/path/.virtualenv-viewer.toml")

	if opts.RestartOnEdit != false {
		t.Errorf("expected missing config to fall to default false, got %v", opts.RestartOnEdit)
	}
}

func TestResolve_ConfigFileParsing_InvalidTOML(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, ".virtualenv-viewer.toml")
	// Write invalid TOML content
	if err := os.WriteFile(path, []byte("this is not valid toml {{{\n"), 0o644); err != nil {
		t.Fatalf("failed to write config: %v", err)
	}
	t.Setenv("VENV_VIEWER_RESTART_ON_EDIT", "")

	cli := CLIFlags{RestartOnEdit: nil}
	opts := ResolveWithConfigPath(cli, path)

	if opts.RestartOnEdit != false {
		t.Errorf("expected invalid TOML config to fall to default false, got %v", opts.RestartOnEdit)
	}
}

func TestResolve_ConfigFile_MissingKey(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, ".virtualenv-viewer.toml")
	// Valid TOML but without restart_on_edit key
	if err := os.WriteFile(path, []byte("some_other_option = true\n"), 0o644); err != nil {
		t.Fatalf("failed to write config: %v", err)
	}
	t.Setenv("VENV_VIEWER_RESTART_ON_EDIT", "")

	cli := CLIFlags{RestartOnEdit: nil}
	opts := ResolveWithConfigPath(cli, path)

	if opts.RestartOnEdit != false {
		t.Errorf("expected config without restart_on_edit key to fall to default false, got %v", opts.RestartOnEdit)
	}
}

// --- Property-Based Tests ---

// Property 10: Configuration Precedence
// For any combination of CLI (*bool), env var (*bool), and config file (*bool),
// the resolved value equals the highest-precedence source present.
// CLI > env var > config file > default (false)
// **Validates: Requirements 6.5**
func TestProperty10_ConfigurationPrecedence(t *testing.T) {
	// Feature: virtualenv-config-viewer, Property 10: Configuration Precedence
	rapid.Check(t, func(rt *rapid.T) {
		// Generate optional CLI value (nil means not provided)
		hasCLI := rapid.Bool().Draw(rt, "hasCLI")
		var cliValue *bool
		if hasCLI {
			v := rapid.Bool().Draw(rt, "cliValue")
			cliValue = &v
		}

		// Generate optional env var value (nil means not set, or invalid)
		envState := rapid.IntRange(0, 2).Draw(rt, "envState")
		// 0 = not set, 1 = set to true, 2 = set to false
		var envVarStr string
		var envExpected *bool
		switch envState {
		case 0:
			envVarStr = ""
			envExpected = nil
		case 1:
			// Pick a valid "true" representation
			trueStrs := []string{"1", "true", "TRUE", "True"}
			idx := rapid.IntRange(0, len(trueStrs)-1).Draw(rt, "trueStrIdx")
			envVarStr = trueStrs[idx]
			v := true
			envExpected = &v
		case 2:
			// Pick a valid "false" representation
			falseStrs := []string{"0", "false", "FALSE", "False"}
			idx := rapid.IntRange(0, len(falseStrs)-1).Draw(rt, "falseStrIdx")
			envVarStr = falseStrs[idx]
			v := false
			envExpected = &v
		}

		// Generate optional config file value (nil means missing/invalid)
		hasConfig := rapid.Bool().Draw(rt, "hasConfig")
		var configValue *bool
		var cfgPath string
		if hasConfig {
			v := rapid.Bool().Draw(rt, "configValue")
			configValue = &v
			dir, err := os.MkdirTemp("", "options-prop10-*")
			if err != nil {
				rt.Fatalf("failed to create temp dir: %v", err)
			}
			defer os.RemoveAll(dir)
			cfgFile := filepath.Join(dir, ".virtualenv-viewer.toml")
			content := "restart_on_edit = false\n"
			if v {
				content = "restart_on_edit = true\n"
			}
			if err := os.WriteFile(cfgFile, []byte(content), 0o644); err != nil {
				rt.Fatalf("failed to write config: %v", err)
			}
			cfgPath = cfgFile
		} else {
			cfgPath = "/nonexistent/path/.virtualenv-viewer.toml"
		}

		// Set environment
		os.Setenv("VENV_VIEWER_RESTART_ON_EDIT", envVarStr)
		defer os.Unsetenv("VENV_VIEWER_RESTART_ON_EDIT")

		// Resolve
		cli := CLIFlags{RestartOnEdit: cliValue}
		opts := ResolveWithConfigPath(cli, cfgPath)

		// Compute expected result based on precedence
		var expected bool
		switch {
		case cliValue != nil:
			expected = *cliValue
		case envExpected != nil:
			expected = *envExpected
		case configValue != nil:
			expected = *configValue
		default:
			expected = false
		}

		if opts.RestartOnEdit != expected {
			rt.Fatalf("precedence violation: CLI=%v, env=%q (parsed=%v), config=%v → got %v, want %v",
				cliValue, envVarStr, envExpected, configValue, opts.RestartOnEdit, expected)
		}
	})
}
