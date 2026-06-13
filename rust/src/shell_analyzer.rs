use regex::Regex;

/// A shell variable exported via `export NAME=VALUE`.
#[derive(Debug, Clone, PartialEq)]
pub struct ShellVariable {
    pub name: String,
    pub value: String,
}

/// A shell alias defined via `alias NAME=VALUE`.
#[derive(Debug, Clone, PartialEq)]
pub struct ShellAlias {
    pub name: String,
    pub definition: String,
}

/// A shell function defined via `name() { ... }` or `function name { ... }`.
#[derive(Debug, Clone, PartialEq)]
pub struct ShellFunction {
    pub name: String,
    pub body: String,
}

/// The parsed shell exports from a postactivate script.
#[derive(Debug, Clone, PartialEq)]
pub struct ShellExports {
    pub variables: Vec<ShellVariable>,
    pub aliases: Vec<ShellAlias>,
    pub functions: Vec<ShellFunction>,
}

/// Analyzes the content of a shell script and extracts exported variables,
/// aliases, and function definitions.
///
/// Uses last-write-wins semantics: if a variable, alias, or function is defined
/// multiple times, only the final definition is kept.
///
/// Variable references (e.g. `$HOME`) are preserved as literal text without expansion.
pub fn analyze_shell(content: &str) -> ShellExports {
    let mut variables = extract_variables(content);
    let mut aliases = extract_aliases(content);
    let mut functions = extract_functions(content);

    // Apply last-write-wins: deduplicate by name, keeping the last occurrence.
    dedup_last_wins(&mut variables, |v| &v.name);
    dedup_last_wins(&mut aliases, |a| &a.name);
    dedup_last_wins(&mut functions, |f| &f.name);

    ShellExports {
        variables,
        aliases,
        functions,
    }
}

/// Removes duplicates by name, keeping only the last occurrence of each name.
fn dedup_last_wins<T, F>(items: &mut Vec<T>, name_fn: F)
where
    F: Fn(&T) -> &str,
{
    let mut seen = std::collections::HashMap::new();
    // Record the last index for each name.
    for (i, item) in items.iter().enumerate() {
        seen.insert(name_fn(item).to_string(), i);
    }
    // Keep only items whose index is the last one for their name.
    let mut idx = 0;
    items.retain(|item| {
        let keep = seen[name_fn(item)] == idx;
        idx += 1;
        keep
    });
}

/// Extracts exported variables from shell script content.
fn extract_variables(content: &str) -> Vec<ShellVariable> {
    let re = Regex::new(r"(?m)^export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)$").unwrap();
    re.captures_iter(content)
        .map(|cap| {
            let name = cap[1].to_string();
            let value = strip_quotes(&cap[2]);
            ShellVariable { name, value }
        })
        .collect()
}

/// Extracts alias definitions from shell script content.
fn extract_aliases(content: &str) -> Vec<ShellAlias> {
    let re = Regex::new(r"(?m)^alias\s+([A-Za-z_][A-Za-z0-9_-]*)=(.*)$").unwrap();
    re.captures_iter(content)
        .map(|cap| {
            let name = cap[1].to_string();
            let definition = strip_quotes(&cap[2]);
            ShellAlias { name, definition }
        })
        .collect()
}

/// Extracts function definitions from shell script content.
///
/// Supports both syntaxes:
/// - `name() { ... }`
/// - `function name { ... }` (zsh style)
fn extract_functions(content: &str) -> Vec<ShellFunction> {
    let mut functions = Vec::new();
    let lines: Vec<&str> = content.lines().collect();
    let mut i = 0;

    // Pattern for `name() {` or `function name() {`
    let re_paren =
        Regex::new(r"^(?:function\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{(.*)$").unwrap();
    // Pattern for `function name {` (zsh style, no parentheses)
    let re_zsh = Regex::new(r"^function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{(.*)$").unwrap();

    while i < lines.len() {
        let line = lines[i];

        // Try paren style first, then zsh style
        let cap = re_paren.captures(line).or_else(|| re_zsh.captures(line));

        if let Some(cap) = cap {
            let name = cap[1].to_string();
            let rest_of_first_line = cap[2].trim();

            // Check if the function body and closing brace are on the same line
            if let Some(body) = single_line_body(rest_of_first_line) {
                functions.push(ShellFunction { name, body });
                i += 1;
                continue;
            }

            // Multi-line function: collect body until matching `}`
            let mut body_lines = Vec::new();
            if !rest_of_first_line.is_empty() {
                body_lines.push(rest_of_first_line.to_string());
            }
            let mut brace_depth = 1;
            i += 1;

            while i < lines.len() && brace_depth > 0 {
                let body_line = lines[i];
                // Count braces to handle nested blocks
                for ch in body_line.chars() {
                    match ch {
                        '{' => brace_depth += 1,
                        '}' => {
                            brace_depth -= 1;
                            if brace_depth == 0 {
                                break;
                            }
                        }
                        _ => {}
                    }
                }
                if brace_depth > 0 {
                    body_lines.push(body_line.to_string());
                } else {
                    // This line contains the closing brace; include any content before it
                    let trimmed = body_line.trim();
                    if trimmed != "}" {
                        // There's content before the closing brace on this line
                        if let Some(pos) = body_line.rfind('}') {
                            let before = body_line[..pos].trim();
                            if !before.is_empty() {
                                body_lines.push(before.to_string());
                            }
                        }
                    }
                }
                i += 1;
            }

            let body = body_lines
                .iter()
                .map(|l| l.trim())
                .collect::<Vec<&str>>()
                .join("\n");
            functions.push(ShellFunction { name, body });
        } else {
            i += 1;
        }
    }

    functions
}

/// Checks if a function body is complete on a single line (ends with `}`).
/// Returns the body content if it's a single-line function, None otherwise.
fn single_line_body(rest: &str) -> Option<String> {
    if let Some(stripped) = rest.strip_suffix('}') {
        let body = stripped.trim().to_string();
        Some(body)
    } else {
        None
    }
}

/// Strips surrounding quotes (single or double) from a value.
fn strip_quotes(s: &str) -> String {
    let trimmed = s.trim();
    if trimmed.len() >= 2 {
        let first = trimmed.as_bytes()[0];
        let last = trimmed.as_bytes()[trimmed.len() - 1];
        if (first == b'"' && last == b'"') || (first == b'\'' && last == b'\'') {
            return trimmed[1..trimmed.len() - 1].to_string();
        }
    }
    trimmed.to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_simple_variable() {
        let content = "export FOO=bar\n";
        let exports = analyze_shell(content);
        assert_eq!(exports.variables.len(), 1);
        assert_eq!(exports.variables[0].name, "FOO");
        assert_eq!(exports.variables[0].value, "bar");
    }

    #[test]
    fn test_extract_quoted_variable() {
        let content = "export PATH=\"/usr/local/bin:$PATH\"\n";
        let exports = analyze_shell(content);
        assert_eq!(exports.variables.len(), 1);
        assert_eq!(exports.variables[0].name, "PATH");
        assert_eq!(exports.variables[0].value, "/usr/local/bin:$PATH");
    }

    #[test]
    fn test_extract_single_quoted_variable() {
        let content = "export GREETING='hello world'\n";
        let exports = analyze_shell(content);
        assert_eq!(exports.variables.len(), 1);
        assert_eq!(exports.variables[0].name, "GREETING");
        assert_eq!(exports.variables[0].value, "hello world");
    }

    #[test]
    fn test_variable_with_dollar_reference_preserved() {
        let content = "export PATH=\"$HOME/bin:$PATH\"\n";
        let exports = analyze_shell(content);
        assert_eq!(exports.variables[0].value, "$HOME/bin:$PATH");
    }

    #[test]
    fn test_extract_simple_alias() {
        let content = "alias ll='ls -la'\n";
        let exports = analyze_shell(content);
        assert_eq!(exports.aliases.len(), 1);
        assert_eq!(exports.aliases[0].name, "ll");
        assert_eq!(exports.aliases[0].definition, "ls -la");
    }

    #[test]
    fn test_extract_alias_with_hyphen() {
        let content = "alias my-cmd=\"echo hello\"\n";
        let exports = analyze_shell(content);
        assert_eq!(exports.aliases.len(), 1);
        assert_eq!(exports.aliases[0].name, "my-cmd");
        assert_eq!(exports.aliases[0].definition, "echo hello");
    }

    #[test]
    fn test_extract_function_paren_style() {
        let content = "greet() {\n    echo hello\n}\n";
        let exports = analyze_shell(content);
        assert_eq!(exports.functions.len(), 1);
        assert_eq!(exports.functions[0].name, "greet");
        assert_eq!(exports.functions[0].body, "echo hello");
    }

    #[test]
    fn test_extract_function_with_function_keyword() {
        let content = "function greet() {\n    echo hello\n}\n";
        let exports = analyze_shell(content);
        assert_eq!(exports.functions.len(), 1);
        assert_eq!(exports.functions[0].name, "greet");
        assert_eq!(exports.functions[0].body, "echo hello");
    }

    #[test]
    fn test_extract_function_zsh_style() {
        let content = "function greet {\n    echo hello\n}\n";
        let exports = analyze_shell(content);
        assert_eq!(exports.functions.len(), 1);
        assert_eq!(exports.functions[0].name, "greet");
        assert_eq!(exports.functions[0].body, "echo hello");
    }

    #[test]
    fn test_single_line_function() {
        let content = "greet() { echo hello; }\n";
        let exports = analyze_shell(content);
        assert_eq!(exports.functions.len(), 1);
        assert_eq!(exports.functions[0].name, "greet");
        assert_eq!(exports.functions[0].body, "echo hello;");
    }

    #[test]
    fn test_last_write_wins_variables() {
        let content = "export FOO=first\nexport FOO=second\n";
        let exports = analyze_shell(content);
        assert_eq!(exports.variables.len(), 1);
        assert_eq!(exports.variables[0].value, "second");
    }

    #[test]
    fn test_last_write_wins_aliases() {
        let content = "alias ll='ls -l'\nalias ll='ls -la'\n";
        let exports = analyze_shell(content);
        assert_eq!(exports.aliases.len(), 1);
        assert_eq!(exports.aliases[0].definition, "ls -la");
    }

    #[test]
    fn test_last_write_wins_functions() {
        let content = "greet() {\n    echo hi\n}\ngreet() {\n    echo hello\n}\n";
        let exports = analyze_shell(content);
        assert_eq!(exports.functions.len(), 1);
        assert_eq!(exports.functions[0].body, "echo hello");
    }

    #[test]
    fn test_empty_content() {
        let exports = analyze_shell("");
        assert!(exports.variables.is_empty());
        assert!(exports.aliases.is_empty());
        assert!(exports.functions.is_empty());
    }

    #[test]
    fn test_no_exports_in_content() {
        let content = "# just a comment\necho hello\n";
        let exports = analyze_shell(content);
        assert!(exports.variables.is_empty());
        assert!(exports.aliases.is_empty());
        assert!(exports.functions.is_empty());
    }

    #[test]
    fn test_mixed_content() {
        let content = "\
export FOO=bar
alias ll='ls -la'
greet() {
    echo hello
}
";
        let exports = analyze_shell(content);
        assert_eq!(exports.variables.len(), 1);
        assert_eq!(exports.aliases.len(), 1);
        assert_eq!(exports.functions.len(), 1);
        assert_eq!(exports.variables[0].name, "FOO");
        assert_eq!(exports.aliases[0].name, "ll");
        assert_eq!(exports.functions[0].name, "greet");
    }

    #[test]
    fn test_nested_braces_in_function() {
        let content = "handler() {\n    if [ -d /tmp ]; then\n        echo yes\n    fi\n}\n";
        let exports = analyze_shell(content);
        assert_eq!(exports.functions.len(), 1);
        assert_eq!(exports.functions[0].name, "handler");
        // The body should contain the nested content
        assert!(exports.functions[0].body.contains("if [ -d /tmp ]; then"));
        assert!(exports.functions[0].body.contains("echo yes"));
    }

    #[test]
    fn test_unquoted_variable_value() {
        let content = "export COUNT=42\n";
        let exports = analyze_shell(content);
        assert_eq!(exports.variables[0].value, "42");
    }

    #[test]
    fn test_variable_with_underscore_and_numbers() {
        let content = "export MY_VAR_2=value\n";
        let exports = analyze_shell(content);
        assert_eq!(exports.variables[0].name, "MY_VAR_2");
    }
}
