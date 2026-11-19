"""SQLite journal, atomic safe-log export, and a process lock released on crash."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import os
from .config import AgentError
from .schemas import Decision


@contextmanager
def process_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    file = path.open("a+b")
    if file.tell() == 0:
        file.write(b"0")
        file.flush()
    file.seek(0)
    acquired = False
    try:
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            raise AgentError("Another agent process holds this account lock.") from None
        yield
    finally:
        if acquired:
            file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)
        file.close()


def fingerprint(ticket):
    fields = {key: ticket.get(key) for key in ("id", "subject", "body", "customer_plan", "channel")}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


class Journal:
    def __init__(self, root, scope):
        self.scope = scope
        self.root = root
        (root / "data").mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(root / "data" / "state.sqlite3")
        self.db.execute("""CREATE TABLE IF NOT EXISTS decisions (
            scope TEXT, ticket_id TEXT, fingerprint TEXT, decision TEXT,
            outcome TEXT, updated TEXT, PRIMARY KEY(scope, ticket_id))""")
        self.db.commit()

    def pending(self):
        return self.db.execute("SELECT ticket_id FROM decisions WHERE scope=? AND outcome='pending'",
                               (self.scope,)).fetchall()

    def prepared(self, ticket):
        row = self.db.execute("SELECT fingerprint, decision, outcome FROM decisions WHERE scope=? AND ticket_id=?",
                              (self.scope, str(ticket["id"]))).fetchone()
        if row and row[0] == fingerprint(ticket) and row[2] == "pending":
            return Decision.model_validate_json(row[1])
        return None

    def save(self, ticket, decision, outcome):
        self.db.execute("INSERT OR REPLACE INTO decisions VALUES (?,?,?,?,?,?)", (
            self.scope, str(ticket["id"]), fingerprint(ticket), decision.model_dump_json(),
            outcome, datetime.now(timezone.utc).isoformat()))
        self.db.commit()

    def mark(self, ticket_id, outcome):
        self.db.execute("UPDATE decisions SET outcome=?, updated=? WHERE scope=? AND ticket_id=?",
                        (outcome, datetime.now(timezone.utc).isoformat(), self.scope, ticket_id))
        self.db.commit()

    def clear(self):
        self.db.execute("DELETE FROM decisions WHERE scope=?", (self.scope,))
        self.db.commit()
        self.export()

    def export(self):
        directory = self.root / "logs"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (self.scope + ".jsonl")
        temporary = path.with_suffix(".tmp")
        rows = self.db.execute("SELECT ticket_id,decision,outcome,updated FROM decisions WHERE scope=? ORDER BY ticket_id",
                               (self.scope,)).fetchall()
        with temporary.open("w", encoding="utf-8") as file:
            for ticket_id, raw, outcome, updated in rows:
                decision = json.loads(raw)
                # Deliberate allowlist: no free text, payment details, email or keys.
                record = {key: decision[key] for key in ("language", "category", "priority", "action")}
                record.update(ticket_id=ticket_id, outcome=outcome, updated=updated)
                file.write(json.dumps(record) + "\n")
        temporary.replace(path)

    def close(self):
        self.db.close()
