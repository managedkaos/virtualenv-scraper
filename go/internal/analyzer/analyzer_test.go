package analyzer

import (
	"fmt"
	"strings"
	"testing"

	"pgregory.net/rapid"
)

// --- Unit Tests ---

func TestAnalyzeShell_EmptyInput(t *testing.T) {
	result := AnalyzeShell("")
	if len(result.Variables) != 0 {
		t.Errorf("expected 0 variables, got %d", len(result.Variables))
	}
	if len(result.Aliases) != 0 {
		t.Errorf("expected 0 aliases, got %d", len(result.Aliases))
	}
	if len(result.Functions) != 0 {
		t.Errorf("expected 0 functions, got %d", len(result.Functions))
	}
}

func TestAnalyzeShell_SingleExport(t *testing.T) {
	content := `export PATH=/usr/local/bin`
	result := AnalyzeShell(content)

	if len(result.Variables) != 1 {
		t.Fatalf("expected 1 variable, got %d", len(result.Variables))
	}
	if result.Variables[0].Name != "PATH" {
		t.Errorf("expected name PATH, got %s", result.Variables[0].Name)
	}
	if result.Variables[0].Value != "/usr/local/bin" {
		t.Errorf("expected value /usr/local/bin, got %s", result.Variables[0].Value)
	}
}

func TestAnalyzeShell_QuotedExport(t *testing.T) {
	content := `export MY_VAR="hello world"`
	result := AnalyzeShell(content)

	if len(result.Variables) != 1 {
		t.Fatalf("expected 1 variable, got %d", len(result.Variables))
	}
	if result.Variables[0].Value != "hello world" {
		t.Errorf("expected value 'hello world', got '%s'", result.Variables[0].Value)
	}
}

func TestAnalyzeShell_SingleQuotedExport(t *testing.T) {
	content := `export MY_VAR='single quoted'`
	result := AnalyzeShell(content)

	if len(result.Variables) != 1 {
		t.Fatalf("expected 1 variable, got %d", len(result.Variables))
	}
	if result.Variables[0].Value != "single quoted" {
		t.Errorf("expected value 'single quoted', got '%s'", result.Variables[0].Value)
	}
}

func TestAnalyzeShell_MultipleExports(t *testing.T) {
	content := `export PATH=/usr/local/bin
export HOME=/home/user
export EDITOR=vim`
	result := AnalyzeShell(content)

	if len(result.Variables) != 3 {
		t.Fatalf("expected 3 variables, got %d", len(result.Variables))
	}
	if result.Variables[0].Name != "PATH" {
		t.Errorf("expected first var PATH, got %s", result.Variables[0].Name)
	}
	if result.Variables[1].Name != "HOME" {
		t.Errorf("expected second var HOME, got %s", result.Variables[1].Name)
	}
	if result.Variables[2].Name != "EDITOR" {
		t.Errorf("expected third var EDITOR, got %s", result.Variables[2].Name)
	}
}

func TestAnalyzeShell_SingleAlias(t *testing.T) {
	content := `alias ll='ls -la'`
	result := AnalyzeShell(content)

	if len(result.Aliases) != 1 {
		t.Fatalf("expected 1 alias, got %d", len(result.Aliases))
	}
	if result.Aliases[0].Name != "ll" {
		t.Errorf("expected alias name ll, got %s", result.Aliases[0].Name)
	}
	if result.Aliases[0].Definition != "ls -la" {
		t.Errorf("expected definition 'ls -la', got '%s'", result.Aliases[0].Definition)
	}
}

func TestAnalyzeShell_AliasWithHyphen(t *testing.T) {
	content := `alias my-alias='echo hello'`
	result := AnalyzeShell(content)

	if len(result.Aliases) != 1 {
		t.Fatalf("expected 1 alias, got %d", len(result.Aliases))
	}
	if result.Aliases[0].Name != "my-alias" {
		t.Errorf("expected alias name my-alias, got %s", result.Aliases[0].Name)
	}
}

func TestAnalyzeShell_BashFunction(t *testing.T) {
	content := `greet() {
  echo "hello"
}`
	result := AnalyzeShell(content)

	if len(result.Functions) != 1 {
		t.Fatalf("expected 1 function, got %d", len(result.Functions))
	}
	if result.Functions[0].Name != "greet" {
		t.Errorf("expected function name greet, got %s", result.Functions[0].Name)
	}
	if !strings.Contains(result.Functions[0].Body, "echo") {
		t.Errorf("expected function body to contain 'echo', got '%s'", result.Functions[0].Body)
	}
}

func TestAnalyzeShell_ZshFunction(t *testing.T) {
	content := `function greet {
  echo "hello"
}`
	result := AnalyzeShell(content)

	if len(result.Functions) != 1 {
		t.Fatalf("expected 1 function, got %d", len(result.Functions))
	}
	if result.Functions[0].Name != "greet" {
		t.Errorf("expected function name greet, got %s", result.Functions[0].Name)
	}
}

func TestAnalyzeShell_ZshFunctionWithParens(t *testing.T) {
	content := `function greet() {
  echo "hello"
}`
	result := AnalyzeShell(content)

	if len(result.Functions) != 1 {
		t.Fatalf("expected 1 function, got %d", len(result.Functions))
	}
	if result.Functions[0].Name != "greet" {
		t.Errorf("expected function name greet, got %s", result.Functions[0].Name)
	}
}

func TestAnalyzeShell_DuplicateExport_LastWriteWins(t *testing.T) {
	content := `export PATH=/first
export PATH=/second
export PATH=/third`
	result := AnalyzeShell(content)

	if len(result.Variables) != 1 {
		t.Fatalf("expected 1 variable (last-write-wins), got %d", len(result.Variables))
	}
	if result.Variables[0].Value != "/third" {
		t.Errorf("expected last value '/third', got '%s'", result.Variables[0].Value)
	}
}

func TestAnalyzeShell_DuplicateAlias_LastWriteWins(t *testing.T) {
	content := `alias ll='ls -l'
alias ll='ls -la'`
	result := AnalyzeShell(content)

	if len(result.Aliases) != 1 {
		t.Fatalf("expected 1 alias (last-write-wins), got %d", len(result.Aliases))
	}
	if result.Aliases[0].Definition != "ls -la" {
		t.Errorf("expected last definition 'ls -la', got '%s'", result.Aliases[0].Definition)
	}
}

func TestAnalyzeShell_DuplicateFunction_LastWriteWins(t *testing.T) {
	content := `greet() {
  echo "first"
}
greet() {
  echo "second"
}`
	result := AnalyzeShell(content)

	if len(result.Functions) != 1 {
		t.Fatalf("expected 1 function (last-write-wins), got %d", len(result.Functions))
	}
	if !strings.Contains(result.Functions[0].Body, "second") {
		t.Errorf("expected last function body with 'second', got '%s'", result.Functions[0].Body)
	}
}

func TestAnalyzeShell_LiteralValuePreservation(t *testing.T) {
	content := `export PATH="$HOME/bin:$PATH"
export FOO='${BAR}/baz'`
	result := AnalyzeShell(content)

	if len(result.Variables) != 2 {
		t.Fatalf("expected 2 variables, got %d", len(result.Variables))
	}
	if result.Variables[0].Value != "$HOME/bin:$PATH" {
		t.Errorf("expected literal '$HOME/bin:$PATH', got '%s'", result.Variables[0].Value)
	}
	if result.Variables[1].Value != "${BAR}/baz" {
		t.Errorf("expected literal '${BAR}/baz', got '%s'", result.Variables[1].Value)
	}
}

func TestAnalyzeShell_MixedContent(t *testing.T) {
	content := `export PATH=/usr/bin
alias ll='ls -la'
greet() {
  echo "hi"
}
export EDITOR=vim`
	result := AnalyzeShell(content)

	if len(result.Variables) != 2 {
		t.Errorf("expected 2 variables, got %d", len(result.Variables))
	}
	if len(result.Aliases) != 1 {
		t.Errorf("expected 1 alias, got %d", len(result.Aliases))
	}
	if len(result.Functions) != 1 {
		t.Errorf("expected 1 function, got %d", len(result.Functions))
	}
}

func TestAnalyzeShell_IgnoresComments(t *testing.T) {
	content := `# This is a comment
export PATH=/usr/bin
# Another comment
alias ll='ls -la'`
	result := AnalyzeShell(content)

	if len(result.Variables) != 1 {
		t.Errorf("expected 1 variable, got %d", len(result.Variables))
	}
	if len(result.Aliases) != 1 {
		t.Errorf("expected 1 alias, got %d", len(result.Aliases))
	}
}

func TestAnalyzeShell_IgnoresBlankLines(t *testing.T) {
	content := `

export PATH=/usr/bin

alias ll='ls -la'

`
	result := AnalyzeShell(content)

	if len(result.Variables) != 1 {
		t.Errorf("expected 1 variable, got %d", len(result.Variables))
	}
	if len(result.Aliases) != 1 {
		t.Errorf("expected 1 alias, got %d", len(result.Aliases))
	}
}

func TestAnalyzeShell_ExportWithUnderscore(t *testing.T) {
	content := `export MY_LONG_VAR_NAME="value"`
	result := AnalyzeShell(content)

	if len(result.Variables) != 1 {
		t.Fatalf("expected 1 variable, got %d", len(result.Variables))
	}
	if result.Variables[0].Name != "MY_LONG_VAR_NAME" {
		t.Errorf("expected name MY_LONG_VAR_NAME, got %s", result.Variables[0].Name)
	}
}

func TestAnalyzeShell_ExportWithNumbers(t *testing.T) {
	content := `export VAR123="value"`
	result := AnalyzeShell(content)

	if len(result.Variables) != 1 {
		t.Fatalf("expected 1 variable, got %d", len(result.Variables))
	}
	if result.Variables[0].Name != "VAR123" {
		t.Errorf("expected name VAR123, got %s", result.Variables[0].Name)
	}
}

func TestAnalyzeShell_MultiFunctionBody(t *testing.T) {
	content := `activate() {
  export VIRTUAL_ENV=/path/to/venv
  export PATH="$VIRTUAL_ENV/bin:$PATH"
  hash -r 2>/dev/null
}`
	result := AnalyzeShell(content)

	if len(result.Functions) != 1 {
		t.Fatalf("expected 1 function, got %d", len(result.Functions))
	}
	if result.Functions[0].Name != "activate" {
		t.Errorf("expected function name activate, got %s", result.Functions[0].Name)
	}
	// Body should contain multiple lines
	if !strings.Contains(result.Functions[0].Body, "VIRTUAL_ENV") {
		t.Errorf("expected body to contain VIRTUAL_ENV, got '%s'", result.Functions[0].Body)
	}
}

// --- Property-Based Tests ---

// validVarName generates a valid shell variable name: starts with letter or underscore,
// followed by letters, digits, or underscores.
func validVarName() *rapid.Generator[string] {
	return rapid.Custom[string](func(t *rapid.T) string {
		first := rapid.SampledFrom([]byte("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")).Draw(t, "firstChar")
		restLen := rapid.IntRange(0, 10).Draw(t, "restLen")
		rest := make([]byte, restLen)
		for i := range rest {
			rest[i] = rapid.SampledFrom([]byte("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")).Draw(t, fmt.Sprintf("restChar%d", i))
		}
		return string(first) + string(rest)
	})
}

// validAliasName generates a valid alias name: like a var name but can also contain hyphens.
func validAliasName() *rapid.Generator[string] {
	return rapid.Custom[string](func(t *rapid.T) string {
		first := rapid.SampledFrom([]byte("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")).Draw(t, "firstChar")
		restLen := rapid.IntRange(0, 10).Draw(t, "restLen")
		rest := make([]byte, restLen)
		for i := range rest {
			rest[i] = rapid.SampledFrom([]byte("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")).Draw(t, fmt.Sprintf("restChar%d", i))
		}
		return string(first) + string(rest)
	})
}

// safeValue generates a value string that doesn't contain newlines or unmatched quotes.
func safeValue() *rapid.Generator[string] {
	return rapid.Custom[string](func(t *rapid.T) string {
		// Generate a simple alphanumeric value with some safe special chars
		length := rapid.IntRange(1, 30).Draw(t, "valueLen")
		chars := make([]byte, length)
		safeChars := []byte("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/._-=+:,")
		for i := range chars {
			chars[i] = rapid.SampledFrom(safeChars).Draw(t, fmt.Sprintf("char%d", i))
		}
		return string(chars)
	})
}

// safeFuncBody generates a simple function body (no braces, no newlines).
func safeFuncBody() *rapid.Generator[string] {
	return rapid.Custom[string](func(t *rapid.T) string {
		length := rapid.IntRange(1, 20).Draw(t, "bodyLen")
		chars := make([]byte, length)
		safeChars := []byte("abcdefghijklmnopqrstuvwxyz 0123456789/._-=+:,")
		for i := range chars {
			chars[i] = rapid.SampledFrom(safeChars).Draw(t, fmt.Sprintf("char%d", i))
		}
		return string(chars)
	})
}

// Property 3: Variable Export Round-Trip
// For any set of valid shell variable names and string values, formatting them as
// export statements and then parsing with the Shell Analyzer SHALL produce an
// equivalent set of name-value pairs.
// **Validates: Requirements 3.1, 3.5**
func TestProperty3_VariableExportRoundTrip(t *testing.T) {
	// Feature: virtualenv-config-viewer, Property 3: Variable Export Round-Trip
	rapid.Check(t, func(rt *rapid.T) {
		// Generate 1-5 unique variable names with values
		count := rapid.IntRange(1, 5).Draw(rt, "varCount")
		names := make([]string, 0, count)
		values := make([]string, 0, count)
		seen := make(map[string]bool)

		for i := 0; i < count; i++ {
			name := validVarName().Draw(rt, fmt.Sprintf("name%d", i))
			if seen[name] {
				continue
			}
			seen[name] = true
			value := safeValue().Draw(rt, fmt.Sprintf("value%d", i))
			names = append(names, name)
			values = append(values, value)
		}

		if len(names) == 0 {
			return
		}

		// Use double quotes for quoting style
		useDoubleQuotes := rapid.Bool().Draw(rt, "useDoubleQuotes")

		// Build the script content
		var lines []string
		for i, name := range names {
			if useDoubleQuotes {
				lines = append(lines, fmt.Sprintf(`export %s="%s"`, name, values[i]))
			} else {
				lines = append(lines, fmt.Sprintf(`export %s=%s`, name, values[i]))
			}
		}
		content := strings.Join(lines, "\n")

		// Parse
		result := AnalyzeShell(content)

		// Verify
		if len(result.Variables) != len(names) {
			rt.Fatalf("expected %d variables, got %d\nContent:\n%s", len(names), len(result.Variables), content)
		}
		for i, name := range names {
			if result.Variables[i].Name != name {
				rt.Fatalf("expected variable name %s at index %d, got %s", name, i, result.Variables[i].Name)
			}
			if result.Variables[i].Value != values[i] {
				rt.Fatalf("expected variable value '%s' for %s, got '%s'", values[i], name, result.Variables[i].Value)
			}
		}
	})
}

// Property 4: Alias Extraction Round-Trip
// For any set of valid alias names and definitions, formatting them as alias statements
// and then parsing with the Shell Analyzer SHALL produce an equivalent set of
// name-definition pairs.
// **Validates: Requirements 3.2, 3.5**
func TestProperty4_AliasExtractionRoundTrip(t *testing.T) {
	// Feature: virtualenv-config-viewer, Property 4: Alias Extraction Round-Trip
	rapid.Check(t, func(rt *rapid.T) {
		// Generate 1-5 unique alias names with definitions
		count := rapid.IntRange(1, 5).Draw(rt, "aliasCount")
		names := make([]string, 0, count)
		defs := make([]string, 0, count)
		seen := make(map[string]bool)

		for i := 0; i < count; i++ {
			name := validAliasName().Draw(rt, fmt.Sprintf("name%d", i))
			if seen[name] {
				continue
			}
			seen[name] = true
			def := safeValue().Draw(rt, fmt.Sprintf("def%d", i))
			names = append(names, name)
			defs = append(defs, def)
		}

		if len(names) == 0 {
			return
		}

		// Use single quotes for alias quoting
		useSingleQuotes := rapid.Bool().Draw(rt, "useSingleQuotes")

		// Build the script content
		var lines []string
		for i, name := range names {
			if useSingleQuotes {
				lines = append(lines, fmt.Sprintf(`alias %s='%s'`, name, defs[i]))
			} else {
				lines = append(lines, fmt.Sprintf(`alias %s=%s`, name, defs[i]))
			}
		}
		content := strings.Join(lines, "\n")

		// Parse
		result := AnalyzeShell(content)

		// Verify
		if len(result.Aliases) != len(names) {
			rt.Fatalf("expected %d aliases, got %d\nContent:\n%s", len(names), len(result.Aliases), content)
		}
		for i, name := range names {
			if result.Aliases[i].Name != name {
				rt.Fatalf("expected alias name %s at index %d, got %s", name, i, result.Aliases[i].Name)
			}
			if result.Aliases[i].Definition != defs[i] {
				rt.Fatalf("expected alias definition '%s' for %s, got '%s'", defs[i], name, result.Aliases[i].Definition)
			}
		}
	})
}

// Property 5: Function Extraction Round-Trip
// For any set of valid function names and bodies, formatting them as function definitions
// and then parsing with the Shell Analyzer SHALL produce an equivalent set of
// name-body pairs.
// **Validates: Requirements 3.3, 3.5**
func TestProperty5_FunctionExtractionRoundTrip(t *testing.T) {
	// Feature: virtualenv-config-viewer, Property 5: Function Extraction Round-Trip
	rapid.Check(t, func(rt *rapid.T) {
		// Generate 1-3 unique function names with bodies
		count := rapid.IntRange(1, 3).Draw(rt, "funcCount")
		names := make([]string, 0, count)
		bodies := make([]string, 0, count)
		seen := make(map[string]bool)

		for i := 0; i < count; i++ {
			name := validVarName().Draw(rt, fmt.Sprintf("name%d", i))
			if seen[name] {
				continue
			}
			seen[name] = true
			body := safeFuncBody().Draw(rt, fmt.Sprintf("body%d", i))
			names = append(names, name)
			bodies = append(bodies, body)
		}

		if len(names) == 0 {
			return
		}

		// Choose bash or zsh style
		useZshStyle := rapid.Bool().Draw(rt, "useZshStyle")

		// Build the script content
		var lines []string
		for i, name := range names {
			if useZshStyle {
				lines = append(lines, fmt.Sprintf("function %s {", name))
			} else {
				lines = append(lines, fmt.Sprintf("%s() {", name))
			}
			lines = append(lines, fmt.Sprintf("  %s", bodies[i]))
			lines = append(lines, "}")
			lines = append(lines, "") // blank line separator
		}
		content := strings.Join(lines, "\n")

		// Parse
		result := AnalyzeShell(content)

		// Verify
		if len(result.Functions) != len(names) {
			rt.Fatalf("expected %d functions, got %d\nContent:\n%s", len(names), len(result.Functions), content)
		}
		for i, name := range names {
			if result.Functions[i].Name != name {
				rt.Fatalf("expected function name %s at index %d, got %s", name, i, result.Functions[i].Name)
			}
			// The body should contain the original content (trimmed/indented by the parser)
			if !strings.Contains(result.Functions[i].Body, strings.TrimSpace(bodies[i])) {
				rt.Fatalf("expected function body to contain '%s' for %s, got '%s'", bodies[i], name, result.Functions[i].Body)
			}
		}
	})
}

// Property 6: Last-Write-Wins
// For any shell script containing multiple definitions of the same variable, alias,
// or function name, the Shell Analyzer SHALL return only the value from the last
// definition in the script.
// **Validates: Requirements 3.4**
func TestProperty6_LastWriteWins(t *testing.T) {
	// Feature: virtualenv-config-viewer, Property 6: Last-Write-Wins
	rapid.Check(t, func(rt *rapid.T) {
		// Generate a variable name and multiple values
		name := validVarName().Draw(rt, "name")
		numDefs := rapid.IntRange(2, 5).Draw(rt, "numDefs")
		values := make([]string, numDefs)
		for i := range values {
			values[i] = safeValue().Draw(rt, fmt.Sprintf("value%d", i))
		}

		// Build script with multiple definitions of the same name
		var lines []string
		for _, value := range values {
			lines = append(lines, fmt.Sprintf(`export %s="%s"`, name, value))
		}
		content := strings.Join(lines, "\n")

		// Parse
		result := AnalyzeShell(content)

		// Verify: only one variable, with the last value
		if len(result.Variables) != 1 {
			rt.Fatalf("expected 1 variable (last-write-wins), got %d", len(result.Variables))
		}
		expectedValue := values[numDefs-1]
		if result.Variables[0].Value != expectedValue {
			rt.Fatalf("expected last value '%s', got '%s'", expectedValue, result.Variables[0].Value)
		}

		// Also test with aliases
		aliasName := validAliasName().Draw(rt, "aliasName")
		numAliasDefs := rapid.IntRange(2, 5).Draw(rt, "numAliasDefs")
		aliasDefs := make([]string, numAliasDefs)
		for i := range aliasDefs {
			aliasDefs[i] = safeValue().Draw(rt, fmt.Sprintf("aliasDef%d", i))
		}

		var aliasLines []string
		for _, def := range aliasDefs {
			aliasLines = append(aliasLines, fmt.Sprintf(`alias %s='%s'`, aliasName, def))
		}
		aliasContent := strings.Join(aliasLines, "\n")

		aliasResult := AnalyzeShell(aliasContent)
		if len(aliasResult.Aliases) != 1 {
			rt.Fatalf("expected 1 alias (last-write-wins), got %d", len(aliasResult.Aliases))
		}
		expectedAliasDef := aliasDefs[numAliasDefs-1]
		if aliasResult.Aliases[0].Definition != expectedAliasDef {
			rt.Fatalf("expected last alias definition '%s', got '%s'", expectedAliasDef, aliasResult.Aliases[0].Definition)
		}
	})
}

// Property 7: Literal Value Preservation
// For any export statement whose value contains shell variable references,
// the Shell Analyzer SHALL return the value as literal text without performing
// any variable expansion or substitution.
// **Validates: Requirements 3.6**
func TestProperty7_LiteralValuePreservation(t *testing.T) {
	// Feature: virtualenv-config-viewer, Property 7: Literal Value Preservation
	rapid.Check(t, func(rt *rapid.T) {
		name := validVarName().Draw(rt, "name")

		// Generate a value that contains shell variable references
		refVarName := validVarName().Draw(rt, "refVarName")

		// Choose a reference style
		refStyle := rapid.IntRange(0, 2).Draw(rt, "refStyle")
		var refExpr string
		switch refStyle {
		case 0:
			refExpr = "$" + refVarName
		case 1:
			refExpr = "${" + refVarName + "}"
		case 2:
			refExpr = "${" + refVarName + "}/suffix"
		}

		prefix := safeValue().Draw(rt, "prefix")
		literalValue := prefix + ":" + refExpr

		// Build the export statement with double quotes (so the $ is preserved literally)
		content := fmt.Sprintf(`export %s="%s"`, name, literalValue)

		// Parse
		result := AnalyzeShell(content)

		// Verify: value must be preserved literally, no expansion
		if len(result.Variables) != 1 {
			rt.Fatalf("expected 1 variable, got %d", len(result.Variables))
		}
		if result.Variables[0].Value != literalValue {
			rt.Fatalf("expected literal value '%s', got '%s' (expansion occurred!)", literalValue, result.Variables[0].Value)
		}
	})
}
