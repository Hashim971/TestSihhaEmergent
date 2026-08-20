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
    intake_refs: List[str] = []
    screening_refs: List[str] = []


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


async def gather_context(db, patient_user_id, profile_id, encounter=None, encounter_id=None):
    profile, profile_ids = await tools.get_health_profile(db, patient_user_id)
    vitals, vital_ids = await tools.get_vitals_summary(db, profile_id, days=90)
    meds, med_ids = await tools.get_medications_with_adherence(db, profile_id, days=90)
    alerts, alert_ids = await tools.get_recent_alerts(db, patient_user_id, days=90)
    reports, report_ids = await tools.get_recent_screening_reports(
        db, patient_user_id, limit=3, encounter_id=encounter_id)
    timeline, _ = await tools.get_symptom_timeline(db, patient_user_id, days=180)
    interactions, _ = await tools.get_interaction_flags(db, profile_id)
    intake, intake_ids = await tools.get_intake_responses(db, encounter_id) if encounter_id else ({}, [])

    context = {
        "patient": profile,
        "reason_for_visit": (encounter or {}).get("reason_for_visit") or "",
        "scheduled_at": (encounter or {}).get("scheduled_at"),
        "vitals_summary": vitals,
        "medications": meds,
        "alerts": alerts,
        "screening_reports": reports,
        "symptom_timeline": timeline,
        "intake": intake,
        "interaction_reference": interactions,
    }
    input_refs = {
        "vitals": vital_ids, "medications": med_ids,
        "alerts": alert_ids, "health_reports": report_ids, "users": profile_ids,
        "intake_forms": intake_ids,
    }
    return context, input_refs, interactions


class PreVisitBriefingAgent:
    agent_type = "previsit_brief"
    model = MODEL

    def __init__(self):
        self.system_prompt, self.prompt_version = load_prompt("previsit_v4.md")

    async def run(self, db, *, patient_user_id, encounter_id, profile_id, encounter=None):
        import server

        context, input_refs, _ = await gather_context(db, patient_user_id, profile_id, encounter, encounter_id)
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

        # A citation must point at a finding or intake answer that actually exists in the record.
        valid_findings = {f.get("finding_id") for r in context["screening_reports"]["reports"]
                          for f in (r.get("findings") or [])}
        valid_intake = {a.get("question_id") for a in (context["intake"] or {}).get("answered", [])}
        brief_dict = brief.model_dump()
        for concern in brief_dict["chief_concerns"]:
            concern["screening_refs"] = [r for r in concern["screening_refs"] if r in valid_findings]
            concern["intake_refs"] = [r for r in concern["intake_refs"] if r in valid_intake]
        return brief_dict, input_refs
