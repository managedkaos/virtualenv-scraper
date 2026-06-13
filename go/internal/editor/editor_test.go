package editor

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestLaunchEditor_NoEditorEnvVar(t *testing.T) {
	// Unset EDITOR to simulate missing environment variable
	t.Setenv("EDITOR", "")

	result := LaunchEditor("/some/path/postactivate")
	if result.Error == nil {
		t.Fatal("expected error when EDITOR is not set")
	}
	if result.Error != ErrNoEditor {
		t.Errorf("expected ErrNoEditor, got: %v", result.Error)
	}
	if result.FileModified {
		t.Error("expected FileModified to be false")
	}
}

func TestLaunchEditor_FileNotFound(t *testing.T) {
	t.Setenv("EDITOR", "cat")

	nonExistentPath := filepath.Join(t.TempDir(), "nonexistent", "postactivate")
	result := LaunchEditor(nonExistentPath)
	if result.Error == nil {
		t.Fatal("expected error when file does not exist")
	}
	if result.Error != ErrFileNotFound {
		t.Errorf("expected ErrFileNotFound, got: %v", result.Error)
	}
	if result.FileModified {
		t.Error("expected FileModified to be false")
	}
}

func TestLaunchEditor_EditorNotFound(t *testing.T) {
	// Use a non-existent editor command
	t.Setenv("EDITOR", "nonexistent-editor-binary-xyz123")

	// Create a temporary postactivate file
	tmpDir := t.TempDir()
	postactivatePath := filepath.Join(tmpDir, "postactivate")
	if err := os.WriteFile(postactivatePath, []byte("export FOO=bar\n"), 0644); err != nil {
		t.Fatalf("failed to create temp file: %v", err)
	}

	result := LaunchEditor(postactivatePath)
	if result.Error == nil {
		t.Fatal("expected error when editor command is not found")
	}
	if !containsError(result.Error, ErrEditorNotFound) {
		t.Errorf("expected ErrEditorNotFound, got: %v", result.Error)
	}
}

func TestLaunchEditor_FileNotModified(t *testing.T) {
	// Use 'true' command which exits immediately without modifying anything
	t.Setenv("EDITOR", "true")

	tmpDir := t.TempDir()
	postactivatePath := filepath.Join(tmpDir, "postactivate")
	if err := os.WriteFile(postactivatePath, []byte("export FOO=bar\n"), 0644); err != nil {
		t.Fatalf("failed to create temp file: %v", err)
	}

	result := LaunchEditor(postactivatePath)
	if result.Error != nil {
		t.Fatalf("unexpected error: %v", result.Error)
	}
	if result.FileModified {
		t.Error("expected FileModified to be false when file is unchanged")
	}
}

func TestLaunchEditor_FileModified(t *testing.T) {
	// Create a script that modifies the file
	tmpDir := t.TempDir()
	postactivatePath := filepath.Join(tmpDir, "postactivate")
	if err := os.WriteFile(postactivatePath, []byte("export FOO=bar\n"), 0644); err != nil {
		t.Fatalf("failed to create temp file: %v", err)
	}

	// Set the mtime to the past so that writing the file will show a difference
	pastTime := time.Now().Add(-10 * time.Second)
	if err := os.Chtimes(postactivatePath, pastTime, pastTime); err != nil {
		t.Fatalf("failed to set file mtime: %v", err)
	}

	// Use a shell command that appends to the file, changing its mtime
	scriptPath := filepath.Join(tmpDir, "modify_editor.sh")
	scriptContent := "#!/bin/sh\necho 'export BAZ=qux' >> \"$1\"\n"
	if err := os.WriteFile(scriptPath, []byte(scriptContent), 0755); err != nil {
		t.Fatalf("failed to create editor script: %v", err)
	}

	t.Setenv("EDITOR", scriptPath)

	result := LaunchEditor(postactivatePath)
	if result.Error != nil {
		t.Fatalf("unexpected error: %v", result.Error)
	}
	if !result.FileModified {
		t.Error("expected FileModified to be true when file was changed")
	}
}

func TestGetMtime_ExistingFile(t *testing.T) {
	tmpDir := t.TempDir()
	path := filepath.Join(tmpDir, "testfile")
	if err := os.WriteFile(path, []byte("hello"), 0644); err != nil {
		t.Fatalf("failed to create temp file: %v", err)
	}

	mtime := GetMtime(path)
	if mtime == nil {
		t.Fatal("expected non-nil mtime for existing file")
	}
	if mtime.IsZero() {
		t.Error("expected non-zero mtime")
	}
}

func TestGetMtime_NonExistentFile(t *testing.T) {
	mtime := GetMtime("/nonexistent/path/file")
	if mtime != nil {
		t.Error("expected nil mtime for non-existent file")
	}
}

// containsError checks whether the error wraps the target error.
func containsError(err, target error) bool {
	if err == nil {
		return false
	}
	// Check if err contains the target error message
	return err.Error() != "" && target.Error() != "" &&
		len(err.Error()) >= len(target.Error()) &&
		err.Error()[:len(target.Error())] == target.Error()
}
