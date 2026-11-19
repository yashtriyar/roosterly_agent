"""CLI defaults to dry-run. Only `run --submit` posts ticket decisions."""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import sys
from .config import Settings, AgentError
from .evaluation import extract_examples, evaluate
from .helpdesk import Helpdesk, handling_state
from .model import Model
from .policy import Agent
from .privacy import clean_object
from .state import Journal, process_lock


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(clean_object(value), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def run(settings, desk, model, *, submit=False, limit=None):
    agent = Agent(model)
    journal = Journal(settings.root, settings.scope)
    count = 0
    try:
        tickets = desk.open_tickets()
        open_ids = {str(ticket["id"]) for ticket in tickets}
        if submit:
            # A crash may occur after server success but before the local commit.
            for (ticket_id,) in journal.pending():
                if ticket_id not in open_ids:
                    if handling_state(desk.get(ticket_id)) != "handled":
                        raise AgentError("Pending ticket absent from open set, but completion is unconfirmed.")
                    journal.mark(ticket_id, "reconciled")
        for ticket in tickets[:limit] if limit else tickets:
            decision = journal.prepared(ticket) if submit else None
            checked = None
            if decision is None:
                decision, checked = agent.decide(ticket)
            if submit:
                journal.save(ticket, decision, "pending")
                # Journal is committed before a potentially ambiguous remote action.
                journal.export()
                outcome = desk.submit(str(ticket["id"]), decision)
                journal.mark(str(ticket["id"]), outcome)
                journal.export()
                print(json.dumps({"ticket_id": str(ticket["id"]), "action": decision.action, "outcome": outcome}))
            else:
                # Preview stays local and does not become a resumable submission.
                print(json.dumps({"ticket_id": str(ticket["id"]), "dry_run": True,
                                  "decision": decision.model_dump(),
                                  "review": checked.model_dump() if checked else None}, ensure_ascii=False))
            count += 1
    finally:
        if submit:
            journal.export()
        journal.close()
        write_json(settings.root / "evals" / "last_run_usage.json", model.cost_report(count))
    return count


def parser():
    result = argparse.ArgumentParser(description="Roosterly support agent (dry-run by default)")
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Read account status; no model needed")
    sub.add_parser("examples", help="Fetch ten labelled examples into data/examples.json")
    reset = sub.add_parser("reset", help="Re-open practice tickets and clear this account's local journal")
    reset.add_argument("--yes", action="store_true", help="Explicitly authorise the practice reset")
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--submit", action="store_true", help="Post validated decisions to the helpdesk")
    run_parser.add_argument("--limit", type=int, help="Process at most this many tickets")
    evaluation = sub.add_parser("eval")
    evaluation.add_argument("--baseline", action="store_true", help="Skip policy/reviewer for evaluation ONLY")
    evaluation.add_argument("--examples", type=Path, default=Path("data/examples.json"))
    evaluation.add_argument("--output", type=Path, help="Report path; default evals/baseline.json or guarded.json")
    return result


def main():
    args = parser().parse_args()
    try:
        if args.command == "reset" and not args.yes:
            raise AgentError("Reset changes the remote practice set. Run `roosterly reset --yes` deliberately.")
        if args.command == "run" and args.limit is not None and args.limit <= 0:
            raise AgentError("--limit must be positive")
        settings = Settings.load(need_model=args.command in {"run", "eval"})
        with ExitStack() as stack:
            desk = Helpdesk(settings)
            stack.callback(desk.http.close)
            stack.enter_context(process_lock(settings.root / "data" / (settings.scope + ".lock")))
            if args.command == "status":
                print(json.dumps(clean_object(desk.http.request("GET", "status")), indent=2))
            elif args.command == "examples":
                examples = extract_examples(desk.http.request("GET", "examples"))
                write_json(settings.root / "data" / "examples.json", examples)
                print("Saved 10 labelled examples to data/examples.json (keep customer data private).")
            elif args.command == "reset":
                # A reset timeout is also ambiguous; never silently replay it.
                desk.http.request("POST", "practice/reset", uncertain_write=True)
                journal = Journal(settings.root, settings.scope)
                try:
                    journal.clear()
                finally:
                    journal.close()
                print("Practice set reset; local journal cleared for this account.")
            else:
                model = Model(settings)
                stack.callback(model.http.close)
                if args.command == "run":
                    count = run(settings, desk, model, submit=args.submit, limit=args.limit)
                    print(json.dumps({"completed": count, "submitted": args.submit}))
                else:
                    examples = extract_examples(json.loads(args.examples.read_text(encoding="utf-8")))
                    report = evaluate(Agent(model), examples, baseline=args.baseline)
                    report["usage"] = model.cost_report(len(examples))
                    output = args.output or Path("evals/baseline.json" if args.baseline else "evals/guarded.json")
                    write_json(output, report)
                    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2))
    except (AgentError, OSError, ValueError) as exc:
        # Never print arbitrary provider errors, raw requests, model output, or secrets.
        message = str(exc) if isinstance(exc, AgentError) else "Local configuration/file error; check paths and numeric settings."
        print("Stopped: " + message, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Pending submissions will be reconciled on the next run.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
