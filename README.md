# Roosterly support agent

## How to run

Python 3.11+. Run `python -m venv .venv`, activate it, then `python -m pip install -e .`.
Copy `.env.example` to `.env` and set the helpdesk key, application email, hosted-model
URL/key and a chat-model ID available to your account. No local GPU is needed.
Run `python -m unittest discover -s tests -v`, `roosterly status`, `roosterly examples`,
then `roosterly run --limit 1` (dry-run). See [the walkthrough](docs/QUICKSTART.md).
Only `roosterly run --submit` posts decisions. The final run is deliberately two
commands: `roosterly reset --yes`, then `roosterly run --submit` without a limit.

## Decisions

1. Small synchronous Python workflow; typed model proposals and code-controlled API
   actions. All 12 FAQ entries fit in context, so no retrieval service/framework.
2. Process Dutch directly, preserving exact UI labels. A separate model pass checks
   grounding/language and produces an English back-translation for inspection.
   This costs a second request per ticket and is not independent human verification.
3. SQLite records vetted pending decisions before submission. Remote state is the
   authority. Hosted-model URL/model/key are configurable; free quotas are account
   dependent. 

## Reliability

503/429: bounded retries with jitter or `Retry-After`; requests are paced below the
helpdesk limit. 409: never repost, reconcile handled state. Timeout: GET before any
retry; unknown state stops. On restart, pending writes are reconciled and unchanged
vetted decisions reused. Snapshot all pages before submitting. A local account lock
prevents concurrent local runs; server duplicate rejection remains necessary across
machines. Inputs are untrusted, models have no tools, and payment identifiers are
redacted. `logs/` contains one metadata-only line per ticket; local drafts/examples
stay in ignored `data/`. Never commit credentials or the state database.

## Eval and fix

Run `roosterly eval --baseline --output evals/before.json`, inspect mismatches,
make and explain one evidence-driven fix, then `roosterly eval --output evals/after.json`.
The baseline omits review/policy checks and can never submit. Reports use the ten
human labels, separate field accuracies, unsafe-reply counts, and token usage.
**Live results and the required observed fix are pending credentials/local execution;
no scores are invented.** Cost/100 = `(input_tokens × input_price + output_tokens ×
output_price) / 1,000,000 × 100 / tickets`. Prices are USD/million from your provider;
blank means unknown. Free allocation may mean zero actual spend, not unlimited usage.

## What I would improve

Add independently reviewed Dutch answer checks and a larger held-out multilingual
set. Replace heuristic risk matching with measured coverage improvements. Ask the
API owner to document handling-state response fields and add idempotency keys;
this reduces uncertainty after network timeouts. See [design and limitations](docs/DESIGN.md).
