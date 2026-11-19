"""The model proposes data; application code owns all API actions."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Language = Literal["nl", "en", "de"]
Action = Literal["reply", "handoff", "close"]


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    language: Language
    category: Literal["bug", "billing", "feature_request", "question", "other"]
    priority: Literal["P1", "P2", "P3", "P4"]
    action: Action
    reason: str = Field(min_length=1, max_length=800)
    draft_reply: str = Field(default="", max_length=4000)
    handoff_note: str = Field(default="", max_length=2000)
    faq_ids: list[str] = Field(default_factory=list)
    # Exact excerpts of the FAQ supporting each material statement in a reply.
    evidence: list[str] = Field(default_factory=list)
    mandatory_handoff: bool
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def action_fields(self):
        if self.action == "reply" and not self.draft_reply.strip():
            raise ValueError("reply requires draft_reply")
        if self.action == "handoff" and not self.handoff_note.strip():
            raise ValueError("handoff requires handoff_note")
        return self

    def payload(self) -> dict:
        result = self.model_dump(include={"language", "category", "priority", "reason", "confidence"})
        if self.action == "reply":
            result["draft_reply"] = self.draft_reply
        elif self.action == "handoff":
            result["handoff_note"] = self.handoff_note
        return result


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    language: Language
    mandatory_handoff: bool
    priority: Literal["P1", "P2", "P3", "P4"]
    supported: bool
    correct_reply_language: bool
    safe_to_close: bool
    english_translation: str = Field(default="", max_length=5000)
    handoff_note_is_english: bool = True
    # English observation, never a copy of payment details.
    explanation: str = Field(min_length=1, max_length=600)
