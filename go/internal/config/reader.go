// Package config reads virtualenv configuration files.
package config

import (
	"os"
	"path/filepath"
	"time"
)

// ConfigFiles holds the raw contents of virtualenv configuration files.
// Fields are nil when the corresponding file is missing or unreadable.
type ConfigFiles struct {
	PyvenvCfg         *string    // raw text of pyvenv.cfg, or nil if unreadable
	Postactivate      *string    // raw text of postactivate, or nil if unreadable
	PostactivatePath  string     // expected path to the postactivate file (for editor)
	PostactivateMtime *time.Time // modification time of postactivate if file exists
}

// ReadConfigs reads the virtualenv configuration files from the given path.
// Missing or unreadable files are silently skipped (returned as nil).
func ReadConfigs(venvPath string) ConfigFiles {
	postactivatePath := filepath.Join(venvPath, "bin", "postactivate")

	cfg := ConfigFiles{
		PostactivatePath: postactivatePath,
	}

	// Read pyvenv.cfg
	pyvenvCfgPath := filepath.Join(venvPath, "pyvenv.cfg")
	if data, err := os.ReadFile(pyvenvCfgPath); err == nil {
		content := string(data)
		cfg.PyvenvCfg = &content
	}

	// Read postactivate
	if data, err := os.ReadFile(postactivatePath); err == nil {
		content := string(data)
		cfg.Postactivate = &content

		// Get modification time
		if info, err := os.Stat(postactivatePath); err == nil {
			mtime := info.ModTime()
			cfg.PostactivateMtime = &mtime
		}
	}

	return cfg
}
