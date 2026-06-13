package tui

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/virtualenv-scraper/virtualenv-viewer/internal/analyzer"
	"github.com/virtualenv-scraper/virtualenv-viewer/internal/config"
	"github.com/virtualenv-scraper/virtualenv-viewer/internal/options"
)

func ptrStr(s string) *string { return &s }

func defaultOpts() options.AppOptions {
	return options.AppOptions{RestartOnEdit: false}
}

func makeTestConfigs() config.ConfigFiles {
	return config.ConfigFiles{
		PyvenvCfg:        ptrStr("home = /usr/bin\nversion = 3.11.5"),
		Postactivate:     ptrStr("export FOO=bar\nalias ll='ls -la'"),
		PostactivatePath: "/tmp/test-venv/bin/postactivate",
	}
}

func makeTestExports() analyzer.ShellExports {
	return analyzer.ShellExports{
		Variables: []analyzer.ShellVariable{
			{Name: "FOO", Value: "bar"},
			{Name: "PATH", Value: "$HOME/bin:$PATH"},
		},
		Aliases: []analyzer.ShellAlias{
			{Name: "ll", Definition: "ls -la"},
		},
		Functions: []analyzer.ShellFunction{
			{Name: "greet", Body: "  echo hello"},
		},
	}
}

func TestRenderContent_IncludesAllSections(t *testing.T) {
	configs := makeTestConfigs()
	exports := makeTestExports()

	lines := renderContent(configs, exports)
	content := strings.Join(lines, "\n")

	// Check section headers
	if !strings.Contains(content, "═══ pyvenv.cfg ═══") {
		t.Error("expected pyvenv.cfg header")
	}
	if !strings.Contains(content, "═══ postactivate (raw) ═══") {
		t.Error("expected postactivate header")
	}
	if !strings.Contains(content, "═══ Shell Exports ═══") {
		t.Error("expected Shell Exports header")
	}

	// Check content from pyvenv.cfg
	if !strings.Contains(content, "home = /usr/bin") {
		t.Error("expected pyvenv.cfg content")
	}

	// Check content from postactivate
	if !strings.Contains(content, "export FOO=bar") {
		t.Error("expected postactivate content")
	}

	// Check parsed exports
	if !strings.Contains(content, "FOO = bar") {
		t.Error("expected variable export")
	}
	if !strings.Contains(content, "ll = ls -la") {
		t.Error("expected alias")
	}
	if !strings.Contains(content, "greet()") {
		t.Error("expected function name")
	}
}

func TestRenderContent_MissingFiles(t *testing.T) {
	configs := config.ConfigFiles{
		PyvenvCfg:        nil,
		Postactivate:     nil,
		PostactivatePath: "/tmp/venv/bin/postactivate",
	}
	exports := analyzer.ShellExports{}

	lines := renderContent(configs, exports)
	content := strings.Join(lines, "\n")

	if !strings.Contains(content, "(file not found or unreadable)") {
		t.Error("expected missing file message")
	}
	if !strings.Contains(content, "(none)") {
		t.Error("expected (none) for empty exports")
	}
}

func TestModel_Recalculate_PageSize(t *testing.T) {
	m := NewModel(makeTestConfigs(), makeTestExports(), "test-venv", "/tmp/test-venv", defaultOpts())
	m.height = 22
	m.width = 80
	m.recalculate()

	if m.pageSize != 20 {
		t.Errorf("expected pageSize=20, got %d", m.pageSize)
	}
}

func TestModel_Recalculate_TotalPages(t *testing.T) {
	m := NewModel(makeTestConfigs(), makeTestExports(), "test-venv", "/tmp/test-venv", defaultOpts())
	m.height = 12 // pageSize = 10
	m.width = 80
	m.recalculate()

	expectedPageSize := 10
	if m.pageSize != expectedPageSize {
		t.Errorf("expected pageSize=%d, got %d", expectedPageSize, m.pageSize)
	}

	totalLines := len(m.contentLines)
	expectedPages := (totalLines + expectedPageSize - 1) / expectedPageSize
	if m.totalPages != expectedPages {
		t.Errorf("expected totalPages=%d, got %d (totalLines=%d)", expectedPages, m.totalPages, totalLines)
	}
}

func TestModel_NavigationBounds(t *testing.T) {
	m := NewModel(makeTestConfigs(), makeTestExports(), "test-venv", "/tmp/test-venv", defaultOpts())
	// Simulate window size
	m.height = 7 // pageSize = 5, forces multiple pages
	m.width = 80
	m.ready = true
	m.recalculate()

	if m.totalPages < 2 {
		t.Fatalf("need at least 2 pages for this test, got %d", m.totalPages)
	}

	// Test: pressing up on first page stays on first page
	if m.currentPage != 1 {
		t.Fatalf("expected to start on page 1, got %d", m.currentPage)
	}
	result, _ := m.Update(tea.KeyMsg{Type: tea.KeyUp})
	m = result.(Model)
	if m.currentPage != 1 {
		t.Errorf("expected page 1 after up on first page, got %d", m.currentPage)
	}

	// Test: pressing down advances page
	result, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = result.(Model)
	if m.currentPage != 2 {
		t.Errorf("expected page 2 after down, got %d", m.currentPage)
	}

	// Test: navigate to last page
	for m.currentPage < m.totalPages {
		result, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
		m = result.(Model)
	}
	lastPage := m.currentPage

	// Test: pressing down on last page stays on last page
	result, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = result.(Model)
	if m.currentPage != lastPage {
		t.Errorf("expected page %d after down on last page, got %d", lastPage, m.currentPage)
	}
}

func TestModel_WindowResize(t *testing.T) {
	m := NewModel(makeTestConfigs(), makeTestExports(), "test-venv", "/tmp/test-venv", defaultOpts())

	// Simulate initial window size
	result, _ := m.Update(tea.WindowSizeMsg{Width: 80, Height: 20})
	m = result.(Model)

	if m.pageSize != 18 {
		t.Errorf("expected pageSize=18, got %d", m.pageSize)
	}

	// Simulate resize
	result, _ = m.Update(tea.WindowSizeMsg{Width: 80, Height: 10})
	m = result.(Model)

	if m.pageSize != 8 {
		t.Errorf("expected pageSize=8 after resize, got %d", m.pageSize)
	}

	// Ensure currentPage is clamped after resize
	if m.currentPage < 1 || m.currentPage > m.totalPages {
		t.Errorf("currentPage %d out of bounds [1, %d]", m.currentPage, m.totalPages)
	}
}

func TestModel_QuitCommand(t *testing.T) {
	m := NewModel(makeTestConfigs(), makeTestExports(), "test-venv", "/tmp/test-venv", defaultOpts())
	m.height = 20
	m.width = 80
	m.ready = true
	m.recalculate()

	_, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'q'}})
	if cmd == nil {
		t.Error("expected quit command, got nil")
	}
}

func TestModel_View_ContainsStatusBar(t *testing.T) {
	m := NewModel(makeTestConfigs(), makeTestExports(), "my-venv", "/tmp/my-venv", defaultOpts())
	// Simulate window size
	result, _ := m.Update(tea.WindowSizeMsg{Width: 80, Height: 20})
	m = result.(Model)

	view := m.View()

	if !strings.Contains(view, "Status: my-venv") {
		t.Error("expected status bar with venv name")
	}
	if !strings.Contains(view, "Page 1/") {
		t.Error("expected page indicator")
	}
	if !strings.Contains(view, "Keys: ↑/↓ navigate | e edit | q quit") {
		t.Error("expected key hints")
	}
}

func TestModel_MinimalHeight(t *testing.T) {
	m := NewModel(makeTestConfigs(), makeTestExports(), "test-venv", "/tmp/test-venv", defaultOpts())
	m.height = 2 // Very small terminal
	m.width = 80
	m.recalculate()

	// pageSize should be at minimum 1 for height < 3
	if m.pageSize < 1 {
		t.Errorf("expected pageSize >= 1, got %d", m.pageSize)
	}
}
