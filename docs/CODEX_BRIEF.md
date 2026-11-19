# Brief for opening this project in the Codex app

This is a Python 3.11+ CLI support agent for Nordavo's Roosterly take-home. Read
README.md, docs/DESIGN.md, docs/QUICKSTART.md and roosterly/faq.md first. Keep code
simple enough to explain and modify in a 20-minute interview.

Review implementation and offline tests before changing it. Run:

```bash
python -m unittest discover -s tests -v
```

The user will set `.env` locally with distinct helpdesk/model keys and the email
they applied with. Do not print, commit, copy into prompts, or request those keys
in chat. The model runs at a hosted compatible API, not on the user's GPU. Confirm
model access using a dry-run; do not assume every advertised model has free access.

Use only the supplied FAQ for customer answers. Mandatory handoffs override FAQ
coverage. Preserve the P1-P4 definitions, reply language, English handoff notes,
redaction, all-page snapshot, account-scoped state, bounded retries and submission
reconciliation. Model proposals never call tools. Baseline evaluation can never
submit decisions. Unknown write state must never become a guessed successful or
failed write. Do not introduce a UI/vector database/framework without a concrete
need the candidate can explain.

Fetch and inspect the actual labelled examples locally, keep labels out of model
context, record honest baseline results, fix one observed error and rerun. Do not
hardcode ticket IDs, expected answers, example labels, or claimed eval scores. Do
not fabricate commit history. Explain why changes help and what tests establish.
The existing synthetic refund regression is not evidence of actual model quality.

`run` defaults to dry-run. `run --submit` sends real helpdesk decisions; `reset --yes`
reopens the remote practice set. Explain these effects before the final live run
and follow the user's current instructions. Never run security exploits against
the supplied helpdesk. Before a final submission, preserve safe logs/eval reports,
update README's pending results, and check that status reports all 30 handled.

Suggested independent comparison: implement against this behavioral contract in
a separate folder and run both on the same downloaded ten examples, same hosted
model and prices. Compare safety errors, helpful reply coverage, priority/action
accuracy, API failure behavior, tokens/cost and readability. Run live mutations
serially on one account, deliberately resetting between experiments when requested;
never have competing implementations submit concurrently.
