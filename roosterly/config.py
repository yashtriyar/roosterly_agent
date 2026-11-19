from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv


class AgentError(Exception):
    """A safe message that can be printed without exposing ticket text or secrets."""


class ManualReview(AgentError):
    """This ONE ticket cannot be automated safely. Hand it to a human; do not stop the run."""


@dataclass
class Settings:
    helpdesk_url: str
    helpdesk_key: str
    email: str
    llm_url: str
    llm_key: str
    model: str
    llm_interval: float = 2.0
    json_mode: bool = True
    input_price: float | None = None
    output_price: float | None = None
    root: Path = Path(".")

    @property
    def scope(self):
        identity = self.helpdesk_url.rstrip("/") + "|" + self.email.strip().lower()
        return hashlib.sha256(identity.encode()).hexdigest()[:20]

    @classmethod
    def load(cls, *, need_model=True):
        load_dotenv()
        names = ["HELPDESK_BASE_URL", "HELPDESK_API_KEY", "CANDIDATE_EMAIL"]
        if need_model:
            names += ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"]
        missing = [name for name in names if not os.getenv(name, "").strip()]
        if missing:
            raise AgentError("Set these environment variables: " + ", ".join(missing))
        for name in ["HELPDESK_BASE_URL"] + (["LLM_BASE_URL"] if need_model else []):
            parsed = urlparse(os.environ[name])
            if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.query:
                raise AgentError(name + " must be an HTTPS URL without embedded credentials/query")
        def price(name):
            value = os.getenv(name, "").strip()
            result = float(value) if value else None
            if result is not None and result < 0:
                raise AgentError(name + " cannot be negative")
            return result
        return cls(
            os.environ["HELPDESK_BASE_URL"].rstrip("/"), os.environ["HELPDESK_API_KEY"],
            os.environ["CANDIDATE_EMAIL"].strip(), os.getenv("LLM_BASE_URL", "").rstrip("/"),
            os.getenv("LLM_API_KEY", ""), os.getenv("LLM_MODEL", ""),
            max(0.0, float(os.getenv("LLM_MIN_INTERVAL_SECONDS", "2"))),
            os.getenv("LLM_JSON_MODE", "true").lower() == "true",
            price("INPUT_USD_PER_MILLION"), price("OUTPUT_USD_PER_MILLION"),
        )
