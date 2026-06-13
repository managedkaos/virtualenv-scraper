package detector

import (
	"os"
	"path/filepath"
	"testing"

	"pgregory.net/rapid"
)

// helper: createValidVirtualenv creates a temp directory with pyvenv.cfg inside.
func createValidVirtualenv(t *testing.T, dir string) {
	t.Helper()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatalf("failed to create dir %s: %v", dir, err)
	}
	cfgPath := filepath.Join(dir, "pyvenv.cfg")
	if err := os.WriteFile(cfgPath, []byte("home = /usr/bin\n"), 0o644); err != nil {
		t.Fatalf("failed to write pyvenv.cfg in %s: %v", dir, err)
	}
}

// resolveSymlinks resolves symlinks in a path (needed on macOS where /var -> /private/var).
func resolveSymlinks(t *testing.T, path string) string {
	t.Helper()
	resolved, err := filepath.EvalSymlinks(path)
	if err != nil {
		t.Fatalf("failed to resolve symlinks for %s: %v", path, err)
	}
	return resolved
}

// --- Unit Tests ---

func TestIsValidVirtualenv_WithPyvenvCfg(t *testing.T) {
	dir := t.TempDir()
	createValidVirtualenv(t, dir)

	if !isValidVirtualenv(dir) {
		t.Errorf("expected %s to be a valid virtualenv", dir)
	}
}

func TestIsValidVirtualenv_WithoutPyvenvCfg(t *testing.T) {
	dir := t.TempDir()

	if isValidVirtualenv(dir) {
		t.Errorf("expected %s to NOT be a valid virtualenv (no pyvenv.cfg)", dir)
	}
}

func TestIsValidVirtualenv_PyvenvCfgIsDirectory(t *testing.T) {
	dir := t.TempDir()
	// Create pyvenv.cfg as a directory, not a file
	cfgDir := filepath.Join(dir, "pyvenv.cfg")
	if err := os.MkdirAll(cfgDir, 0o755); err != nil {
		t.Fatalf("failed to create dir: %v", err)
	}

	if isValidVirtualenv(dir) {
		t.Errorf("expected %s to NOT be valid when pyvenv.cfg is a directory", dir)
	}
}

func TestIsValidVirtualenv_NonexistentPath(t *testing.T) {
	if isValidVirtualenv("/nonexistent/path/that/does/not/exist") {
		t.Error("expected nonexistent path to NOT be a valid virtualenv")
	}
}

func TestDetectVirtualenv_VirtualEnvSet_Valid(t *testing.T) {
	dir := t.TempDir()
	createValidVirtualenv(t, dir)

	t.Setenv("VIRTUAL_ENV", dir)

	result, err := DetectVirtualenv()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != dir {
		t.Errorf("expected %s, got %s", dir, result)
	}
}

func TestDetectVirtualenv_VirtualEnvSet_Invalid(t *testing.T) {
	dir := t.TempDir() // No pyvenv.cfg

	t.Setenv("VIRTUAL_ENV", dir)

	_, err := DetectVirtualenv()
	if err == nil {
		t.Fatal("expected error when VIRTUAL_ENV is set but invalid")
	}
	if !errorIs(err, ErrVirtualEnvInvalid) {
		t.Errorf("expected ErrVirtualEnvInvalid, got: %v", err)
	}
}

func TestDetectVirtualenv_DotEnvPriority(t *testing.T) {
	cwd := resolveSymlinks(t, t.TempDir())
	if err := os.Chdir(cwd); err != nil {
		t.Fatalf("failed to chdir: %v", err)
	}
	t.Setenv("VIRTUAL_ENV", "")

	// Create .env and .venv both valid
	createValidVirtualenv(t, filepath.Join(cwd, ".env"))
	createValidVirtualenv(t, filepath.Join(cwd, ".venv"))

	result, err := DetectVirtualenv()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expected := filepath.Join(cwd, ".env")
	if result != expected {
		t.Errorf("expected %s (higher priority), got %s", expected, result)
	}
}

func TestDetectVirtualenv_DotVenvPriority(t *testing.T) {
	cwd := resolveSymlinks(t, t.TempDir())
	if err := os.Chdir(cwd); err != nil {
		t.Fatalf("failed to chdir: %v", err)
	}
	t.Setenv("VIRTUAL_ENV", "")

	// Only .venv and venv exist
	createValidVirtualenv(t, filepath.Join(cwd, ".venv"))
	createValidVirtualenv(t, filepath.Join(cwd, "venv"))

	result, err := DetectVirtualenv()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expected := filepath.Join(cwd, ".venv")
	if result != expected {
		t.Errorf("expected %s (higher priority), got %s", expected, result)
	}
}

func TestDetectVirtualenv_VenvPriority(t *testing.T) {
	cwd := resolveSymlinks(t, t.TempDir())
	if err := os.Chdir(cwd); err != nil {
		t.Fatalf("failed to chdir: %v", err)
	}
	t.Setenv("VIRTUAL_ENV", "")

	// Only venv and env exist
	createValidVirtualenv(t, filepath.Join(cwd, "venv"))
	createValidVirtualenv(t, filepath.Join(cwd, "env"))

	result, err := DetectVirtualenv()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expected := filepath.Join(cwd, "venv")
	if result != expected {
		t.Errorf("expected %s (higher priority), got %s", expected, result)
	}
}

func TestDetectVirtualenv_EnvFallback(t *testing.T) {
	cwd := resolveSymlinks(t, t.TempDir())
	if err := os.Chdir(cwd); err != nil {
		t.Fatalf("failed to chdir: %v", err)
	}
	t.Setenv("VIRTUAL_ENV", "")

	// Only env exists
	createValidVirtualenv(t, filepath.Join(cwd, "env"))

	result, err := DetectVirtualenv()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expected := filepath.Join(cwd, "env")
	if result != expected {
		t.Errorf("expected %s, got %s", expected, result)
	}
}

func TestDetectVirtualenv_NoVirtualenvFound(t *testing.T) {
	cwd := resolveSymlinks(t, t.TempDir())
	if err := os.Chdir(cwd); err != nil {
		t.Fatalf("failed to chdir: %v", err)
	}
	t.Setenv("VIRTUAL_ENV", "")

	_, err := DetectVirtualenv()
	if err == nil {
		t.Fatal("expected error when no virtualenv is found")
	}
	if !errorIs(err, ErrNoVirtualenvFound) {
		t.Errorf("expected ErrNoVirtualenvFound, got: %v", err)
	}
}

func TestDetectVirtualenv_SkipsInvalidCandidates(t *testing.T) {
	cwd := resolveSymlinks(t, t.TempDir())
	if err := os.Chdir(cwd); err != nil {
		t.Fatalf("failed to chdir: %v", err)
	}
	t.Setenv("VIRTUAL_ENV", "")

	// Create .env and .venv as directories WITHOUT pyvenv.cfg
	if err := os.MkdirAll(filepath.Join(cwd, ".env"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(cwd, ".venv"), 0o755); err != nil {
		t.Fatal(err)
	}
	// Create venv as a valid virtualenv
	createValidVirtualenv(t, filepath.Join(cwd, "venv"))

	result, err := DetectVirtualenv()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expected := filepath.Join(cwd, "venv")
	if result != expected {
		t.Errorf("expected %s (first valid), got %s", expected, result)
	}
}

func TestDetectVirtualenv_VirtualEnvTakesPriorityOverCwd(t *testing.T) {
	cwd := t.TempDir()
	if err := os.Chdir(cwd); err != nil {
		t.Fatalf("failed to chdir: %v", err)
	}

	// Create .env as valid in cwd
	createValidVirtualenv(t, filepath.Join(cwd, ".env"))

	// Set VIRTUAL_ENV to a different valid dir
	venvDir := t.TempDir()
	createValidVirtualenv(t, venvDir)
	t.Setenv("VIRTUAL_ENV", venvDir)

	result, err := DetectVirtualenv()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != venvDir {
		t.Errorf("expected VIRTUAL_ENV (%s) to take priority, got %s", venvDir, result)
	}
}

// errorIs is a helper that unwraps and checks errors.Is
func errorIs(err, target error) bool {
	return err != nil && (err == target || (err.Error() != "" && target.Error() != "" && contains(err.Error(), target.Error())))
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > 0 && containsHelper(s, substr))
}

func containsHelper(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

// --- Property-Based Tests ---

// Property 1: Detection Priority Ordering
// For any set of candidate directories that contain a valid pyvenv.cfg file,
// the Virtualenv Detector SHALL return the directory with the highest priority.
// **Validates: Requirements 1.3, 1.5**
func TestProperty1_DetectionPriorityOrdering(t *testing.T) {
	// Feature: virtualenv-config-viewer, Property 1: Detection Priority Ordering
	rapid.Check(t, func(rt *rapid.T) {
		cwd, err := os.MkdirTemp("", "detector-prop1-*")
		if err != nil {
			rt.Fatalf("failed to create temp dir: %v", err)
		}
		defer os.RemoveAll(cwd)

		// Resolve symlinks (e.g., /var -> /private/var on macOS)
		cwd, err = filepath.EvalSymlinks(cwd)
		if err != nil {
			rt.Fatalf("failed to resolve symlinks: %v", err)
		}

		origDir, _ := os.Getwd()
		if err := os.Chdir(cwd); err != nil {
			rt.Fatalf("failed to chdir: %v", err)
		}
		defer func() { _ = os.Chdir(origDir) }()

		origVenv := os.Getenv("VIRTUAL_ENV")
		os.Setenv("VIRTUAL_ENV", "")
		defer os.Setenv("VIRTUAL_ENV", origVenv)

		candidateNames := []string{".env", ".venv", "venv", "env"}

		// Generate a random non-empty subset of candidates to make valid
		validMask := rapid.SliceOfN(rapid.Bool(), 4, 4).Draw(rt, "validMask")

		// Ensure at least one candidate is valid
		anyValid := false
		for _, v := range validMask {
			if v {
				anyValid = true
				break
			}
		}
		if !anyValid {
			// Force at least one to be valid
			idx := rapid.IntRange(0, 3).Draw(rt, "forceValidIdx")
			validMask[idx] = true
		}

		// Create the directories
		var expectedWinner string
		for i, name := range candidateNames {
			dirPath := filepath.Join(cwd, name)
			if validMask[i] {
				createValidVirtualenvRapid(rt, dirPath)
				if expectedWinner == "" {
					expectedWinner = dirPath
				}
			} else {
				// Create the dir but without pyvenv.cfg (invalid)
				if err := os.MkdirAll(dirPath, 0o755); err != nil {
					rt.Fatalf("failed to create dir: %v", err)
				}
			}
		}

		result, err := DetectVirtualenv()
		if err != nil {
			rt.Fatalf("unexpected error: %v", err)
		}
		if result != expectedWinner {
			rt.Fatalf("expected highest priority %s, got %s", expectedWinner, result)
		}
	})
}

// Property 2: Virtualenv Validation
// For any directory path, isValidVirtualenv(path) SHALL return true if and only if
// the file {path}/pyvenv.cfg exists. Directories without pyvenv.cfg must always
// return false; directories with pyvenv.cfg must always return true.
// **Validates: Requirements 1.6**
func TestProperty2_VirtualenvValidation(t *testing.T) {
	// Feature: virtualenv-config-viewer, Property 2: Virtualenv Validation
	rapid.Check(t, func(rt *rapid.T) {
		dir, err := os.MkdirTemp("", "detector-prop2-*")
		if err != nil {
			rt.Fatalf("failed to create temp dir: %v", err)
		}
		defer os.RemoveAll(dir)

		// Resolve symlinks (e.g., /var -> /private/var on macOS)
		dir, err = filepath.EvalSymlinks(dir)
		if err != nil {
			rt.Fatalf("failed to resolve symlinks: %v", err)
		}

		hasCfg := rapid.Bool().Draw(rt, "hasPyvenvCfg")

		if hasCfg {
			cfgPath := filepath.Join(dir, "pyvenv.cfg")
			if err := os.WriteFile(cfgPath, []byte("home = /usr/bin\n"), 0o644); err != nil {
				rt.Fatalf("failed to write pyvenv.cfg: %v", err)
			}
		}

		result := isValidVirtualenv(dir)
		if hasCfg && !result {
			rt.Fatalf("expected isValidVirtualenv=true when pyvenv.cfg exists in %s", dir)
		}
		if !hasCfg && result {
			rt.Fatalf("expected isValidVirtualenv=false when pyvenv.cfg does not exist in %s", dir)
		}
	})
}

// createValidVirtualenvRapid is a helper for rapid tests.
func createValidVirtualenvRapid(rt *rapid.T, dir string) {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		rt.Fatalf("failed to create dir %s: %v", dir, err)
	}
	cfgPath := filepath.Join(dir, "pyvenv.cfg")
	if err := os.WriteFile(cfgPath, []byte("home = /usr/bin\n"), 0o644); err != nil {
		rt.Fatalf("failed to write pyvenv.cfg in %s: %v", dir, err)
	}
}
