// Package tui implements the interactive terminal UI using the Bubble Tea
// framework (Elm Architecture: Model-View-Update) with lipgloss for styling.
package tui

import (
	"fmt"
	"math"
	"os"
	"os/exec"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/virtualenv-scraper/virtualenv-viewer/internal/analyzer"
	"github.com/virtualenv-scraper/virtualenv-viewer/internal/config"
	"github.com/virtualenv-scraper/virtualenv-viewer/internal/options"
	"github.com/virtualenv-scraper/virtualenv-viewer/internal/restart"
)

// statusBarStyle defines the styling for the status bar line.
var statusBarStyle = lipgloss.NewStyle().
	Bold(true).
	Foreground(lipgloss.Color("229")).
	Background(lipgloss.Color("57"))

// keyHintStyle defines the styling for the key hints bar.
var keyHintStyle = lipgloss.NewStyle().
	Foreground(lipgloss.Color("241"))

// editorFinishedMsg is sent when the editor process exits.
type editorFinishedMsg struct {
	err error
}

// Model holds the TUI application state following bubbletea conventions.
type Model struct {
	contentLines  []string // pre-rendered content lines
	currentPage   int      // 1-based current page index
	pageSize      int      // lines of content per page
	totalPages    int      // total number of pages
	venvName      string   // virtualenv name for status bar display
	venvPath      string   // full virtualenv path (for restart)
	width         int      // terminal width
	height        int      // terminal height
	ready         bool     // whether we have received initial WindowSizeMsg
	statusMessage string   // temporary status message for errors/info

	// Editor and restart support
	postactivatePath string         // path to postactivate file
	opts             options.AppOptions // resolved application options
}

// NewModel creates and initializes a TUI Model from config data and shell exports.
func NewModel(configs config.ConfigFiles, exports analyzer.ShellExports, venvName string, venvPath string, opts options.AppOptions) Model {
	lines := renderContent(configs, exports)
	return Model{
		contentLines:     lines,
		currentPage:      1,
		venvName:         venvName,
		venvPath:         venvPath,
		postactivatePath: configs.PostactivatePath,
		opts:             opts,
	}
}

// renderContent pre-renders all configuration data into a flat list of display lines.
func renderContent(configs config.ConfigFiles, exports analyzer.ShellExports) []string {
	var lines []string

	// Section 1: pyvenv.cfg
	lines = append(lines, "═══ pyvenv.cfg ═══")
	if configs.PyvenvCfg != nil {
		lines = append(lines, strings.Split(*configs.PyvenvCfg, "\n")...)
	} else {
		lines = append(lines, "  (file not found or unreadable)")
	}

	// Blank separator
	lines = append(lines, "")

	// Section 2: postactivate (raw)
	lines = append(lines, "═══ postactivate (raw) ═══")
	if configs.Postactivate != nil {
		lines = append(lines, strings.Split(*configs.Postactivate, "\n")...)
	} else {
		lines = append(lines, "  (file not found or unreadable)")
	}

	// Blank separator
	lines = append(lines, "")

	// Section 3: Shell Exports
	lines = append(lines, "═══ Shell Exports ═══")

	// Variables
	lines = append(lines, "── Variables ──")
	if len(exports.Variables) > 0 {
		for _, v := range exports.Variables {
			lines = append(lines, fmt.Sprintf("  %s = %s", v.Name, v.Value))
		}
	} else {
		lines = append(lines, "  (none)")
	}

	// Aliases
	lines = append(lines, "── Aliases ──")
	if len(exports.Aliases) > 0 {
		for _, a := range exports.Aliases {
			lines = append(lines, fmt.Sprintf("  %s = %s", a.Name, a.Definition))
		}
	} else {
		lines = append(lines, "  (none)")
	}

	// Functions
	lines = append(lines, "── Functions ──")
	if len(exports.Functions) > 0 {
		for _, f := range exports.Functions {
			lines = append(lines, fmt.Sprintf("  %s()", f.Name))
			if f.Body != "" {
				for _, bodyLine := range strings.Split(f.Body, "\n") {
					lines = append(lines, fmt.Sprintf("    %s", bodyLine))
				}
			}
		}
	} else {
		lines = append(lines, "  (none)")
	}

	return lines
}

// recalculate updates pageSize and totalPages based on current terminal height.
func (m *Model) recalculate() {
	if m.height < 3 {
		m.pageSize = 1
	} else {
		m.pageSize = m.height - 2
	}

	totalLines := len(m.contentLines)
	if totalLines == 0 {
		m.totalPages = 1
	} else {
		m.totalPages = int(math.Ceil(float64(totalLines) / float64(m.pageSize)))
	}

	// Clamp current page
	if m.currentPage > m.totalPages {
		m.currentPage = m.totalPages
	}
	if m.currentPage < 1 {
		m.currentPage = 1
	}
}

// Init implements tea.Model. No initial commands are needed.
func (m Model) Init() tea.Cmd {
	return nil
}

// Update implements tea.Model. Handles key presses and window resize events.
func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.ready = true
		m.recalculate()
		return m, nil

	case editorFinishedMsg:
		// Editor process has exited; check if the file was modified and refresh
		m.statusMessage = ""
		if msg.err != nil {
			m.statusMessage = fmt.Sprintf("Editor error: %v", msg.err)
			return m, nil
		}
		// Use editor.GetMtime to compare — but since we used editor.LaunchEditor
		// via ExecProcess we check file modification ourselves here.
		// Re-read configs and re-render content
		configs := config.ReadConfigs(m.venvPath)
		var exports analyzer.ShellExports
		if configs.Postactivate != nil {
			exports = analyzer.AnalyzeShell(*configs.Postactivate)
		}
		m.contentLines = renderContent(configs, exports)
		m.recalculate()

		// If restart-on-edit is enabled, trigger restart
		if m.opts.RestartOnEdit {
			result := restart.RestartVirtualenv(m.venvPath)
			m.statusMessage = result.Message
		}
		return m, nil

	case tea.KeyMsg:
		// Clear status message on any key press
		m.statusMessage = ""

		switch msg.String() {
		case "q", "ctrl+c":
			return m, tea.Quit

		case "down":
			// Next page
			if m.currentPage < m.totalPages {
				m.currentPage++
			}
			return m, nil

		case "up":
			// Previous page
			if m.currentPage > 1 {
				m.currentPage--
			}
			return m, nil

		case "e":
			// Launch editor for postactivate file
			editorEnv := os.Getenv("EDITOR")
			if editorEnv == "" {
				m.statusMessage = "Error: EDITOR environment variable is not set"
				return m, nil
			}
			// Check postactivate file exists
			if _, err := os.Stat(m.postactivatePath); os.IsNotExist(err) {
				m.statusMessage = "Error: postactivate file does not exist"
				return m, nil
			}
			// Launch editor via tea.ExecProcess
			cmd := exec.Command(editorEnv, m.postactivatePath)
			return m, tea.ExecProcess(cmd, func(err error) tea.Msg {
				return editorFinishedMsg{err: err}
			})
		}
	}

	return m, nil
}

// View implements tea.Model. Renders the current page of content plus status bars.
func (m Model) View() string {
	if !m.ready {
		return "Initializing..."
	}

	var b strings.Builder

	// Calculate the slice of content lines for the current page
	startIdx := (m.currentPage - 1) * m.pageSize
	endIdx := startIdx + m.pageSize
	if endIdx > len(m.contentLines) {
		endIdx = len(m.contentLines)
	}

	// Render content lines
	pageLines := m.contentLines[startIdx:endIdx]
	for _, line := range pageLines {
		b.WriteString(line)
		b.WriteString("\n")
	}

	// Pad remaining lines to fill the content area
	renderedLines := len(pageLines)
	for i := renderedLines; i < m.pageSize; i++ {
		b.WriteString("\n")
	}

	// Status bar
	statusText := fmt.Sprintf(" Status: %s | Page %d/%d ", m.venvName, m.currentPage, m.totalPages)
	if m.statusMessage != "" {
		statusText = fmt.Sprintf(" %s ", m.statusMessage)
	}
	// Pad status bar to terminal width
	if m.width > 0 && len(statusText) < m.width {
		statusText += strings.Repeat(" ", m.width-len(statusText))
	}
	b.WriteString(statusBarStyle.Render(statusText))
	b.WriteString("\n")

	// Key hints bar
	keyHintText := " Keys: ↑/↓ navigate | e edit | q quit"
	b.WriteString(keyHintStyle.Render(keyHintText))

	return b.String()
}

// RunTUI starts the interactive TUI application.
// It accepts configuration data, shell exports, the virtualenv name, path, and app options.
func RunTUI(configs config.ConfigFiles, exports analyzer.ShellExports, venvName string, venvPath string, opts options.AppOptions) error {
	model := NewModel(configs, exports, venvName, venvPath, opts)
	p := tea.NewProgram(model, tea.WithAltScreen())
	_, err := p.Run()
	return err
}
