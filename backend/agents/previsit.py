import json
import os
import uuid
from typing import List, Optional

from pydantic import BaseModel, ValidationError
from emergentintegrations.llm.chat import LlmChat, UserMessage

from . import load_prompt
from . import tools

MODEL = "gpt-5.5"


class ChiefConcern(BaseModel):
    concern: str
    evidence: str
    priority: str


class VitalLine(BaseModel):
    metric: str
    current: str
    trend: str
    note: str = ""


class MedicationLine(BaseModel):
    medication: str
    adherence_pct: Optional[float] = None
    flag: str = "none"
    note: str = ""


class PreVisitBrief(BaseModel):
    headline: str
    chief_concerns: List[ChiefConcern] = []
    vitals_summary: List[VitalLine] = []
    medication_review: List[MedicationLine] = []
    suggested_discussion_points: List[str] = []
    data_gaps: List[str] = []
    confidence: str


async def gather_context(db, patient_user_id, profile_id, encounter=None):
    profile, profile_ids = await tools.get_health_profile(db, patient_user_id)
    vitals, vital_ids = await tools.get_vitals_summary(db, profile_id, days=90)
    meds, med_ids = await tools.get_medications_with_adherence(db, profile_id, days=90)
    alerts, alert_ids = await tools.get_recent_alerts(db, patient_user_id, days=90)
    reports, report_ids = await tools.get_recent_screening_reports(db, patient_user_id, limit=3)
    interactions, _ = await tools.get_interaction_flags(db, profile_id)

    context = {
        "patient": profile,
        "reason_for_visit": (encounter or {}).get("reason_for_visit") or "",
        "scheduled_at": (encounter or {}).get("scheduled_at"),
        "vitals_summary": vitals,
        "medications": meds,
        "alerts": alerts,
        "screening_reports": reports,
        "interaction_reference": interactions,
    }
    input_refs = {
        "vitals": vital_ids, "medications": med_ids,
        "alerts": alert_ids, "health_reports": report_ids, "users": profile_ids,
    }
    return context, input_refs, interactions


class PreVisitBriefingAgent:
    agent_type = "previsit_brief"
    model = MODEL

    def __init__(self):
        self.system_prompt, self.prompt_version = load_prompt("previsit_v1.md")

    async def run(self, db, *, patient_user_id, encounter_id, profile_id, encounter=None):
        import server

        context, input_refs, _ = await gather_context(db, patient_user_id, profile_id, encounter)
        payload = json.dumps(context, default=str)

        chat = LlmChat(
            api_key=os.environ["EMERGENT_LLM_KEY"],
            session_id=f"previsit_{encounter_id or uuid.uuid4().hex[:8]}",
            system_message=self.system_prompt,
        ).with_model("openai", MODEL)

        result = await chat.send_message(UserMessage(
            text="Patient record snapshot (JSON):\n" + payload + "\n\nReturn the briefing JSON."
        ))
        parsed = server.parse_llm_json(result)
        try:
            brief = PreVisitBrief(**(parsed or {}))
        except (ValidationError, TypeError):
            repair = await chat.send_message(UserMessage(
                text="That response did not match the required schema. Return ONLY valid JSON with keys "
                     "headline, chief_concerns, vitals_summary, medication_review, "
                     "suggested_discussion_points, data_gaps, confidence."
            ))
            brief = PreVisitBrief(**(server.parse_llm_json(repair) or {}))

        return brief.model_dump(), input_refs
