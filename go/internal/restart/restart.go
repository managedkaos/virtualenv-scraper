// Package restart handles deactivation and reactivation of the active
// Python virtual environment after the postactivate file has been modified.
//
// Note: Because the viewer runs as a child process, executing deactivate/activate
// in a subshell does not modify the parent shell's environment. The restart
// handler executes the sequence and reports success or failure; changes will
// be reflected on the user's next shell command.
package restart

import (
	"fmt"
	"os/exec"
	"path/filepath"
)

// Result describes the outcome of a virtualenv restart attempt.
type Result struct {
	Success bool
	Message string
}

// RestartVirtualenv deactivates and reactivates the virtualenv located at
// venvPath by running `deactivate && source <venvPath>/bin/activate` in a
// bash subshell.
//
// Returns a Result with a confirmation message on success or an error message
// on failure. On failure the virtualenv is left in its deactivated state.
func RestartVirtualenv(venvPath string) Result {
	activatePath := filepath.Join(venvPath, "bin", "activate")

	// Build the deactivate && source activate command to run in a subshell.
	shellCmd := fmt.Sprintf("deactivate 2>/dev/null; source %q", activatePath)

	cmd := exec.Command("bash", "-c", shellCmd)
	output, err := cmd.CombinedOutput()
	if err != nil {
		errMsg := fmt.Sprintf("Virtualenv restart failed: %s", err.Error())
		if len(output) > 0 {
			errMsg = fmt.Sprintf("Virtualenv restart failed: %s", string(output))
		}
		return Result{
			Success: false,
			Message: errMsg,
		}
	}

	return Result{
		Success: true,
		Message: fmt.Sprintf("Virtualenv restarted successfully (%s)", filepath.Base(venvPath)),
	}
}
