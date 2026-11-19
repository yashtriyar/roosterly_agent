from urllib.parse import quote
from .config import AgentError
from .http import Transport, HTTPFailure, UncertainWrite


def ticket_object(value):
    if not isinstance(value, dict):
        raise AgentError("Unexpected ticket response shape")
    ticket = value.get("ticket", value)
    if not isinstance(ticket, dict) or "id" not in ticket:
        raise AgentError("Ticket response is missing an id")
    return ticket


def handling_state(value):
    """Return open/handled/unknown. Never infer 'open' from missing metadata."""
    objects = [value]
    if isinstance(value, dict) and isinstance(value.get("ticket"), dict):
        objects.append(value["ticket"])
    for item in objects:
        if not isinstance(item, dict):
            continue
        if item.get("handled_at") or item.get("decision") or item.get("resolution"):
            return "handled"
        if item.get("handled") is True or item.get("is_handled") is True:
            return "handled"
        if item.get("status") in {"handled", "replied", "closed", "handed_off", "handoff"}:
            return "handled"
    for item in objects:
        if isinstance(item, dict) and (item.get("status") == "open" or
                                      item.get("handled") is False or
                                      item.get("is_handled") is False):
            return "open"
    return "unknown"


class Helpdesk:
    def __init__(self, settings, *, http=None):
        self.http = http or Transport(settings.helpdesk_url, {
            "Authorization": "Bearer " + settings.helpdesk_key,
            "X-Candidate-Email": settings.email,
        })

    def get(self, ticket_id):
        return self.http.request("GET", "tickets/" + quote(ticket_id, safe=""))

    def open_tickets(self):
        # Snapshot the complete open set before any writes mutate pagination.
        result, seen, cursors = [], set(), set()
        cursor = None
        while True:
            params = {"status": "open", "limit": 10}
            if cursor is not None:
                params["cursor"] = cursor
            page = self.http.request("GET", "tickets", params=params)
            if not isinstance(page, dict) or not isinstance(page.get("tickets"), list):
                raise AgentError("Expected {tickets: [...], next_cursor: ...}")
            for raw in page["tickets"]:
                ticket = ticket_object(raw)
                identity = str(ticket["id"])
                if identity not in seen:
                    seen.add(identity)
                    result.append(ticket)
            cursor = page.get("next_cursor")
            if cursor is None:
                return result
            if str(cursor) in cursors:
                raise AgentError("Repeated pagination cursor; refusing an infinite loop")
            cursors.add(str(cursor))

    def submit(self, ticket_id, decision):
        path = "tickets/" + quote(ticket_id, safe="") + "/" + decision.action
        # At most one retry after a transport ambiguity, and only after confirmed open.
        for attempt in range(2):
            try:
                self.http.request("POST", path, json=decision.payload(), uncertain_write=True)
                return "submitted"
            except HTTPFailure as exc:
                if exc.status != 409:
                    raise
                state = handling_state(self.get(ticket_id))
                if state != "handled":
                    raise AgentError("409 received but handling state cannot be reconciled") from None
                return "already_handled"
            except UncertainWrite:
                state = handling_state(self.get(ticket_id))
                if state == "handled":
                    return "reconciled"
                if state != "open" or attempt == 1:
                    raise AgentError("Ambiguous submission; stopped safely. Rerun after checking ticket state.") from None
        raise AgentError("Submission could not be confirmed")
