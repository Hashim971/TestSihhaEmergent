import json
import os
from typing import List

from pydantic import BaseModel, ValidationError
from emergentintegrations.llm.chat import LlmChat, UserMessage

from . import load_prompt
from . import tools

MODEL = "gpt-5.5"


class SummaryMedication(BaseModel):
    name: str
    instructions: str = ""


class SummaryBody(BaseModel):
    what_we_discussed: str = ""
    diagnosis_plain: str = ""
    medications: List[SummaryMedication] = []
    next_steps: List[str] = []
    red_flags: List[str] = []


class PatientVisitSummary(BaseModel):
    ar: SummaryBody = SummaryBody()
    en: SummaryBody = SummaryBody()


class PatientSummaryAgent:
    agent_type = "patient_summary"
    model = MODEL

    def __init__(self):
        self.system_prompt, self.prompt_version = load_prompt("patient_summary_v1.md")

    async def run(self, db, *, patient_user_id, encounter_id, note, source_artifact_id,
                  reason_for_visit=None):
        import server

        profile, profile_ids = await tools.get_health_profile(db, patient_user_id)
        context = {
            "patient_first_name": (profile or {}).get("name"),
            "reason_for_visit": reason_for_visit,
            "signed_note": note,
        }
        chat = LlmChat(
            api_key=os.environ["EMERGENT_LLM_KEY"],
            session_id=f"patient_summary_{encounter_id}",
            system_message=self.system_prompt,
        ).with_model("openai", MODEL)

        result = await chat.send_message(UserMessage(
            text="Signed visit context (JSON):\n" + json.dumps(context, default=str, ensure_ascii=False)
                 + "\n\nReturn the patient summary JSON."
        ))
        parsed = server.parse_llm_json(result)
        try:
            summary = PatientVisitSummary(**(parsed or {}))
        except (ValidationError, TypeError):
            repair = await chat.send_message(UserMessage(
                text="That response did not match the required schema. Return ONLY valid JSON with top-level "
                     "keys \"ar\" and \"en\", each holding what_we_discussed, diagnosis_plain, medications, "
                     "next_steps and red_flags."
            ))
            summary = PatientVisitSummary(**(server.parse_llm_json(repair) or {}))

        input_refs = {"users": profile_ids, "clinical_artifacts": [source_artifact_id]}
        return summary.model_dump(), input_refs
