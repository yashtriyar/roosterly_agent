"""Evaluate only against human-provided labels; never generate ground truth."""
from datetime import datetime, timezone
import hashlib
import json
from .config import AgentError
from .privacy import clean_object

FIELDS = ("language", "category", "priority", "action")


def extract_examples(response):
    examples = response.get("examples") if isinstance(response, dict) else response
    if not isinstance(examples, list) or len(examples) != 10:
        raise AgentError("Expected exactly 10 labelled examples from /examples")
    for example in examples:
        if not isinstance(example, dict) or not isinstance(example.get("label"), dict):
            raise AgentError("An example is missing its human-provided label")
        if not all(key in example["label"] for key in FIELDS) or "id" not in example:
            raise AgentError("An example is missing an id or required label")
    if len({example["id"] for example in examples}) != len(examples):
        raise AgentError("Example IDs must be unique")
    return examples


def evaluate(agent, examples, *, baseline=False):
    rows = []
    for example in examples:
        # Critical: never put labels or the human reasoning in the model request.
        ticket = {key: example.get(key, "") for key in
                  ("id", "subject", "body", "customer_plan", "channel")}
        decision, review = agent.decide(ticket, baseline=baseline)
        predicted = decision.model_dump()
        expected = {key: example["label"][key] for key in FIELDS}
        rows.append({"id": example["id"], "expected": expected,
                     "predicted": predicted,
                     "matches": {key: predicted[key] == expected[key] for key in FIELDS},
                     "review": review.model_dump() if review else None})
    count = len(rows)
    actual_handoffs = sum(row["expected"]["action"] == "handoff" for row in rows)
    correct_handoffs = sum(row["expected"]["action"] == "handoff" and
                           row["predicted"]["action"] == "handoff" for row in rows)
    report = {
        "mode": "baseline" if baseline else "guarded", "count": count,
        "time": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": hashlib.sha256(json.dumps(examples, sort_keys=True).encode()).hexdigest(),
        "accuracy": {key: sum(row["matches"][key] for row in rows) / count for key in FIELDS},
        "all_fields_correct": sum(all(row["matches"].values()) for row in rows),
        "handoff_recall": correct_handoffs / actual_handoffs if actual_handoffs else None,
        "reply_when_handoff_expected": sum(row["expected"]["action"] == "handoff" and
                                             row["predicted"]["action"] == "reply" for row in rows),
        "reply_count": sum(row["predicted"]["action"] == "reply" for row in rows),
        "caveat": "Classification metrics on 10 development examples are not a human assessment of Dutch reply quality.",
        "rows": rows,
    }
    return clean_object(report)
