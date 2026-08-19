import json
import os
from typing import List, Optional

from pydantic import BaseModel, ValidationError
from emergentintegrations.llm.chat import LlmChat, UserMessage

from . import load_prompt
from .previsit import MODEL, gather_context


class CitedRecord(BaseModel):
    collection: str
    id: str
    summary: str = ""


class QAResponse(BaseModel):
    answer: str = ""
    cited_records: List[CitedRecord] = []
    refused: bool = False
    refusal_reason: Optional[str] = None


class BriefingQAAgent:
    agent_type = "briefing_qa"
    model = MODEL

    def __init__(self):
        self.system_prompt, self.prompt_version = load_prompt("briefing_qa_v1.md")

    async def run(self, db, *, patient_user_id, encounter_id, profile_id, artifact, question, history=None):
        import server

        context, input_refs, _ = await gather_context(db, patient_user_id, profile_id, None, encounter_id)
        briefing = artifact.get("edited_content") or artifact.get("content")
        context["briefing"] = {"artifact_id": artifact["artifact_id"], "status": artifact["status"], "content": briefing}

        prior = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in (history or [])[-10:] if not m.get("refused")
        )
        chat = LlmChat(
            api_key=os.environ["EMERGENT_LLM_KEY"],
            session_id=f"briefqa_{artifact['artifact_id']}",
            system_message=self.system_prompt,
        ).with_model("openai", MODEL)

        prompt = (
            "Patient record and briefing (JSON):\n" + json.dumps(context, default=str)
            + (f"\n\nEarlier turns in this thread:\n{prior}" if prior else "")
            + f"\n\nClinician question: {question}\n\nReturn the JSON response."
        )
        result = await chat.send_message(UserMessage(text=prompt))
        parsed = server.parse_llm_json(result)
        try:
            answer = QAResponse(**(parsed or {}))
        except (ValidationError, TypeError):
            answer = QAResponse(answer="", refused=False)

        needs_retry = (not answer.refused and answer.answer and not answer.cited_records) or (
            not answer.refused and not answer.answer
        )
        if needs_retry:
            retry = await chat.send_message(UserMessage(
                text="Your response was invalid: a factual answer must include at least one entry in "
                     "cited_records using document ids from the supplied context, or set refused true "
                     "with a refusal_reason. Return ONLY the corrected JSON."
            ))
            try:
                answer = QAResponse(**(server.parse_llm_json(retry) or {}))
            except (ValidationError, TypeError):
                pass

        input_refs["clinical_artifacts"] = [artifact["artifact_id"]]
        return answer.model_dump(), input_refs
