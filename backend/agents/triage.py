import json
import os
from typing import List

from pydantic import BaseModel, ValidationError, field_validator
from emergentintegrations.llm.chat import LlmChat, UserMessage

from . import load_prompt
from . import tools
from triage import rules

MODEL = "gpt-5.5"


class TriageReason(BaseModel):
    text: str
    finding_ids: List[str] = []


class TriageDisposition(BaseModel):
    level: str = "routine_2w"
    headline: str = ""
    reasons: List[TriageReason] = []
    recommended_specialty: str = "General practice"
    suggested_reason_for_visit: str = ""
    self_care_advice: List[str] = []
    watch_for: List[str] = []
    confidence: str = "medium"

    @field_validator("level")
    @classmethod
    def known_level(cls, v):
        return v if v in rules.LEVELS else "routine_2w"


class TriageAgent:
    """Says how soon a patient should be seen. The deterministic rules always win on the way down."""
    agent_type = "triage_disposition"
    model = MODEL

    def __init__(self):
        self.system_prompt, self.prompt_version = load_prompt("triage_v1.md")

    async def run(self, db, *, patient_user_id, encounter_id, report, profile_id):
        import server

        findings = report.get("findings") or []
        profile, profile_ids = await tools.get_health_profile(db, patient_user_id)
        vitals, vital_ids = await tools.get_vitals_summary(db, profile_id, days=30)
        flags = rules.detect_red_flags(findings, vitals)
        floor = rules.floor_level(flags)

        context = {
            "patient": profile,
            "screening_report": (report.get("content") or "")[:5000],
            "findings": findings,
            "vitals": vitals.get("metrics"),
            "safety_rules_already_flagged": flags,
            "minimum_level_from_safety_rules": floor,
        }
        chat = LlmChat(
            api_key=os.environ["EMERGENT_LLM_KEY"],
            session_id=f"triage_{report['report_id']}",
            system_message=self.system_prompt,
        ).with_model("openai", MODEL)

        result = await chat.send_message(UserMessage(
            text="Screening context (JSON):\n" + json.dumps(context, default=str, ensure_ascii=False)
                 + "\n\nReturn the triage JSON."
        ))
        parsed = server.parse_llm_json(result)
        try:
            disposition = TriageDisposition(**(parsed or {}))
        except (ValidationError, TypeError):
            repair = await chat.send_message(UserMessage(
                text="That response did not match the required schema. Return ONLY valid JSON with keys "
                     "level, headline, reasons, recommended_specialty, suggested_reason_for_visit, "
                     "self_care_advice, watch_for and confidence."
            ))
            disposition = TriageDisposition(**(server.parse_llm_json(repair) or {}))

        out = disposition.model_dump()
        valid_findings = {f.get("finding_id") for f in findings}
        for reason in out["reasons"]:
            reason["finding_ids"] = [fid for fid in reason["finding_ids"] if fid in valid_findings]

        # The safety floor is not negotiable, and every flag must be visible to the patient.
        model_level = out["level"]
        out["model_level"] = model_level
        out["rule_floor"] = floor
        out["level"] = rules.highest(model_level, floor)
        out["escalated_by_rules"] = out["level"] != model_level
        out["red_flags"] = flags
        out["timeframe"] = rules.TIMEFRAMES[out["level"]]
        out["emergency_number"] = rules.EMERGENCY_NUMBER
        if out["level"] == "emergency_now":
            out["self_care_advice"] = []
        cited = {r["text"] for r in out["reasons"]}
        for flag in flags:
            text = f"{flag['label']} — {flag['guidance']}"
            if text not in cited:
                out["reasons"].append({"text": text,
                                       "finding_ids": [flag["finding_id"]] if flag.get("finding_id") else []})

        input_refs = {"users": profile_ids, "vitals": vital_ids, "health_reports": [report["report_id"]]}
        return out, input_refs
