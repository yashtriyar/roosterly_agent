"""Compare two real eval reports without making model calls."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args()
    before = json.loads(args.before.read_text(encoding="utf-8"))
    after = json.loads(args.after.read_text(encoding="utf-8"))
    if before["dataset_sha256"] != after["dataset_sha256"]:
        parser.error("Reports use different datasets; compare the same human-labelled examples")
    print("Metric                         Before      After")
    for field in ("language", "category", "priority", "action"):
        print(f"{field + ' accuracy':30} {before['accuracy'][field]:8.1%} {after['accuracy'][field]:10.1%}")
    for field in ("all_fields_correct", "reply_when_handoff_expected", "reply_count"):
        print(f"{field:30} {before[field]:8} {after[field]:10}")
    print("Inspect handoff recall, individual mismatches and answer quality before concluding improvement.")


if __name__ == "__main__":
    main()
