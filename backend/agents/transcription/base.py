from typing import Protocol


class Transcriber(Protocol):
    async def transcribe(self, audio_path: str, language_hint: str = "ar-SA") -> dict:
        """Returns {
            "text": str,
            "segments": [{"start": float, "end": float, "text": str, "confidence": float}],
            "overall_confidence": float,
            "detected_languages": [str],
        }"""
