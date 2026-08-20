"""Hosted speech-to-text provider. Swapped in with TRANSCRIPTION_PROVIDER=hosted."""
import math
import os

from emergentintegrations.llm.openai import OpenAISpeechToText

MODEL = "whisper-1"


def _confidence(segment) -> float:
    logprob = getattr(segment, "avg_logprob", None)
    if logprob is None:
        return 0.7
    return round(min(1.0, max(0.0, math.exp(logprob))), 3)


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

        segments = []
        for s in getattr(result, "segments", None) or []:
            segments.append({
                "start": round(float(getattr(s, "start", 0.0)), 2),
                "end": round(float(getattr(s, "end", 0.0)), 2),
                "text": getattr(s, "text", "").strip(),
                "confidence": _confidence(s),
            })
        overall = round(sum(s["confidence"] for s in segments) / len(segments), 3) if segments else 0.0
        language = getattr(result, "language", None) or (language_hint or "ar")
        return {
            "text": getattr(result, "text", ""),
            "segments": segments,
            "overall_confidence": overall,
            "detected_languages": [language],
        }
