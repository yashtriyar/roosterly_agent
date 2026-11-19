"""Conservative redaction before model requests and persisted outputs."""
import re

# Broad matches intentionally favor privacy over retaining order/phone numbers.
# Country code + check digits must be attached ("NL91"); a spaced "NL 91" is only accepted in
# upper case. This stops ordinary text such as "Op 15 november 2026" being read as an IBAN.
IBAN = re.compile(r"\b(?:[A-Za-z]{2}\d{2}|[A-Z]{2} \d{2})(?:[ -]?[A-Za-z0-9]){10,30}\b")
PAYMENT_LABEL = re.compile(r"\b(?:cvv|cvc|security code|beveiligingscode|account number|rekeningnummer)\s*[:=]?\s*[A-Z0-9][A-Z0-9 -]{2,30}", re.I)
NUMBERS = re.compile(r"(?<!\w)(?:\d[ -]?){8,19}(?!\w)")


def _mod97(compact: str) -> bool:
    moved = compact[4:] + compact[:4]
    return int("".join(str(int(c, 36)) for c in moved)) % 97 == 1


def _redact_iban(match) -> str:
    """Redact the candidate. If a prefix is a checksum-valid IBAN, keep any trailing words."""
    text = match.group(0)
    ends, compact = [], ""
    for index, char in enumerate(text):
        if char.isalnum():
            compact += char.upper()
            ends.append(index + 1)
    for length in range(min(34, len(compact)), 14, -1):
        if _mod97(compact[:length]):
            return "[REDACTED_IBAN]" + text[ends[length - 1]:]
    return "[REDACTED_IBAN]"  # checksum invalid (typo / fake test IBAN): still never repeat it


def redact(text: str) -> str:
    return PAYMENT_LABEL.sub("[REDACTED_PAYMENT]", NUMBERS.sub("[REDACTED_NUMBER]", IBAN.sub(_redact_iban, text)))


def safe_ticket(ticket: dict) -> dict:
    return {key: redact(str(ticket.get(key, ""))) for key in
            ("subject", "body", "customer_plan", "channel")}


def clean_object(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [clean_object(item) for item in value]
    if isinstance(value, dict):
        return {key: clean_object(item) for key, item in value.items()}
    return value
