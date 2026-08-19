import json
import os
from typing import List, Optional

from pydantic import BaseModel, ValidationError, field_validator
from emergentintegrations.llm.chat import LlmChat, UserMessage

from . import load_prompt
from . import tools

MODEL = "gpt-5.5"
ALLOWED_TYPES = ("text", "single_choice", "multi_choice", "scale")


class IntakeQuestion(BaseModel):
    question_id: str
    text: str
    type: str
    options: Optional[List[str]] = None
    required: bool = False

    @field_validator("type")
    @classmethod
    def known_type(cls, v):
        if v not in ALLOWED_TYPES:
            raise ValueError(f"unknown question type {v}")
        return v


class IntakeForm(BaseModel):
    questions: List[IntakeQuestion]

    @field_validator("questions")
    @classmethod
    def bounded(cls, v):
        if not 5 <= len(v) <= 8:
            raise ValueError("expected between 5 and 8 questions")
        if sum(1 for q in v if q.type == "text") > 2:
            raise ValueError("at most two free-text questions")
        return v


class IntakeAgent:
    agent_type = "intake_form"
    model = MODEL

    def __init__(self):
        self.system_prompt, self.prompt_version = load_prompt("intake_v1.md")

    async def run(self, db, *, patient_user_id, encounter_id, profile_id, encounter=None):
        import server

        profile, profile_ids = await tools.get_health_profile(db, patient_user_id)
        meds, med_ids = await tools.get_medications_with_adherence(db, profile_id, days=30)
        alerts, alert_ids = await tools.get_recent_alerts(db, patient_user_id, days=30)

        context = {
            "patient_health_profile": profile,
            "active_medications": [m["name"] for m in meds["medications"]],
            "recent_alerts": alerts["alerts"],
            "reason_for_visit": (encounter or {}).get("reason_for_visit") or "",
        }
        chat = LlmChat(
            api_key=os.environ["EMERGENT_LLM_KEY"],
            session_id=f"intake_{encounter_id}",
            system_message=self.system_prompt,
        ).with_model("openai", MODEL)

        result = await chat.send_message(UserMessage(
            text="Patient context (JSON):\n" + json.dumps(context, default=str)
                 + "\n\nReturn the questionnaire JSON."
        ))
        parsed = server.parse_llm_json(result)
        try:
            form = IntakeForm(**(parsed or {}))
        except (ValidationError, TypeError):
            repair = await chat.send_message(UserMessage(
                text="That response did not match the required schema. Return ONLY valid JSON with a "
                     "`questions` array of 5-8 items, each with question_id, text, type "
                     "(text|single_choice|multi_choice|scale), options (or null) and required. "
                     "At most two `text` questions."
            ))
            form = IntakeForm(**(server.parse_llm_json(repair) or {}))

        input_refs = {"users": profile_ids, "medications": med_ids, "alerts": alert_ids}
        return {"questions": [q.model_dump() for q in form.questions]}, input_refs
