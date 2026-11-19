# Validation of this initial build

Checked on 2026-11-16:

- `python -m unittest discover -s tests -v`: 40 tests passed, no remote calls.
- `python -m roosterly --help`: CLI command router loads successfully.
- `python -m pip wheel . --no-deps --no-build-isolation --no-cache-dir --wheel-dir build_check`: package builds successfully.
- Built wheel inspected: FAQ data and the `roosterly` console entry point are present.

Tests cover temporary 503s, Retry-After, bounded retry, non-retried authentication
errors, redirects, timeout-after-success reconciliation, a retry after explicit
open state, unknown state, 409, multi-page snapshots, cursor loops, account isolation,
crash recovery, lock exclusion, unchanged/changed pending decisions, dry-run writes,
safe-log uniqueness, payment redaction, invalid model JSON/repair, cost calculation,
label leakage prevention, FAQ evidence, language checks and escalation overrides.

These are mocked contract tests. They do not establish provider availability, real
API response shapes, prompt-injection immunity, Dutch quality, or model accuracy.
No API keys were configured, no human-labelled examples were fetched, and no real
helpdesk actions, resets, eval scores or final 30-ticket run are claimed. No fake
production logs or example labels have been included to fill those gaps.
