use proptest::prelude::*;
use virtualenv_viewer::shell_analyzer::analyze_shell;

// ─────────────────────────────────────────────────────────────────────────────
// Generators
// ─────────────────────────────────────────────────────────────────────────────

/// Generate a valid shell variable name: starts with [A-Za-z_], followed by [A-Za-z0-9_].
fn var_name() -> impl Strategy<Value = String> {
    "[A-Z_][A-Z0-9_]{1,10}".prop_map(|s| s)
}

/// Generate a valid alias name: starts with [A-Za-z_], followed by [A-Za-z0-9_-].
fn alias_name() -> impl Strategy<Value = String> {
    "[a-z_][a-z0-9_-]{1,10}".prop_map(|s| s)
}

/// Generate a valid function name: starts with [A-Za-z_], followed by [A-Za-z0-9_].
fn func_name() -> impl Strategy<Value = String> {
    "[a-z_][a-z0-9_]{1,10}".prop_map(|s| s)
}

/// Generate a simple variable value that doesn't contain newlines or quotes.
/// This ensures the round-trip is unambiguous.
fn simple_value() -> impl Strategy<Value = String> {
    "[a-zA-Z0-9/_.:=-]{1,30}".prop_map(|s| s)
}

/// Generate a simple function body (single line, no braces).
fn simple_body() -> impl Strategy<Value = String> {
    "[a-z ]{1,20}"
        .prop_map(|s| s.trim().to_string())
        .prop_filter("body must not be empty", |s| !s.is_empty())
}

/// Generate a value that contains shell variable references like $HOME or $PATH.
fn value_with_var_refs() -> impl Strategy<Value = String> {
    prop_oneof![
        Just("$HOME/bin".to_string()),
        Just("$HOME/.local/bin:$PATH".to_string()),
        Just("${HOME}/projects".to_string()),
        Just("/usr/local/bin:$PATH".to_string()),
        Just("$USER@$HOSTNAME".to_string()),
        Just("${MY_VAR}/sub/$OTHER".to_string()),
        "[A-Z_]{1,5}".prop_map(|name| format!("${}/{}", name, "bin")),
    ]
}

// ─────────────────────────────────────────────────────────────────────────────
// Property-Based Tests
// ─────────────────────────────────────────────────────────────────────────────

proptest! {
    #![proptest_config(ProptestConfig::with_cases(100))]

    /// **Feature: virtualenv-config-viewer, Property 3: Variable Export Round-Trip**
    ///
    /// For any set of valid shell variable names and string values, formatting them
    /// as export statements and then parsing with the Shell Analyzer SHALL produce
    /// an equivalent set of name-value pairs.
    ///
    /// **Validates: Requirements 3.1, 3.5**
    #[test]
    fn prop_variable_export_round_trip(
        names_and_values in prop::collection::vec((var_name(), simple_value()), 1..5)
    ) {
        // Deduplicate names, keeping the last occurrence (matching last-write-wins)
        let mut unique: Vec<(String, String)> = Vec::new();
        for (name, value) in &names_and_values {
            if let Some(pos) = unique.iter().position(|(n, _)| n == name) {
                unique[pos] = (name.clone(), value.clone());
            } else {
                unique.push((name.clone(), value.clone()));
            }
        }

        // Format as export statements (test both quoted and unquoted)
        let script: String = names_and_values
            .iter()
            .enumerate()
            .map(|(i, (name, value))| {
                if i % 2 == 0 {
                    format!("export {}=\"{}\"", name, value)
                } else {
                    format!("export {}={}", name, value)
                }
            })
            .collect::<Vec<_>>()
            .join("\n");

        let exports = analyze_shell(&script);

        prop_assert_eq!(exports.variables.len(), unique.len());
        for (expected_name, expected_value) in &unique {
            let found = exports.variables.iter().find(|v| v.name == *expected_name);
            prop_assert!(found.is_some(), "Variable {} not found", expected_name);
            prop_assert_eq!(&found.unwrap().value, expected_value);
        }
    }

    /// **Feature: virtualenv-config-viewer, Property 4: Alias Extraction Round-Trip**
    ///
    /// For any set of valid alias names and definitions, formatting them as alias
    /// statements and then parsing with the Shell Analyzer SHALL produce an equivalent
    /// set of name-definition pairs.
    ///
    /// **Validates: Requirements 3.2, 3.5**
    #[test]
    fn prop_alias_extraction_round_trip(
        names_and_defs in prop::collection::vec((alias_name(), simple_value()), 1..5)
    ) {
        // Deduplicate names, keeping the last occurrence
        let mut unique: Vec<(String, String)> = Vec::new();
        for (name, def) in &names_and_defs {
            if let Some(pos) = unique.iter().position(|(n, _)| n == name) {
                unique[pos] = (name.clone(), def.clone());
            } else {
                unique.push((name.clone(), def.clone()));
            }
        }

        // Format as alias statements (test both single-quoted and double-quoted)
        let script: String = names_and_defs
            .iter()
            .enumerate()
            .map(|(i, (name, def))| {
                if i % 2 == 0 {
                    format!("alias {}='{}'", name, def)
                } else {
                    format!("alias {}=\"{}\"", name, def)
                }
            })
            .collect::<Vec<_>>()
            .join("\n");

        let exports = analyze_shell(&script);

        prop_assert_eq!(exports.aliases.len(), unique.len());
        for (expected_name, expected_def) in &unique {
            let found = exports.aliases.iter().find(|a| a.name == *expected_name);
            prop_assert!(found.is_some(), "Alias {} not found", expected_name);
            prop_assert_eq!(&found.unwrap().definition, expected_def);
        }
    }

    /// **Feature: virtualenv-config-viewer, Property 5: Function Extraction Round-Trip**
    ///
    /// For any set of valid function names and bodies, formatting them as function
    /// definitions and then parsing with the Shell Analyzer SHALL produce an equivalent
    /// set of name-body pairs.
    ///
    /// **Validates: Requirements 3.3, 3.5**
    #[test]
    fn prop_function_extraction_round_trip(
        names_and_bodies in prop::collection::vec((func_name(), simple_body()), 1..3)
    ) {
        // Deduplicate names, keeping the last occurrence
        let mut unique: Vec<(String, String)> = Vec::new();
        for (name, body) in &names_and_bodies {
            if let Some(pos) = unique.iter().position(|(n, _)| n == name) {
                unique[pos] = (name.clone(), body.clone());
            } else {
                unique.push((name.clone(), body.clone()));
            }
        }

        // Alternate between bash-style `name() {` and zsh-style `function name {`
        let script: String = names_and_bodies
            .iter()
            .enumerate()
            .map(|(i, (name, body))| {
                if i % 2 == 0 {
                    format!("{}() {{\n    {}\n}}", name, body)
                } else {
                    format!("function {} {{\n    {}\n}}", name, body)
                }
            })
            .collect::<Vec<_>>()
            .join("\n");

        let exports = analyze_shell(&script);

        prop_assert_eq!(exports.functions.len(), unique.len());
        for (expected_name, expected_body) in &unique {
            let found = exports.functions.iter().find(|f| f.name == *expected_name);
            prop_assert!(found.is_some(), "Function {} not found", expected_name);
            prop_assert_eq!(&found.unwrap().body, expected_body);
        }
    }

    /// **Feature: virtualenv-config-viewer, Property 6: Last-Write-Wins**
    ///
    /// For any shell script containing multiple definitions of the same variable,
    /// alias, or function name, the Shell Analyzer SHALL return only the value from
    /// the last definition in the script, discarding all earlier definitions.
    ///
    /// **Validates: Requirements 3.4**
    #[test]
    fn prop_last_write_wins(
        name in var_name(),
        values in prop::collection::vec(simple_value(), 2..5)
    ) {
        // Build a script with the same variable name exported multiple times
        let script: String = values
            .iter()
            .map(|v| format!("export {}=\"{}\"", name, v))
            .collect::<Vec<_>>()
            .join("\n");

        let exports = analyze_shell(&script);

        // Should have exactly one variable with this name
        prop_assert_eq!(exports.variables.len(), 1);
        prop_assert_eq!(&exports.variables[0].name, &name);
        // The value should be the LAST one defined
        prop_assert_eq!(&exports.variables[0].value, values.last().unwrap());
    }

    /// **Feature: virtualenv-config-viewer, Property 7: Literal Value Preservation**
    ///
    /// For any export statement whose value contains shell variable references
    /// (e.g., $HOME, $PATH, ${VAR}), the Shell Analyzer SHALL return the value as
    /// literal text exactly as written, without performing any variable expansion
    /// or substitution.
    ///
    /// **Validates: Requirements 3.6**
    #[test]
    fn prop_literal_value_preservation(
        name in var_name(),
        value in value_with_var_refs()
    ) {
        // Format the export with the value that contains variable references
        let script = format!("export {}=\"{}\"", name, value);

        let exports = analyze_shell(&script);

        prop_assert_eq!(exports.variables.len(), 1);
        prop_assert_eq!(&exports.variables[0].name, &name);
        // The value must be preserved literally, with $ references intact
        prop_assert_eq!(&exports.variables[0].value, &value);
    }
}
