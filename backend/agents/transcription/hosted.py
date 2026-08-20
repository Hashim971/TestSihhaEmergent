"""Hosted speech-to-text provider. Swapped in with TRANSCRIPTION_PROVIDER=hosted."""
import math
import os

from emergentintegrations.llm.openai import OpenAISpeechToText

MODEL = "whisper-1"


def _field(segment, key, default=None):
    if isinstance(segment, dict):
        return segment.get(key, default)
    return getattr(segment, key, default)


def _confidence(segment) -> float:
    logprob = _field(segment, "avg_logprob")
    if logprob is None:
        return 0.7
    return round(min(1.0, max(0.0, math.exp(float(logprob)))), 3)


class HostedTranscriber:
    async def transcribe(self, audio_path: str, language_hint: str = "ar-SA") -> dict:
        client = OpenAISpeechToText(api_key=os.environ["EMERGENT_LLM_KEY"])
        with open(audio_path, "rb") as fh:
            result = await client.transcribe(
                file=fh,
                model=MODEL,
                response_format="verbose_json",
                language=(language_hint or "ar").split("-")[0],
                prompt="Clinical consultation in Saudi dialect Arabic with English drug and procedure names.",
                temperature=0.0,
                timestamp_granularities=["segment"],
            )

        raw = _field(result, "segments") or []
        segments = []
        for s in raw:
            text = (_field(s, "text") or "").strip()
            if not text:
                continue
            segments.append({
                "start": round(float(_field(s, "start", 0.0) or 0.0), 2),
                "end": round(float(_field(s, "end", 0.0) or 0.0), 2),
                "text": text,
                "confidence": _confidence(s),
            })
        full_text = _field(result, "text") or ""
        if not segments and full_text.strip():
            segments = [{"start": 0.0, "end": float(_field(result, "duration", 0.0) or 0.0),
                         "text": full_text.strip(), "confidence": 0.7}]
        overall = round(sum(s["confidence"] for s in segments) / len(segments), 3) if segments else 0.0
        language = _field(result, "language") or (language_hint or "ar")
        return {
            "text": full_text,
            "segments": segments,
            "overall_confidence": overall,
            "detected_languages": [language],
        }
