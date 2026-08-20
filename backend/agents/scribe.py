import json
import os
from typing import List, Optional

from pydantic import BaseModel, ValidationError
from emergentintegrations.llm.chat import LlmChat, UserMessage

from . import load_prompt
from . import tools
from .transcription import CONFIDENCE_THRESHOLD

MODEL = "gpt-5.5"


class Subjective(BaseModel):
    chief_complaint: str = ""
    hpi: str = ""
    review_of_systems: str = ""


class VitalEntry(BaseModel):
    metric: str
    value: str
    source: str = "recorded"
    conflict: Optional[str] = None


class Objective(BaseModel):
    vitals: List[VitalEntry] = []
    exam_findings: str = ""


class Plan(BaseModel):
    actions: List[str] = []
    medications_discussed: List[str] = []
    followup: str = ""


class LowConfidenceSegment(BaseModel):
    text: str
    confidence: float = 0.0
    affects_section: str = ""


class SoapNote(BaseModel):
    subjective: Subjective = Subjective()
    objective: Objective = Objective()
    assessment: str = ""
    plan: Plan = Plan()
    low_confidence_segments: List[LowConfidenceSegment] = []
    transcript_quality: str = "fair"


class ScribeAgent:
    agent_type = "soap_note"
    model = MODEL

    def __init__(self):
        self.system_prompt, self.prompt_version = load_prompt("scribe_v1.md")

    async def run(self, db, *, patient_user_id, encounter_id, profile_id, transcript, audio_id=None):
        import server

        profile, profile_ids = await tools.get_health_profile(db, patient_user_id)
        vitals, vital_ids = await tools.get_vitals_summary(db, profile_id, days=90)
        meds, med_ids = await tools.get_medications_with_adherence(db, profile_id, days=90)

        context = {
            "patient": profile,
            "recorded_vitals": vitals,
            "active_medications": [m["name"] for m in meds["medications"]],
            "confidence_threshold": CONFIDENCE_THRESHOLD,
            "transcript": {
                "overall_confidence": transcript.get("overall_confidence"),
                "detected_languages": transcript.get("detected_languages"),
                "segments": transcript.get("segments"),
            },
        }
        chat = LlmChat(
            api_key=os.environ["EMERGENT_LLM_KEY"],
            session_id=f"scribe_{encounter_id}",
            system_message=self.system_prompt,
        ).with_model("openai", MODEL)

        result = await chat.send_message(UserMessage(
            text="Consultation context (JSON):\n" + json.dumps(context, default=str, ensure_ascii=False)
                 + "\n\nReturn the SOAP note JSON."
        ))
        parsed = server.parse_llm_json(result)
        try:
            note = SoapNote(**(parsed or {}))
        except (ValidationError, TypeError):
            repair = await chat.send_message(UserMessage(
                text="That response did not match the required schema. Return ONLY valid JSON with keys "
                     "subjective, objective, assessment, plan, low_confidence_segments, transcript_quality."
            ))
            note = SoapNote(**(server.parse_llm_json(repair) or {}))

        input_refs = {"users": profile_ids, "vitals": vital_ids, "medications": med_ids,
                      "consultation_audio": [audio_id] if audio_id else []}
        return note.model_dump(), input_refs
