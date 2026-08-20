"""Transcription provider selection. Agents and routes never name a vendor."""
import os

CONFIDENCE_THRESHOLD = float(os.environ.get("TRANSCRIPTION_CONFIDENCE_THRESHOLD", "0.65"))


def get_transcriber():
    provider = os.environ.get("TRANSCRIPTION_PROVIDER", "stub").strip().lower()
    if provider == "stub":
        from .stub import StubTranscriber
        return StubTranscriber()
    if provider == "hosted":
        from .hosted import HostedTranscriber
        return HostedTranscriber()
    raise RuntimeError(f"Unknown TRANSCRIPTION_PROVIDER: {provider}")
