package config

import (
	"os"
	"path/filepath"
	"testing"
)

// helper: createVenvWithBothFiles creates a temp venv directory with both
// pyvenv.cfg and bin/postactivate files.
func createVenvWithBothFiles(t *testing.T, dir string, cfgContent, postactivateContent string) {
	t.Helper()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatalf("failed to create dir %s: %v", dir, err)
	}
	// Write pyvenv.cfg
	cfgPath := filepath.Join(dir, "pyvenv.cfg")
	if err := os.WriteFile(cfgPath, []byte(cfgContent), 0o644); err != nil {
		t.Fatalf("failed to write pyvenv.cfg: %v", err)
	}
	// Create bin/ directory and write postactivate
	binDir := filepath.Join(dir, "bin")
	if err := os.MkdirAll(binDir, 0o755); err != nil {
		t.Fatalf("failed to create bin dir: %v", err)
	}
	postactivatePath := filepath.Join(binDir, "postactivate")
	if err := os.WriteFile(postactivatePath, []byte(postactivateContent), 0o644); err != nil {
		t.Fatalf("failed to write postactivate: %v", err)
	}
}

// --- Unit Tests ---

func TestReadConfigs_BothFilesPresent(t *testing.T) {
	dir := t.TempDir()
	cfgContent := "home = /usr/bin\nversion = 3.11.0\n"
	postactivateContent := "export FOO=bar\n"
	createVenvWithBothFiles(t, dir, cfgContent, postactivateContent)

	result := ReadConfigs(dir)

	if result.PyvenvCfg == nil {
		t.Fatal("expected PyvenvCfg to be non-nil")
	}
	if *result.PyvenvCfg != cfgContent {
		t.Errorf("PyvenvCfg: expected %q, got %q", cfgContent, *result.PyvenvCfg)
	}

	if result.Postactivate == nil {
		t.Fatal("expected Postactivate to be non-nil")
	}
	if *result.Postactivate != postactivateContent {
		t.Errorf("Postactivate: expected %q, got %q", postactivateContent, *result.Postactivate)
	}
}

func TestReadConfigs_MissingPyvenvCfg_ReturnsNil(t *testing.T) {
	dir := t.TempDir()
	// Only create bin/postactivate, no pyvenv.cfg
	binDir := filepath.Join(dir, "bin")
	if err := os.MkdirAll(binDir, 0o755); err != nil {
		t.Fatalf("failed to create bin dir: %v", err)
	}
	postactivatePath := filepath.Join(binDir, "postactivate")
	if err := os.WriteFile(postactivatePath, []byte("export X=1\n"), 0o644); err != nil {
		t.Fatalf("failed to write postactivate: %v", err)
	}

	result := ReadConfigs(dir)

	if result.PyvenvCfg != nil {
		t.Errorf("expected PyvenvCfg to be nil when file is missing, got %q", *result.PyvenvCfg)
	}
	if result.Postactivate == nil {
		t.Fatal("expected Postactivate to be non-nil")
	}
}

func TestReadConfigs_MissingPostactivate_ReturnsNil(t *testing.T) {
	dir := t.TempDir()
	// Only create pyvenv.cfg, no bin/postactivate
	cfgPath := filepath.Join(dir, "pyvenv.cfg")
	if err := os.WriteFile(cfgPath, []byte("home = /usr/bin\n"), 0o644); err != nil {
		t.Fatalf("failed to write pyvenv.cfg: %v", err)
	}

	result := ReadConfigs(dir)

	if result.PyvenvCfg == nil {
		t.Fatal("expected PyvenvCfg to be non-nil")
	}
	if result.Postactivate != nil {
		t.Errorf("expected Postactivate to be nil when file is missing, got %q", *result.Postactivate)
	}
}

func TestReadConfigs_BothFilesMissing(t *testing.T) {
	dir := t.TempDir()
	// Empty directory, no config files at all

	result := ReadConfigs(dir)

	if result.PyvenvCfg != nil {
		t.Errorf("expected PyvenvCfg to be nil, got %q", *result.PyvenvCfg)
	}
	if result.Postactivate != nil {
		t.Errorf("expected Postactivate to be nil, got %q", *result.Postactivate)
	}
}

func TestReadConfigs_PostactivatePath_AlwaysSetCorrectly(t *testing.T) {
	dir := t.TempDir()

	result := ReadConfigs(dir)

	expectedPath := filepath.Join(dir, "bin", "postactivate")
	if result.PostactivatePath != expectedPath {
		t.Errorf("PostactivatePath: expected %q, got %q", expectedPath, result.PostactivatePath)
	}
}

func TestReadConfigs_PostactivatePath_SetEvenWhenFileMissing(t *testing.T) {
	dir := t.TempDir()
	// No files created at all

	result := ReadConfigs(dir)

	expectedPath := filepath.Join(dir, "bin", "postactivate")
	if result.PostactivatePath != expectedPath {
		t.Errorf("PostactivatePath should always be set; expected %q, got %q", expectedPath, result.PostactivatePath)
	}
}

func TestReadConfigs_PostactivateMtime_SetWhenFileExists(t *testing.T) {
	dir := t.TempDir()
	cfgContent := "home = /usr/bin\n"
	postactivateContent := "export PATH=$HOME/bin:$PATH\n"
	createVenvWithBothFiles(t, dir, cfgContent, postactivateContent)

	result := ReadConfigs(dir)

	if result.PostactivateMtime == nil {
		t.Fatal("expected PostactivateMtime to be non-nil when postactivate file exists")
	}
	// Verify mtime is reasonable (not zero time)
	if result.PostactivateMtime.IsZero() {
		t.Error("PostactivateMtime should not be zero time")
	}
}

func TestReadConfigs_PostactivateMtime_NilWhenFileMissing(t *testing.T) {
	dir := t.TempDir()
	// Only create pyvenv.cfg
	cfgPath := filepath.Join(dir, "pyvenv.cfg")
	if err := os.WriteFile(cfgPath, []byte("home = /usr/bin\n"), 0o644); err != nil {
		t.Fatalf("failed to write pyvenv.cfg: %v", err)
	}

	result := ReadConfigs(dir)

	if result.PostactivateMtime != nil {
		t.Errorf("expected PostactivateMtime to be nil when postactivate is missing, got %v", *result.PostactivateMtime)
	}
}

func TestReadConfigs_NonExistentVenvDirectory(t *testing.T) {
	nonExistentPath := filepath.Join(t.TempDir(), "does-not-exist")

	result := ReadConfigs(nonExistentPath)

	if result.PyvenvCfg != nil {
		t.Errorf("expected PyvenvCfg to be nil for non-existent dir, got %q", *result.PyvenvCfg)
	}
	if result.Postactivate != nil {
		t.Errorf("expected Postactivate to be nil for non-existent dir, got %q", *result.Postactivate)
	}
	if result.PostactivateMtime != nil {
		t.Errorf("expected PostactivateMtime to be nil for non-existent dir, got %v", *result.PostactivateMtime)
	}
	// PostactivatePath should still be set correctly
	expectedPath := filepath.Join(nonExistentPath, "bin", "postactivate")
	if result.PostactivatePath != expectedPath {
		t.Errorf("PostactivatePath: expected %q, got %q", expectedPath, result.PostactivatePath)
	}
}
