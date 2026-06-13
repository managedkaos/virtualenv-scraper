// Package analyzer extracts exported variables, aliases, and functions
// from shell activation scripts using regex-based parsing.
package analyzer

import (
	"regexp"
	"strings"
)

// ShellVariable represents a single exported shell variable.
type ShellVariable struct {
	Name  string
	Value string // literal, unresolved text
}

// ShellAlias represents a single alias definition.
type ShellAlias struct {
	Name       string
	Definition string // everything after the =
}

// ShellFunction represents a single function definition.
type ShellFunction struct {
	Name string
	Body string // full function body between braces
}

// ShellExports holds all parsed shell exports from a script.
type ShellExports struct {
	Variables []ShellVariable
	Aliases   []ShellAlias
	Functions []ShellFunction
}

var (
	// exportRe matches: export NAME=VALUE
	exportRe = regexp.MustCompile(`^export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)`)

	// aliasRe matches: alias NAME=VALUE
	aliasRe = regexp.MustCompile(`^alias\s+([A-Za-z_][A-Za-z0-9_-]*)=(.*)`)

	// funcBashRe matches: name() { (with optional leading whitespace on the brace)
	funcBashRe = regexp.MustCompile(`^([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{`)

	// funcZshRe matches: function name() { or function name {
	funcZshRe = regexp.MustCompile(`^function\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(\)\s*)?\{`)
)

// AnalyzeShell parses the content of a shell script and extracts exported
// variables, aliases, and function definitions. It applies last-write-wins
// semantics: if a name is defined multiple times, only the final value is kept.
// Variable values are preserved as literal text without expansion.
func AnalyzeShell(content string) ShellExports {
	varMap := make(map[string]string)
	aliasMap := make(map[string]string)
	funcMap := make(map[string]string)

	// Maintain insertion order
	varOrder := []string{}
	aliasOrder := []string{}
	funcOrder := []string{}

	lines := strings.Split(content, "\n")

	for i := 0; i < len(lines); i++ {
		line := lines[i]
		trimmed := strings.TrimSpace(line)

		// Try export match
		if matches := exportRe.FindStringSubmatch(trimmed); matches != nil {
			name := matches[1]
			value := stripQuotes(matches[2])
			if _, exists := varMap[name]; !exists {
				varOrder = append(varOrder, name)
			}
			varMap[name] = value
			continue
		}

		// Try alias match
		if matches := aliasRe.FindStringSubmatch(trimmed); matches != nil {
			name := matches[1]
			definition := stripQuotes(matches[2])
			if _, exists := aliasMap[name]; !exists {
				aliasOrder = append(aliasOrder, name)
			}
			aliasMap[name] = definition
			continue
		}

		// Try function match (zsh-style first since it's more specific)
		if matches := funcZshRe.FindStringSubmatch(trimmed); matches != nil {
			name := matches[1]
			body := extractFunctionBody(lines, i)
			if _, exists := funcMap[name]; !exists {
				funcOrder = append(funcOrder, name)
			}
			funcMap[name] = body
			// Skip past the function body
			i = skipFunctionBody(lines, i)
			continue
		}

		// Try bash-style function: name() {
		if matches := funcBashRe.FindStringSubmatch(trimmed); matches != nil {
			name := matches[1]
			body := extractFunctionBody(lines, i)
			if _, exists := funcMap[name]; !exists {
				funcOrder = append(funcOrder, name)
			}
			funcMap[name] = body
			// Skip past the function body
			i = skipFunctionBody(lines, i)
			continue
		}
	}

	// Build result slices in insertion order
	exports := ShellExports{}

	for _, name := range varOrder {
		exports.Variables = append(exports.Variables, ShellVariable{
			Name:  name,
			Value: varMap[name],
		})
	}

	for _, name := range aliasOrder {
		exports.Aliases = append(exports.Aliases, ShellAlias{
			Name:       name,
			Definition: aliasMap[name],
		})
	}

	for _, name := range funcOrder {
		exports.Functions = append(exports.Functions, ShellFunction{
			Name: name,
			Body: funcMap[name],
		})
	}

	return exports
}

// stripQuotes removes surrounding single or double quotes from a value.
func stripQuotes(s string) string {
	if len(s) >= 2 {
		if (s[0] == '"' && s[len(s)-1] == '"') ||
			(s[0] == '\'' && s[len(s)-1] == '\'') {
			return s[1 : len(s)-1]
		}
	}
	return s
}

// extractFunctionBody extracts the body of a function starting at the given line index.
// It captures content between the opening { and the matching closing }.
func extractFunctionBody(lines []string, startIdx int) string {
	// Find the opening brace on the start line
	braceCount := 0
	var bodyLines []string
	started := false

	for i := startIdx; i < len(lines); i++ {
		line := lines[i]

		for _, ch := range line {
			if ch == '{' {
				braceCount++
				if !started {
					started = true
				}
			} else if ch == '}' {
				braceCount--
				if started && braceCount == 0 {
					// We found the matching closing brace
					// Collect body content (everything between outer braces)
					return extractBodyContent(lines, startIdx, i)
				}
			}
		}
	}

	// If we never found the matching brace, return what we have
	if len(bodyLines) > 0 {
		return strings.Join(bodyLines, "\n")
	}
	return ""
}

// extractBodyContent extracts the content between the opening { and closing }
// across the given line range.
func extractBodyContent(lines []string, startIdx int, endIdx int) string {
	var bodyLines []string

	for i := startIdx; i <= endIdx; i++ {
		line := lines[i]

		if i == startIdx {
			// Find the opening brace and take everything after it
			braceIdx := strings.Index(line, "{")
			if braceIdx >= 0 {
				after := line[braceIdx+1:]
				trimmed := strings.TrimSpace(after)
				if trimmed != "" && trimmed != "}" {
					bodyLines = append(bodyLines, "  "+trimmed)
				}
			}
		} else if i == endIdx {
			// Find the closing brace and take everything before it
			braceIdx := strings.LastIndex(line, "}")
			if braceIdx >= 0 {
				before := line[:braceIdx]
				trimmed := strings.TrimSpace(before)
				if trimmed != "" {
					bodyLines = append(bodyLines, "  "+trimmed)
				}
			}
		} else {
			// Middle lines - include as-is but trimmed of leading/trailing whitespace
			trimmed := strings.TrimSpace(line)
			if trimmed != "" {
				bodyLines = append(bodyLines, "  "+trimmed)
			}
		}
	}

	return strings.Join(bodyLines, "\n")
}

// skipFunctionBody advances the line index past the function body.
// Returns the index of the line containing the matching closing brace.
func skipFunctionBody(lines []string, startIdx int) int {
	braceCount := 0
	started := false

	for i := startIdx; i < len(lines); i++ {
		line := lines[i]

		for _, ch := range line {
			if ch == '{' {
				braceCount++
				started = true
			} else if ch == '}' {
				braceCount--
				if started && braceCount == 0 {
					return i
				}
			}
		}
	}

	return len(lines) - 1
}
