"""Small hosted-model adapter using the chat-completions HTTP protocol."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from pydantic import ValidationError
from .config import AgentError, ManualReview
from .http import Transport
from .privacy import clean_object


def normalise(value):
    """Tolerate harmless LLM sloppiness: null for unused fields, 'P2'-style case, numeric strings.
    Missing REQUIRED fields and wrong enum values still fail validation."""
    if not isinstance(value, dict):
        return value
    value = {key: item for key, item in value.items() if item is not None}
    for key, fix in (("priority", str.upper), ("language", str.lower), ("action", str.lower),
                     ("category", str.lower)):
        if isinstance(value.get(key), str):
            value[key] = fix(value[key].strip())
    if isinstance(value.get("confidence"), str):
        try:
            value["confidence"] = float(value["confidence"])
        except ValueError:
            pass
    return value


class Model:
    def __init__(self, settings, *, http=None):
        self.settings = settings
        self.http = http or Transport(settings.llm_url, {"Authorization": "Bearer " + settings.llm_key},
                              interval=settings.llm_interval)
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "missing_usage_calls": 0}

    def ask(self, system, data, schema):
        prompt = system + "\nReturn ONLY a JSON object matching this schema:\n" + json.dumps(schema.model_json_schema())
        messages = [{"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(data, ensure_ascii=False)}]
        for attempt in range(2):
            body = {"model": self.settings.model, "messages": messages,
                    "temperature": 0, "max_tokens": 1800}
            if self.settings.json_mode:
                body["response_format"] = {"type": "json_object"}
            response = self.http.request("POST", "chat/completions", json=body)
            if not isinstance(response, dict):
                raise AgentError("Model endpoint returned an unexpected response shape.")
            self.record_usage(response)
            try:
                text = response["choices"][0]["message"]["content"]
                if not isinstance(text, str):
                    raise ValueError("Expected text")
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
                value = json.loads(text)
                return schema.model_validate(clean_object(normalise(value)))
            except (KeyError, IndexError, ValueError, TypeError, ValidationError) as exc:
                # Name the failing FIELDS only; never echo model output (it may hold ticket data).
                hint = ""
                if isinstance(exc, ValidationError):
                    hint = " Problems: " + "; ".join(sorted({
                        ".".join(str(part) for part in err["loc"]) + " (" + err["type"] + ")"
                        for err in exc.errors()}))[:400]
                messages.append({"role": "user", "content": "The previous output was invalid." + hint +
                                 " Return exactly the required JSON with correct types, all required fields, and no additional fields."})
        raise ManualReview("Model failed structured-output validation twice.")

    def record_usage(self, response):
        usage = response.get("usage") or {}
        if not isinstance(usage, dict):
            usage = {}
        self.usage["calls"] += 1
        missing = not all(isinstance(usage.get(k), int) for k in ("prompt_tokens", "completion_tokens"))
        self.usage["missing_usage_calls"] += int(missing)
        self.usage["input_tokens"] += usage.get("prompt_tokens", 0) if isinstance(usage.get("prompt_tokens"), int) else 0
        self.usage["output_tokens"] += usage.get("completion_tokens", 0) if isinstance(usage.get("completion_tokens"), int) else 0
        path = self.settings.root / "data" / "usage.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"time": datetime.now(timezone.utc).isoformat(), "model": self.settings.model,
                  "input_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens")}
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record) + "\n")

    def cost_report(self, ticket_count):
        report = {**self.usage, "tickets": ticket_count, "model": self.settings.model,
                  "input_usd_per_million": self.settings.input_price,
                  "output_usd_per_million": self.settings.output_price,
                  "estimated_usd": None, "estimated_usd_per_100_tickets": None}
        if (self.settings.input_price is not None and self.settings.output_price is not None
                and not self.usage["missing_usage_calls"] and ticket_count):
            cost = (self.usage["input_tokens"] * self.settings.input_price +
                    self.usage["output_tokens"] * self.settings.output_price) / 1_000_000
            report.update(estimated_usd=cost, estimated_usd_per_100_tickets=cost * 100 / ticket_count)
        return report
