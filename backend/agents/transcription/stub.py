"""Fixture-backed transcriber so the whole scribe pipeline runs with no provider and no cost."""
import json
import os
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


class StubTranscriber:
    async def transcribe(self, audio_path: str, language_hint: str = "ar-SA") -> dict:
        name = os.environ.get("TRANSCRIPTION_STUB_FIXTURE", "consultation_ar_sa.json")
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
