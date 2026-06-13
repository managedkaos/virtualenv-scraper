use proptest::prelude::*;
use virtualenv_viewer::options::resolve_options_from_sources;

// ─────────────────────────────────────────────────────────────────────────────
// Property-Based Tests: Configuration Precedence
// ─────────────────────────────────────────────────────────────────────────────

/// Strategy to generate an Option<bool> representing a configuration source.
/// None means the source is absent, Some(true/false) means present with a value.
fn option_bool_strategy() -> impl Strategy<Value = Option<bool>> {
    prop_oneof![Just(None), Just(Some(true)), Just(Some(false)),]
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(100))]

    /// **Feature: virtualenv-config-viewer, Property 10: Configuration Precedence**
    ///
    /// For any combination of CLI flag (Some(true), Some(false), None),
    /// env var (Some(true), Some(false), None), and config file (Some(true),
    /// Some(false), None), the resolved value equals the highest-precedence
    /// source present (CLI > env > config file > default false).
    ///
    /// **Validates: Requirements 6.5**
    #[test]
    fn prop_configuration_precedence(
        cli in option_bool_strategy(),
        env in option_bool_strategy(),
        config in option_bool_strategy(),
    ) {
        let result = resolve_options_from_sources(cli, env, config);

        // Compute expected value: first present source wins, default is false
        let expected_restart = cli.or(env).or(config).unwrap_or(false);

        prop_assert_eq!(
            result.restart_on_edit, expected_restart,
            "Precedence violated: cli={:?}, env={:?}, config={:?} → got {}, expected {}",
            cli, env, config, result.restart_on_edit, expected_restart
        );
    }
}
