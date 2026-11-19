# Run the project locally

## 1. Open the folder in Codex

Extract the ZIP, then open the `roosterly_agent` folder as a project in the Codex app.
Read README.md and docs/DESIGN.md. Python 3.11 or newer is required. The code runs
on your CPU; the selected API provider hosts the model.

Create and activate a virtual environment:

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item .env.example .env
```

```bash
# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
```

If activation is restricted, invoke `.venv\Scripts\python.exe` and
`.venv\Scripts\roosterly.exe` directly on Windows. On Unix use `.venv/bin/python`
and `.venv/bin/roosterly`.

## 2. Configure a hosted model

Open `.env` locally. Fill in `HELPDESK_API_KEY` from the assignment email and
`CANDIDATE_EMAIL` with the email you applied with, every time. Set a separate
`LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` for the hosted model.

The supplied base URL example is Groq's compatible endpoint:
`https://api.groq.com/openai/v1`. Obtain an API key at https://console.groq.com/keys
and select a chat model actually available under your account and intended quota.
The model ID is intentionally blank because access changes. Consult the current
[model catalogue](https://console.groq.com/docs/models) and
[account limits](https://console.groq.com/settings/limits).

Hugging Face's alternative URL is `https://router.huggingface.co/v1`; choose a
currently hosted model and use an HF token with inference permission. Its
[pricing page](https://huggingface.co/docs/inference-providers/pricing) checked on
2026-11-16 states free accounts have no included inference credits. Do not assume
an HF signup means free hosted inference. Other compatible providers work with
the same three environment settings. There is no automatic paid fallback.

Use a provider/model supporting chat completions, system messages, and enough
output tokens for JSON. If it rejects `response_format`, set `LLM_JSON_MODE=false`;
Pydantic still validates the response. If it rejects the model or parameters,
choose a compatible endpoint/model. For 429s increase `LLM_MIN_INTERVAL_SECONDS`;
if quota is exhausted, wait or explicitly reconfigure the provider yourself.
The code does not run tools/search exposed by any provider.

Set token prices only from your provider's actual terms. Leave them blank if
unknown; set both to zero only when reporting usage covered by a free allocation.
For a SOCKS proxy environment install `python -m pip install 'httpx[socks]'` too.

## 3. Test, fetch labels, inspect a preview

```bash
python -m unittest discover -s tests -v
roosterly status
roosterly examples
roosterly run --limit 1
```

The last command prints a decision, the review, and an English translation for
inspection. It calls the hosted model but does NOT post ticket decisions. Preview
output is redacted for common payment identifiers, but may still contain personal
information: keep it private. The example download stays in ignored `data/`.

## 4. Measure and fix an actual failure

```bash
roosterly eval --baseline --output evals/before.json
# Inspect rows[].matches and rows[].predicted; make and document one observed fix.
roosterly eval --output evals/after.json
python compare_evals.py evals/before.json evals/after.json
```

Eval never posts decisions. Neither `label` nor human reasoning goes to the model.
Baseline means proposal-only; guarded means proposal plus review and code policy.
Comparing these is an ablation, not automatically proof of an improvement: if the
baseline gets everything right, find a real limitation rather than manufacturing
an incorrect score. Preserve before/after files and actual commits. Temperature
zero is not a guarantee of deterministic results; use the same model/dataset and
record any model changes. Small improvements on ten examples can be noise.

After a fix, inspect wrong cases, Dutch/English/de replies, English handoff notes,
UI paths, plan restrictions, and whether the system is escalating too much.
Fill in README's pending results with measured values and your explanation.

## 5. Submit a practice run and final run

```bash
roosterly run --submit --limit 1
# Inspect the outcome and safe log before handling the rest.
roosterly run --submit
```

Restarting after a crash reconciles pending writes. Use only one runner per account,
even across machines. Do not delete `data/state.sqlite3` to solve an ambiguous write.
For a deliberate fresh practice round, use the reset command rather than deleting
local files.

Final run, only when you are ready:

```bash
roosterly reset --yes
roosterly run --submit
roosterly status
```

Check status shows no open tickets and the expected 30 handled. The runner does not
assume a fixed batch size; the final check matters. Do not reset after that run.
Review and explicitly add intended `evals/before.json`, `evals/after.json` and safe
`logs/*.jsonl` to your repo; evals are ignored by default because they include drafts.
Never commit `.env`, example ticket text, usage files with private metadata, SQLite,
or API keys. Fill in the one-page README before delivering. Create real incremental
commits; do not fabricate development history. Send the repo link yourself using
the assignment instructions, granting `nordavo-hiring` access if it is private.

## Troubleshooting

- 401: fix the relevant key locally; the helpdesk and model keys are different.
- 402/quota: inspect provider billing/free allocation; no paid fallback is enabled.
- 400/422: inspect your provider's supported parameters or the helpdesk contract.
  Bodies are deliberately omitted from errors because they may contain customer data.
- Language disagreement/invalid JSON: no decision was sent for that ticket. Inspect
  a dry-run, improve the prompt or choose a stronger model, then retry.
- Unknown handling state after a timeout/409: inspect that ticket via the API locally;
  update `handling_state()` and its contract tests if the real response uses different
  documented field names. Do not guess that missing metadata means open.
- Long customer input: manual review is required rather than silently truncating a
  possibly important risk at the end of the message.
