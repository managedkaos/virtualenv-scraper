package restart

import (
	"os"
	"path/filepath"
	"testing"
)

func TestRestartVirtualenv_Success(t *testing.T) {
	// Create a temp directory simulating a virtualenv with bin/activate.
	tmpDir := t.TempDir()
	binDir := filepath.Join(tmpDir, "bin")
	if err := os.MkdirAll(binDir, 0o755); err != nil {
		t.Fatalf("failed to create bin dir: %v", err)
	}

	// Write a minimal activate script that succeeds.
	activatePath := filepath.Join(binDir, "activate")
	if err := os.WriteFile(activatePath, []byte("# activate script\n"), 0o644); err != nil {
		t.Fatalf("failed to write activate script: %v", err)
	}

	result := RestartVirtualenv(tmpDir)

	if !result.Success {
		t.Errorf("expected success, got failure: %s", result.Message)
	}
	if result.Message == "" {
		t.Error("expected a non-empty confirmation message")
	}
}

func TestRestartVirtualenv_FailureMissingActivate(t *testing.T) {
	// Create a temp directory without an activate script.
	tmpDir := t.TempDir()

	result := RestartVirtualenv(tmpDir)

	if result.Success {
		t.Error("expected failure when activate script is missing")
	}
	if result.Message == "" {
		t.Error("expected a non-empty error message")
	}
}

func TestRestartVirtualenv_FailureInvalidScript(t *testing.T) {
	// Create a temp directory with an activate script that exits with error.
	tmpDir := t.TempDir()
	binDir := filepath.Join(tmpDir, "bin")
	if err := os.MkdirAll(binDir, 0o755); err != nil {
		t.Fatalf("failed to create bin dir: %v", err)
	}

	activatePath := filepath.Join(binDir, "activate")
	if err := os.WriteFile(activatePath, []byte("exit 1\n"), 0o644); err != nil {
		t.Fatalf("failed to write activate script: %v", err)
	}

	result := RestartVirtualenv(tmpDir)

	if result.Success {
		t.Error("expected failure when activate script exits with error")
	}
	if result.Message == "" {
		t.Error("expected a non-empty error message")
	}
}

func TestRestartVirtualenv_SuccessMessageContainsVenvName(t *testing.T) {
	// Create a temp virtualenv with a known basename.
	tmpDir := t.TempDir()
	venvDir := filepath.Join(tmpDir, "myenv")
	binDir := filepath.Join(venvDir, "bin")
	if err := os.MkdirAll(binDir, 0o755); err != nil {
		t.Fatalf("failed to create bin dir: %v", err)
	}

	activatePath := filepath.Join(binDir, "activate")
	if err := os.WriteFile(activatePath, []byte("# activate\n"), 0o644); err != nil {
		t.Fatalf("failed to write activate script: %v", err)
	}

	result := RestartVirtualenv(venvDir)

	if !result.Success {
		t.Fatalf("expected success, got failure: %s", result.Message)
	}
	expected := "myenv"
	if len(result.Message) == 0 {
		t.Fatal("expected non-empty message")
	}
	if !contains(result.Message, expected) {
		t.Errorf("expected message to contain %q, got %q", expected, result.Message)
	}
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > 0 && containsSubstr(s, substr))
}

func containsSubstr(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
