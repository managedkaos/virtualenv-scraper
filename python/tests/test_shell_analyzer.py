"""Unit and property-based tests for the shell analyzer module."""

from hypothesis import given, settings
from hypothesis import strategies as st

from virtualenv_viewer.shell_analyzer import (
    ShellExports,
    analyze_shell,
)

# ─────────────────────────────────────────────────────────────────────────────
# Strategies for property-based tests
# ─────────────────────────────────────────────────────────────────────────────

# Valid shell identifier: starts with letter/underscore, followed by letters/digits/underscores
_shell_var_name = st.from_regex(r"[A-Za-z_][A-Za-z0-9_]{0,15}", fullmatch=True)

# Alias names can also contain hyphens
_shell_alias_name = st.from_regex(r"[A-Za-z_][A-Za-z0-9_\-]{0,15}", fullmatch=True)

# Function names (same as variable names)
_shell_func_name = st.from_regex(r"[A-Za-z_][A-Za-z0-9_]{0,15}", fullmatch=True)

# Values that don't contain newlines or quotes (simple unquoted values)
_simple_value = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "S"),
        whitelist_characters="_-/.,:;+=@!%^&*~",
        blacklist_characters="'\"\n\r{}()` \t#$\\",
    ),
    min_size=1,
    max_size=30,
)

# Values that can contain spaces and special chars (to be used with quoting)
_quoted_value = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "S"),
        whitelist_characters="_-/.,:;+=@!%^&* \t~",
        blacklist_characters="'\"\n\r{}()`#$\\",
    ),
    min_size=1,
    max_size=30,
)

# Values containing shell variable references (for literal preservation test)
_var_ref_value = st.one_of(
    st.builds(lambda name, rest: f"${name}/{rest}", _shell_var_name, _simple_value),
    st.builds(lambda name, rest: f"${{{name}}}/{rest}", _shell_var_name, _simple_value),
    st.builds(lambda name: f"$HOME/bin:${name}", _shell_var_name),
)

# Simple function body (single line, no braces)
_simple_func_body = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        whitelist_characters="_-/.,:;+=@!%^&* \t~()\"'$",
        blacklist_characters="{}\n\r\\`",
    ),
    min_size=1,
    max_size=40,
)


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests: Export Statements
# ─────────────────────────────────────────────────────────────────────────────


class TestExportParsing:
    """Tests for parsing export statements (Req 3.1)."""

    def test_simple_unquoted_export(self) -> None:
        result = analyze_shell("export MY_VAR=hello")
        assert len(result.variables) == 1
        assert result.variables[0].name == "MY_VAR"
        assert result.variables[0].value == "hello"

    def test_double_quoted_export(self) -> None:
        result = analyze_shell('export MY_VAR="hello world"')
        assert len(result.variables) == 1
        assert result.variables[0].name == "MY_VAR"
        assert result.variables[0].value == "hello world"

    def test_single_quoted_export(self) -> None:
        result = analyze_shell("export MY_VAR='hello world'")
        assert len(result.variables) == 1
        assert result.variables[0].name == "MY_VAR"
        assert result.variables[0].value == "hello world"

    def test_export_with_path_value(self) -> None:
        result = analyze_shell("export PATH=/usr/local/bin:/usr/bin")
        assert result.variables[0].value == "/usr/local/bin:/usr/bin"

    def test_export_with_equals_in_value(self) -> None:
        result = analyze_shell("export OPTS=--flag=value")
        assert result.variables[0].value == "--flag=value"

    def test_multiple_exports(self) -> None:
        script = "export FOO=bar\nexport BAZ=qux\n"
        result = analyze_shell(script)
        assert len(result.variables) == 2
        names = {v.name for v in result.variables}
        assert names == {"FOO", "BAZ"}

    def test_export_with_underscore_name(self) -> None:
        result = analyze_shell("export _PRIVATE=secret")
        assert result.variables[0].name == "_PRIVATE"

    def test_export_with_numbers_in_name(self) -> None:
        result = analyze_shell("export VAR123=value")
        assert result.variables[0].name == "VAR123"

    def test_export_empty_value(self) -> None:
        result = analyze_shell('export EMPTY=""')
        assert result.variables[0].name == "EMPTY"
        assert result.variables[0].value == ""


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests: Alias Statements
# ─────────────────────────────────────────────────────────────────────────────


class TestAliasParsing:
    """Tests for parsing alias statements (Req 3.2)."""

    def test_simple_unquoted_alias(self) -> None:
        result = analyze_shell("alias ll=ls")
        assert len(result.aliases) == 1
        assert result.aliases[0].name == "ll"
        assert result.aliases[0].definition == "ls"

    def test_double_quoted_alias(self) -> None:
        result = analyze_shell('alias ll="ls -la"')
        assert len(result.aliases) == 1
        assert result.aliases[0].name == "ll"
        assert result.aliases[0].definition == "ls -la"

    def test_single_quoted_alias(self) -> None:
        result = analyze_shell("alias ll='ls -la'")
        assert len(result.aliases) == 1
        assert result.aliases[0].definition == "ls -la"

    def test_alias_with_hyphen_in_name(self) -> None:
        result = analyze_shell("alias my-alias='echo hello'")
        assert result.aliases[0].name == "my-alias"

    def test_multiple_aliases(self) -> None:
        script = "alias gs='git status'\nalias gp='git push'\n"
        result = analyze_shell(script)
        assert len(result.aliases) == 2

    def test_alias_with_complex_command(self) -> None:
        result = analyze_shell("alias deploy='docker compose up -d'")
        assert result.aliases[0].definition == "docker compose up -d"


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests: Function Definitions
# ─────────────────────────────────────────────────────────────────────────────


class TestFunctionParsing:
    """Tests for parsing function definitions (Req 3.3)."""

    def test_simple_function_bash_style(self) -> None:
        script = "greet() {\n  echo hello\n}\n"
        result = analyze_shell(script)
        assert len(result.functions) == 1
        assert result.functions[0].name == "greet"
        assert "echo hello" in result.functions[0].body

    def test_function_keyword_style(self) -> None:
        script = "function greet() {\n  echo hello\n}\n"
        result = analyze_shell(script)
        assert len(result.functions) == 1
        assert result.functions[0].name == "greet"

    def test_multi_line_function_body(self) -> None:
        script = "deploy() {\n  echo building\n  make build\n  echo done\n}\n"
        result = analyze_shell(script)
        assert result.functions[0].name == "deploy"
        assert "echo building" in result.functions[0].body
        assert "make build" in result.functions[0].body
        assert "echo done" in result.functions[0].body

    def test_function_with_underscore_name(self) -> None:
        script = "_helper() {\n  echo helper\n}\n"
        result = analyze_shell(script)
        assert result.functions[0].name == "_helper"

    def test_inline_function_body(self) -> None:
        script = "greet() { echo hello; }\n"
        result = analyze_shell(script)
        assert result.functions[0].name == "greet"
        assert "echo hello;" in result.functions[0].body


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests: Last-Write-Wins (Req 3.4)
# ─────────────────────────────────────────────────────────────────────────────


class TestLastWriteWins:
    """Tests for last-write-wins behavior for duplicate definitions."""

    def test_duplicate_variable_keeps_last(self) -> None:
        script = "export FOO=first\nexport FOO=second\n"
        result = analyze_shell(script)
        assert len(result.variables) == 1
        assert result.variables[0].value == "second"

    def test_duplicate_alias_keeps_last(self) -> None:
        script = "alias ll='ls -l'\nalias ll='ls -la'\n"
        result = analyze_shell(script)
        assert len(result.aliases) == 1
        assert result.aliases[0].definition == "ls -la"

    def test_duplicate_function_keeps_last(self) -> None:
        script = "greet() {\n  echo hello\n}\ngreet() {\n  echo hi\n}\n"
        result = analyze_shell(script)
        assert len(result.functions) == 1
        assert "echo hi" in result.functions[0].body

    def test_many_duplicates_keeps_final(self) -> None:
        script = "export X=a\nexport X=b\nexport X=c\nexport X=final\n"
        result = analyze_shell(script)
        assert len(result.variables) == 1
        assert result.variables[0].value == "final"


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests: Bash and Zsh Syntax Variants (Req 3.5)
# ─────────────────────────────────────────────────────────────────────────────


class TestShellSyntaxVariants:
    """Tests for both bash and zsh syntax conventions."""

    def test_export_no_quotes(self) -> None:
        result = analyze_shell("export VAR=value")
        assert result.variables[0].value == "value"

    def test_export_double_quotes(self) -> None:
        result = analyze_shell('export VAR="value with spaces"')
        assert result.variables[0].value == "value with spaces"

    def test_export_single_quotes(self) -> None:
        result = analyze_shell("export VAR='value with spaces'")
        assert result.variables[0].value == "value with spaces"

    def test_function_with_parens_style(self) -> None:
        """Bash-style: name() { ... }"""
        script = "myfunc() {\n  echo test\n}\n"
        result = analyze_shell(script)
        assert result.functions[0].name == "myfunc"

    def test_function_with_keyword_style(self) -> None:
        """Zsh/bash-style: function name() { ... }"""
        script = "function myfunc() {\n  echo test\n}\n"
        result = analyze_shell(script)
        assert result.functions[0].name == "myfunc"

    def test_mixed_syntax_in_same_script(self) -> None:
        """Script mixing bash and zsh styles."""
        script = (
            "export PATH=/usr/bin\n"
            'export HOME_BIN="$HOME/bin"\n'
            "alias ll='ls -la'\n"
            'alias gs="git status"\n'
            "greet() {\n  echo hello\n}\n"
            "function cleanup() {\n  rm -rf /tmp/cache\n}\n"
        )
        result = analyze_shell(script)
        assert len(result.variables) == 2
        assert len(result.aliases) == 2
        assert len(result.functions) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests: Literal Value Preservation (Req 3.6)
# ─────────────────────────────────────────────────────────────────────────────


class TestLiteralValuePreservation:
    """Tests that variable references are preserved literally."""

    def test_dollar_variable_not_expanded(self) -> None:
        result = analyze_shell('export PATH="$HOME/bin:$PATH"')
        assert result.variables[0].value == "$HOME/bin:$PATH"

    def test_braced_variable_not_expanded(self) -> None:
        result = analyze_shell('export GOPATH="${HOME}/go"')
        assert result.variables[0].value == "${HOME}/go"

    def test_mixed_literal_and_variable_refs(self) -> None:
        result = analyze_shell('export LD_LIBRARY_PATH="/usr/lib:${HOME}/lib:$OTHER"')
        assert result.variables[0].value == "/usr/lib:${HOME}/lib:$OTHER"


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests: Empty Script (Req 3.7)
# ─────────────────────────────────────────────────────────────────────────────


class TestEmptyScript:
    """Tests for empty or comment-only scripts."""

    def test_empty_string(self) -> None:
        result = analyze_shell("")
        assert result.variables == []
        assert result.aliases == []
        assert result.functions == []

    def test_only_comments(self) -> None:
        script = "#!/bin/bash\n# This is a comment\n# Another comment\n"
        result = analyze_shell(script)
        assert result.variables == []
        assert result.aliases == []
        assert result.functions == []

    def test_only_whitespace(self) -> None:
        result = analyze_shell("   \n\n   \n")
        assert result.variables == []
        assert result.aliases == []
        assert result.functions == []

    def test_no_exports_returns_empty_shell_exports(self) -> None:
        """ShellExports with empty lists signals 'no shell exports detected'."""
        result = analyze_shell("echo hello\nls -la\n")
        assert result == ShellExports(variables=[], aliases=[], functions=[])


# ─────────────────────────────────────────────────────────────────────────────
# Property-Based Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestPropertyVariableExportRoundTrip:
    """Feature: virtualenv-config-viewer, Property 3: Variable Export Round-Trip

    For any set of valid shell variable names and string values (supporting
    both `export NAME=VALUE` and `export NAME="VALUE"` syntax, in both bash
    and zsh conventions), formatting them as export statements and then
    parsing with the Shell Analyzer SHALL produce an equivalent set of
    name-value pairs.

    **Validates: Requirements 3.1, 3.5**
    """

    @settings(max_examples=100)
    @given(name=_shell_var_name, value=_simple_value)
    def test_unquoted_export_round_trip(self, name: str, value: str) -> None:
        """Unquoted export round-trips through the analyzer."""
        script = f"export {name}={value}"
        result = analyze_shell(script)
        assert len(result.variables) == 1
        assert result.variables[0].name == name
        assert result.variables[0].value == value

    @settings(max_examples=100)
    @given(name=_shell_var_name, value=_quoted_value)
    def test_double_quoted_export_round_trip(self, name: str, value: str) -> None:
        """Double-quoted export round-trips through the analyzer."""
        script = f'export {name}="{value}"'
        result = analyze_shell(script)
        assert len(result.variables) == 1
        assert result.variables[0].name == name
        assert result.variables[0].value == value

    @settings(max_examples=100)
    @given(name=_shell_var_name, value=_quoted_value)
    def test_single_quoted_export_round_trip(self, name: str, value: str) -> None:
        """Single-quoted export round-trips through the analyzer."""
        script = f"export {name}='{value}'"
        result = analyze_shell(script)
        assert len(result.variables) == 1
        assert result.variables[0].name == name
        assert result.variables[0].value == value


class TestPropertyAliasExtractionRoundTrip:
    """Feature: virtualenv-config-viewer, Property 4: Alias Extraction Round-Trip

    For any set of valid alias names and definitions (supporting both
    `alias NAME=VALUE` and `alias NAME='VALUE'` syntax), formatting them
    as alias statements and then parsing with the Shell Analyzer SHALL
    produce an equivalent set of name-definition pairs.

    **Validates: Requirements 3.2, 3.5**
    """

    @settings(max_examples=100)
    @given(name=_shell_alias_name, definition=_simple_value)
    def test_unquoted_alias_round_trip(self, name: str, definition: str) -> None:
        """Unquoted alias round-trips through the analyzer."""
        script = f"alias {name}={definition}"
        result = analyze_shell(script)
        assert len(result.aliases) == 1
        assert result.aliases[0].name == name
        assert result.aliases[0].definition == definition

    @settings(max_examples=100)
    @given(name=_shell_alias_name, definition=_quoted_value)
    def test_single_quoted_alias_round_trip(self, name: str, definition: str) -> None:
        """Single-quoted alias round-trips through the analyzer."""
        script = f"alias {name}='{definition}'"
        result = analyze_shell(script)
        assert len(result.aliases) == 1
        assert result.aliases[0].name == name
        assert result.aliases[0].definition == definition

    @settings(max_examples=100)
    @given(name=_shell_alias_name, definition=_quoted_value)
    def test_double_quoted_alias_round_trip(self, name: str, definition: str) -> None:
        """Double-quoted alias round-trips through the analyzer."""
        script = f'alias {name}="{definition}"'
        result = analyze_shell(script)
        assert len(result.aliases) == 1
        assert result.aliases[0].name == name
        assert result.aliases[0].definition == definition


class TestPropertyFunctionExtractionRoundTrip:
    """Feature: virtualenv-config-viewer, Property 5: Function Extraction Round-Trip

    For any set of valid function names and bodies (supporting both
    `name() { body }` and `function name { body }` syntax), formatting
    them as function definitions and then parsing with the Shell Analyzer
    SHALL produce an equivalent set of name-body pairs.

    **Validates: Requirements 3.3, 3.5**
    """

    @settings(max_examples=100)
    @given(name=_shell_func_name, body=_simple_func_body)
    def test_bash_function_round_trip(self, name: str, body: str) -> None:
        """Bash-style function (name() { body }) round-trips."""
        script = f"{name}() {{\n  {body}\n}}"
        result = analyze_shell(script)
        assert len(result.functions) == 1
        assert result.functions[0].name == name
        assert body in result.functions[0].body

    @settings(max_examples=100)
    @given(name=_shell_func_name, body=_simple_func_body)
    def test_function_keyword_round_trip(self, name: str, body: str) -> None:
        """Keyword-style function (function name() { body }) round-trips."""
        script = f"function {name}() {{\n  {body}\n}}"
        result = analyze_shell(script)
        assert len(result.functions) == 1
        assert result.functions[0].name == name
        assert body in result.functions[0].body


class TestPropertyLastWriteWins:
    """Feature: virtualenv-config-viewer, Property 6: Last-Write-Wins

    For any shell script containing multiple definitions of the same
    variable, alias, or function name, the Shell Analyzer SHALL return only
    the value from the last definition in the script, discarding all earlier
    definitions for that name.

    **Validates: Requirements 3.4**
    """

    @settings(max_examples=100)
    @given(
        name=_shell_var_name,
        values=st.lists(_simple_value, min_size=2, max_size=5),
    )
    def test_duplicate_variables_last_wins(self, name: str, values: list[str]) -> None:
        """For duplicate variable exports, the last value wins."""
        script = "\n".join(f"export {name}={v}" for v in values)
        result = analyze_shell(script)
        assert len(result.variables) == 1
        assert result.variables[0].name == name
        assert result.variables[0].value == values[-1]

    @settings(max_examples=100)
    @given(
        name=_shell_alias_name,
        definitions=st.lists(_simple_value, min_size=2, max_size=5),
    )
    def test_duplicate_aliases_last_wins(self, name: str, definitions: list[str]) -> None:
        """For duplicate alias definitions, the last definition wins."""
        script = "\n".join(f"alias {name}={d}" for d in definitions)
        result = analyze_shell(script)
        assert len(result.aliases) == 1
        assert result.aliases[0].name == name
        assert result.aliases[0].definition == definitions[-1]

    @settings(max_examples=100)
    @given(
        name=_shell_func_name,
        bodies=st.lists(_simple_func_body, min_size=2, max_size=3),
    )
    def test_duplicate_functions_last_wins(self, name: str, bodies: list[str]) -> None:
        """For duplicate function definitions, the last body wins."""
        script = "\n".join(f"{name}() {{\n  {b}\n}}" for b in bodies)
        result = analyze_shell(script)
        assert len(result.functions) == 1
        assert result.functions[0].name == name
        assert bodies[-1] in result.functions[0].body


class TestPropertyLiteralValuePreservation:
    """Feature: virtualenv-config-viewer, Property 7: Literal Value Preservation

    For any export statement whose value contains shell variable references
    (e.g., `$HOME`, `$PATH`, `${VAR}`), the Shell Analyzer SHALL return the
    value as literal text exactly as written, without performing any variable
    expansion or substitution.

    **Validates: Requirements 3.6**
    """

    @settings(max_examples=100)
    @given(name=_shell_var_name, value=_var_ref_value)
    def test_variable_references_preserved_literally(self, name: str, value: str) -> None:
        """Variable references ($NAME, ${NAME}) are returned as literal text."""
        script = f'export {name}="{value}"'
        result = analyze_shell(script)
        assert len(result.variables) == 1
        assert result.variables[0].name == name
        assert result.variables[0].value == value

    @settings(max_examples=100)
    @given(
        name=_shell_var_name,
        ref_name=_shell_var_name,
        prefix=_simple_value,
    )
    def test_dollar_sign_never_expanded(self, name: str, ref_name: str, prefix: str) -> None:
        """The $ character in values is never interpreted."""
        dollar_value = f"{prefix}/${ref_name}"
        script = f'export {name}="{dollar_value}"'
        result = analyze_shell(script)
        assert result.variables[0].value == dollar_value
