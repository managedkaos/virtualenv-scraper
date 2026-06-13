// Package detector locates the active Python virtual environment
// using a prioritized detection strategy.
package detector

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
)

// ErrVirtualEnvInvalid is returned when VIRTUAL_ENV is set but does not point
// to a valid virtualenv directory.
var ErrVirtualEnvInvalid = errors.New("VIRTUAL_ENV is set but not a valid virtualenv")

// ErrNoVirtualenvFound is returned when no valid virtualenv directory is found
// after exhausting all detection strategies.
var ErrNoVirtualenvFound = errors.New("no valid virtualenv found")

// isValidVirtualenv checks if a directory is a valid virtualenv by verifying
// that a pyvenv.cfg file exists at its root.
func isValidVirtualenv(path string) bool {
	info, err := os.Stat(filepath.Join(path, "pyvenv.cfg"))
	if err != nil {
		return false
	}
	return !info.IsDir()
}

// DetectVirtualenv detects the active virtualenv using a prioritized search strategy.
//
// Priority order:
//  1. $VIRTUAL_ENV environment variable
//  2. $PWD/.env
//  3. $PWD/.venv
//  4. $PWD/venv
//  5. $PWD/env
//
// Returns the absolute path to the first valid virtualenv found.
//
// If VIRTUAL_ENV is set but invalid, returns a specific error.
// If no virtualenv is found after all candidates, returns an error listing
// all attempted paths.
func DetectVirtualenv() (string, error) {
	// Check $VIRTUAL_ENV first
	virtualEnv := os.Getenv("VIRTUAL_ENV")
	if virtualEnv != "" {
		if isValidVirtualenv(virtualEnv) {
			return virtualEnv, nil
		}
		// VIRTUAL_ENV is set but invalid — specific error message
		return "", fmt.Errorf(
			"%w: '%s' is not a valid virtualenv directory",
			ErrVirtualEnvInvalid,
			virtualEnv,
		)
	}

	// Candidate directories relative to CWD
	cwd, err := os.Getwd()
	if err != nil {
		return "", fmt.Errorf("failed to get current working directory: %w", err)
	}

	candidates := []string{
		filepath.Join(cwd, ".env"),
		filepath.Join(cwd, ".venv"),
		filepath.Join(cwd, "venv"),
		filepath.Join(cwd, "env"),
	}

	for _, candidate := range candidates {
		if isValidVirtualenv(candidate) {
			return candidate, nil
		}
	}

	// No valid virtualenv found — error with attempted paths
	msg := "no valid virtualenv found. Attempted the following paths:"
	for _, c := range candidates {
		msg += "\n  " + c
	}
	return "", fmt.Errorf("%w: %s", ErrNoVirtualenvFound, msg)
}
