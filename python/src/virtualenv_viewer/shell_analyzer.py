"""Shell script analyzer for virtualenv postactivate files.

Parses exported variables, aliases, and function definitions from shell
scripts using regex-based pattern matching. Supports both bash and zsh
syntax conventions. Returns literal unresolved values (no variable expansion).
"""

import re
from dataclasses import dataclass, field


@dataclass
class ShellVariable:
    """A shell variable exported via an `export` statement.

    Attributes:
        name: The variable name.
        value: The literal, unresolved value text.
    """

    name: str
    value: str


@dataclass
class ShellAlias:
    """A shell alias definition.

    Attributes:
        name: The alias name.
        definition: Everything after the = in the alias statement.
    """

    name: str
    definition: str


@dataclass
class ShellFunction:
    """A shell function definition.

    Attributes:
        name: The function name.
        body: The full function body between braces.
    """

    name: str
    body: str


@dataclass
class ShellExports:
    """Container for all parsed shell definitions.

    Attributes:
        variables: Exported variables (name + literal value).
        aliases: Alias definitions (name + definition).
        functions: Function definitions (name + body).
    """

    variables: list[ShellVariable] = field(default_factory=list)
    aliases: list[ShellAlias] = field(default_factory=list)
    functions: list[ShellFunction] = field(default_factory=list)


# Regex patterns for shell parsing
_EXPORT_PATTERN = re.compile(r"^export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)")
_ALIAS_PATTERN = re.compile(r"^alias\s+([A-Za-z_][A-Za-z0-9_-]*)=(.*)")
_FUNCTION_PATTERN = re.compile(r"^(?:function\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{")


def _strip_quotes(value: str) -> str:
    """Strip surrounding quotes from a value if present.

    Handles single quotes, double quotes, and $'...' syntax.
    """
    if len(value) >= 2:
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            return value[1:-1]
        if value.startswith("$'") and value.endswith("'") and len(value) >= 3:
            return value[2:-1]
    return value


def _extract_function_body(lines: list[str], start_idx: int) -> tuple[str, int]:
    """Extract the function body by tracking brace nesting.

    Args:
        lines: All lines of the script.
        start_idx: The index of the line containing the opening brace.

    Returns:
        A tuple of (body_text, end_index) where end_index is the line
        index of the closing brace.
    """
    brace_depth = 0
    body_lines: list[str] = []

    for i in range(start_idx, len(lines)):
        line = lines[i]

        # Count braces in this line
        for char in line:
            if char == "{":
                brace_depth += 1
            elif char == "}":
                brace_depth -= 1

        if i == start_idx:
            # The opening line may contain content after the {
            # Find the position after the opening brace
            brace_pos = line.index("{")
            after_brace = line[brace_pos + 1 :].strip()
            if after_brace and after_brace != "}":
                body_lines.append(after_brace)
        else:
            if brace_depth <= 0:
                # This is the closing brace line — capture content before }
                closing_content = line.rstrip()
                # Find the last } that brings us to depth 0
                last_brace = closing_content.rfind("}")
                before_brace = closing_content[:last_brace].strip()
                if before_brace:
                    body_lines.append(before_brace)
            else:
                body_lines.append(line)

        if brace_depth <= 0:
            return "\n".join(body_lines), i

    # If we never found a matching close brace, return what we have
    return "\n".join(body_lines), len(lines) - 1


def analyze_shell(content: str) -> ShellExports:
    """Parse shell script content and extract exports, aliases, and functions.

    Supports both bash and zsh syntax conventions. Uses last-write-wins
    semantics for duplicate definitions of the same name. Values are returned
    as literal text without variable expansion.

    Args:
        content: The raw shell script text to analyze.

    Returns:
        A ShellExports dataclass containing parsed variables, aliases,
        and functions.
    """
    variables: dict[str, str] = {}
    aliases: dict[str, str] = {}
    functions: dict[str, str] = {}

    lines = content.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Check for function definitions first (to avoid confusing them with other patterns)
        func_match = _FUNCTION_PATTERN.match(stripped)
        if func_match:
            name = func_match.group(1)
            body, end_idx = _extract_function_body(lines, i)
            functions[name] = body
            i = end_idx + 1
            continue

        # Check for export statements
        export_match = _EXPORT_PATTERN.match(stripped)
        if export_match:
            name = export_match.group(1)
            value = _strip_quotes(export_match.group(2))
            variables[name] = value
            i += 1
            continue

        # Check for alias statements
        alias_match = _ALIAS_PATTERN.match(stripped)
        if alias_match:
            name = alias_match.group(1)
            definition = _strip_quotes(alias_match.group(2))
            aliases[name] = definition
            i += 1
            continue

        i += 1

    # Build result lists preserving last-write-wins (dict already handles this)
    return ShellExports(
        variables=[ShellVariable(name=k, value=v) for k, v in variables.items()],
        aliases=[ShellAlias(name=k, definition=v) for k, v in aliases.items()],
        functions=[ShellFunction(name=k, body=v) for k, v in functions.items()],
    )
