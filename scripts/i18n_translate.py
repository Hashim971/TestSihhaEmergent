"""Translates the extracted UI strings to Saudi-friendly Modern Standard Arabic with the Emergent LLM key."""
import asyncio
import json
import os
import pathlib
import uuid

from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage

load_dotenv("/app/backend/.env")
SRC = pathlib.Path("/app/frontend/src/i18n/strings_en.json")
OUT = pathlib.Path("/app/frontend/src/i18n/ar.json")
PROMPT = (
    "You translate UI strings of a Saudi healthcare web app (patients, doctors, hospital admins) from English to "
    "clear Modern Standard Arabic suitable for Saudi users. Keep brand names (Sihha AI), product codes, units (mg, SAR), "
    "IDs, emails, URLs and placeholders like {x} unchanged. Keep it concise like UI text. Medical terms must be accurate "
    "(SOAP note = ملاحظة SOAP, triage = الفرز). Reply ONLY with a JSON object mapping each English string to Arabic."
)


async def translate(batch):
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"i18n-{uuid.uuid4().hex}",
                   system_message=PROMPT).with_model("openai", "gpt-5.2")
    reply = await chat.send_message(UserMessage(text=json.dumps(batch, ensure_ascii=False)))
    text = reply.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


async def main():
    strings = json.loads(SRC.read_text(encoding="utf-8"))
    done = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    todo = [s for s in strings if s not in done]
    batches = [todo[i:i + 80] for i in range(0, len(todo), 80)]
    sem = asyncio.Semaphore(6)

    async def run(b):
        async with sem:
            for attempt in range(3):
                try:
                    return await translate(b)
                except Exception as exc:
                    print("retry", attempt, type(exc).__name__)
            return {}

    for result in await asyncio.gather(*(run(b) for b in batches)):
        done.update({k: v for k, v in result.items() if isinstance(v, str)})
    OUT.write_text(json.dumps(done, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    print(f"{len(done)} translated, {len([s for s in strings if s not in done])} missing")


asyncio.run(main())
