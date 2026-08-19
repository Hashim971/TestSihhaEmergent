import json
import os
import uuid
from typing import List, Optional

from pydantic import BaseModel, ValidationError, field_validator
from emergentintegrations.llm.chat import LlmChat, UserMessage

from . import load_prompt

MODEL = "gpt-5.5"
SEVERITIES = ("mild", "moderate", "severe", "unclear")


class ScreeningFinding(BaseModel):
    symptom: str
    onset: Optional[str] = None
    duration: Optional[str] = None
    severity: str = "unclear"
    patient_words: str
    source_message_ids: List[str] = []

    @field_validator("severity")
    @classmethod
    def known_severity(cls, v):
        return v if v in SEVERITIES else "unclear"


class ScreeningFindings(BaseModel):
    findings: List[ScreeningFinding] = []


class ScreeningExtractionAgent:
    """Turns a free-text screening report into citable, structured findings."""
    agent_type = "screening_extract"
    model = MODEL

    def __init__(self):
        self.system_prompt, self.prompt_version = load_prompt("screening_extract_v1.md")

    async def run(self, db, *, patient_user_id, encounter_id, report):
        import server

        messages = await db.chat_messages.find(
            {"chat_session_id": report["chat_session_id"]},
            {"_id": 0, "message_id": 1, "role": 1, "content": 1},
        ).sort("created_at", 1).to_list(200)
        transcript = [{"message_id": m.get("message_id"), "role": m["role"], "content": m["content"]}
                      for m in messages]
        valid_ids = {m["message_id"] for m in transcript if m.get("message_id")}

        chat = LlmChat(
            api_key=os.environ["EMERGENT_LLM_KEY"],
            session_id=f"screening_extract_{report['report_id']}",
            system_message=self.system_prompt,
        ).with_model("openai", MODEL)

        result = await chat.send_message(UserMessage(
            text="Screening report:\n" + (report.get("content") or "")[:6000]
                 + "\n\nTranscript (JSON):\n" + json.dumps(transcript, default=str)
                 + "\n\nReturn the findings JSON."
        ))
        parsed = server.parse_llm_json(result)
        try:
            extracted = ScreeningFindings(**(parsed or {}))
        except (ValidationError, TypeError):
            repair = await chat.send_message(UserMessage(
                text="That response did not match the required schema. Return ONLY valid JSON with a "
                     "`findings` array; each item needs symptom, onset, duration, severity, patient_words "
                     "and source_message_ids."
            ))
            extracted = ScreeningFindings(**(server.parse_llm_json(repair) or {}))

        findings = []
        for f in extracted.findings:
            item = f.model_dump()
            item["finding_id"] = f"find_{uuid.uuid4().hex[:10]}"
            item["report_id"] = report["report_id"]
            item["source_message_ids"] = [m for m in item["source_message_ids"] if m in valid_ids]
            findings.append(item)

        return {"findings": findings}, {"health_reports": [report["report_id"]]}
