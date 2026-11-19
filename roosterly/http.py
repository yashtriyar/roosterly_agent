"""Bounded retries, pacing, and safe errors. Action timeouts are NOT retried here."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import random
import time
import httpx
from .config import AgentError


class HTTPFailure(AgentError):
    def __init__(self, status, message="HTTP request failed"):
        self.status = status
        super().__init__(f"{message} (HTTP {status}). Response body omitted for privacy.")


class UncertainWrite(AgentError):
    pass


def retry_delay(value: str | None, attempt: int) -> float:
    if value:
        try:
            return max(0, float(value))
        except ValueError:
            try:
                return max(0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
            except (ValueError, TypeError, OverflowError):
                pass
    return min(16, 0.5 * 2 ** attempt) + random.uniform(0, 0.25)


class Transport:
    def __init__(self, base_url, headers, interval=0.3, *, client=None, sleep=time.sleep):
        self.client = client or httpx.Client(base_url=base_url + "/", headers=headers,
                                            timeout=60, follow_redirects=False)
        self.interval = interval
        self.sleep = sleep
        self.last_request = 0.0

    def request(self, method, path, *, uncertain_write=False, **kwargs):
        for attempt in range(5):
            wait = self.interval - (time.monotonic() - self.last_request)
            if wait > 0:
                self.sleep(wait)
            self.last_request = time.monotonic()
            try:
                response = self.client.request(method, path.lstrip("/"), **kwargs)
            except httpx.TransportError:
                if uncertain_write:
                    raise UncertainWrite("Submission outcome unknown; reconcile before retrying.") from None
                if attempt == 4:
                    raise AgentError("Network retries exhausted; no response body was logged.") from None
                self.sleep(retry_delay(None, attempt))
                continue
            if response.status_code in (429, 503):
                if attempt == 4:
                    raise HTTPFailure(response.status_code, "Retry budget exhausted")
                # No cap on server Retry-After: never retry earlier than requested.
                self.sleep(retry_delay(response.headers.get("Retry-After"), attempt))
                continue
            if response.is_error or response.is_redirect:
                raise HTTPFailure(response.status_code)
            try:
                return response.json() if response.content else {}
            except ValueError:
                if uncertain_write:
                    raise UncertainWrite("Submission returned unreadable JSON; reconcile first.") from None
                raise AgentError("Server returned unreadable JSON.") from None
        raise AgentError("Request retries exhausted")

    def close(self):
        self.client.close()
