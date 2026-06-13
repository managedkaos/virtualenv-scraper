// Package editor provides functionality to launch the user's preferred editor
// for the postactivate file and detect changes after editing.
package editor

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"time"
)

// Errors returned by the editor launcher.
var (
	ErrNoEditor       = errors.New("EDITOR environment variable is not set")
	ErrFileNotFound   = errors.New("postactivate file does not exist")
	ErrEditorNotFound = errors.New("editor command not found")
)

// Result represents the outcome of an editor launch operation.
type Result struct {
	// FileModified indicates whether the file was changed during editing.
	FileModified bool
	// Error holds any error that occurred during the launch process.
	// Non-fatal errors (displayed in status bar) are returned here.
	Error error
}

// LaunchEditor opens the postactivate file in the user's preferred editor.
//
// The function:
//  1. Checks that $EDITOR is set and non-empty
//  2. Checks that the postactivate file exists
//  3. Records the file modification timestamp
//  4. Spawns the editor process (with stdin/stdout/stderr connected to the terminal)
//  5. Waits for the editor to exit
//  6. Compares the modification timestamp to detect changes
//
// The caller is responsible for suspending/resuming the TUI (leaving and
// re-entering the alternate screen) around calls to this function.
func LaunchEditor(postactivatePath string) Result {
	// Step 1: Check EDITOR environment variable
	editor := os.Getenv("EDITOR")
	if editor == "" {
		return Result{Error: ErrNoEditor}
	}

	// Step 2: Check postactivate file exists
	info, err := os.Stat(postactivatePath)
	if err != nil {
		if os.IsNotExist(err) {
			return Result{Error: ErrFileNotFound}
		}
		return Result{Error: fmt.Errorf("cannot access postactivate file: %w", err)}
	}

	// Step 3: Record modification timestamp before editing
	mtimeBefore := info.ModTime()

	// Steps 4-6: Spawn editor and wait for exit
	cmd := exec.Command(editor, postactivatePath)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		// Check if the error is because the editor command was not found
		var execErr *exec.Error
		if errors.As(err, &execErr) {
			return Result{Error: fmt.Errorf("%w: %s", ErrEditorNotFound, editor)}
		}
		return Result{Error: fmt.Errorf("editor exited with error: %w", err)}
	}

	// Step 7: Compare modification timestamp to detect changes
	infoAfter, err := os.Stat(postactivatePath)
	if err != nil {
		// File was deleted during editing - treat as not modified
		return Result{FileModified: false}
	}

	mtimeAfter := infoAfter.ModTime()
	modified := !mtimeAfter.Equal(mtimeBefore)

	return Result{FileModified: modified}
}

// GetMtime returns the modification time of the specified file, or nil if
// the file cannot be stat'd.
func GetMtime(path string) *time.Time {
	info, err := os.Stat(path)
	if err != nil {
		return nil
	}
	mtime := info.ModTime()
	return &mtime
}
