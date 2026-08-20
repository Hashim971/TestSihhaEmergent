"""Phase 3 tests: consent gate, stub-transcribed SOAP note, conflicts, acknowledgement gate, retention.

Run:  cd /app/backend && set -a && . ./.env && set +a && \
      REACT_APP_BACKEND_URL=<preview url> python -m pytest tests/test_phase3_scribe.py -q
"""
import io
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient

API = f"{os.environ['REACT_APP_BACKEND_URL'].rstrip('/')}/api"
LAYLA = {"email": "dr.layla@sihha.ai", "password": "Doctor@123"}
OMAR = {"email": "omar.patient@sihha.ai", "password": "Patient@123"}


@pytest.fixture(scope="module")
def db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=60)
    r.raise_for_status()
    return s, r.json()


@pytest.fixture(scope="module")
def doctor():
    return login(LAYLA)


@pytest.fixture(scope="module", autouse=True)
def stub_provider():
    """These tests upload synthetic bytes, so they always run on the fixture transcriber."""
    adm, _ = login({"email": os.environ.get("ADMIN_EMAIL", "admin@sihha.ai"),
                    "password": os.environ.get("ADMIN_PASSWORD", "Admin@123")})
    before = adm.get(f"{API}/admin/transcription", timeout=60).json()["provider"]
    adm.put(f"{API}/admin/transcription", json={"provider": "stub"}, timeout=60)
    yield
    restore, _ = login({"email": os.environ.get("ADMIN_EMAIL", "admin@sihha.ai"),
                        "password": os.environ.get("ADMIN_PASSWORD", "Admin@123")})
    restore.put(f"{API}/admin/transcription", json={"provider": before}, timeout=60)


@pytest.fixture(scope="module")
def encounter(doctor, db):
    ds, _ = doctor
    _, p = login(OMAR)
    r = ds.post(f"{API}/encounters", json={
        "patient_user_id": p["user_id"],
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "reason_for_visit": "Scribe test consultation",
    }, timeout=60)
    assert r.status_code == 200, r.text
    enc = r.json()
    yield enc
    db.encounters.delete_one({"encounter_id": enc["encounter_id"]})
    db.consultation_audio.delete_many({"encounter_id": enc["encounter_id"]})
    db.clinical_artifacts.delete_many({"encounter_id": enc["encounter_id"]})


def upload_audio(session, encounter_id):
    init = session.post(f"{API}/encounters/{encounter_id}/audio/init", timeout=60)
    assert init.status_code == 200, init.text
    audio_id = init.json()["audio_id"]
    chunk = session.post(f"{API}/audio/{audio_id}/chunk", data={"index": 0},
                         files={"chunk": ("part-0.webm", io.BytesIO(b"\x1aE\xdf\xa3fake-webm-bytes"),
                                          "audio/webm")}, timeout=60)
    assert chunk.status_code == 200, chunk.text
    done = session.post(f"{API}/audio/{audio_id}/complete", data={"duration_seconds": 53.0}, timeout=240)
    return audio_id, done


@pytest.fixture(scope="module")
def note(doctor, encounter):
    ds, _ = doctor
    ds.post(f"{API}/encounters/{encounter['encounter_id']}/consent", json={"granted": True}, timeout=60)
    audio_id, done = upload_audio(ds, encounter["encounter_id"])
    assert done.status_code == 200, done.text
    return audio_id, done.json()


class TestConsentGate:
    def test_upload_refused_without_consent(self, doctor, encounter):
        ds, _ = doctor
        r = ds.post(f"{API}/encounters/{encounter['encounter_id']}/audio/init", timeout=60)
        assert r.status_code == 403
        assert "consent" in r.json()["detail"].lower()

    def test_consent_is_recorded_on_the_encounter(self, doctor, encounter):
        ds, doc = doctor
        r = ds.post(f"{API}/encounters/{encounter['encounter_id']}/consent", json={"granted": True}, timeout=60)
        assert r.status_code == 200
        body = r.json()
        assert body["granted"] is True and body["granted_by"] == doc["user_id"] and body["granted_at"]

    def test_outsider_cannot_grant_consent(self, encounter, db):
        email = f"TEST_scribe_{uuid.uuid4().hex[:8]}@example.com"
        s = requests.Session()
        u = s.post(f"{API}/auth/register", json={"name": "Nosy", "email": email, "password": "Passw0rd!"},
                   timeout=60).json()
        try:
            assert s.post(f"{API}/encounters/{encounter['encounter_id']}/consent",
                          json={"granted": True}, timeout=60).status_code == 403
        finally:
            db.users.delete_one({"user_id": u["user_id"]})


class TestScribePipeline:
    def test_stub_transcriber_produces_a_complete_note(self, note):
        _, artifact = note
        assert artifact["artifact_type"] == "soap_note" and artifact["status"] == "draft"
        c = artifact["content"]
        assert c["subjective"]["chief_complaint"]
        assert c["transcript_quality"] in ("good", "fair", "poor")
        assert c["objective"]["vitals"], "vitals must be present"
        assert isinstance(c["plan"]["actions"], list)

    def test_vitals_come_from_the_database_and_conflicts_are_flagged(self, note):
        _, artifact = note
        vitals = artifact["content"]["objective"]["vitals"]
        assert any(v["source"] == "recorded" for v in vitals), "recorded vitals must be included"
        stated = [v for v in vitals if v["source"] == "stated"]
        assert stated, "the transcript states a blood pressure, so a stated entry is required"
        assert any(v.get("conflict") for v in vitals), "the disagreement must be described, not resolved silently"

    def test_low_confidence_segments_are_surfaced(self, note):
        _, artifact = note
        segs = artifact["content"]["low_confidence_segments"]
        assert segs, "the fixture contains two unclear passages"
        assert all(s["confidence"] <= 0.65 for s in segs), segs

    def test_audio_row_holds_transcript_and_retention(self, note, db):
        audio_id, _ = note
        audio = db.consultation_audio.find_one({"audio_id": audio_id}, {"_id": 0})
        assert audio["transcription_status"] == "complete"
        assert audio["transcript"]["segments"] and audio["consent_recorded_at"]
        assert audio["retention_expires_at"] > audio["created_at"]
        assert Path(audio["storage_path"]).exists()
        assert audio["size_bytes"] > 0

    def test_agent_run_holds_no_audio_bytes(self, note, db):
        _, artifact = note
        run = db.agent_runs.find_one({"agent_run_id": artifact["agent_run_id"]}, {"_id": 0})
        assert run["agent_type"] == "soap_note" and run["status"] == "success"
        assert run["prompt_version"] == "v1"
        blob = str(run)
        assert "webm" not in blob and "base64" not in blob
        assert run["input_refs"]["consultation_audio"], "the audio is referenced by id only"
        assert run["input_refs"]["vitals"]

    def test_signing_blocked_until_every_segment_acknowledged(self, doctor, note):
        ds, _ = doctor
        _, artifact = note
        aid = artifact["artifact_id"]
        segs = artifact["content"]["low_confidence_segments"]

        blocked = ds.post(f"{API}/artifacts/{aid}/sign", timeout=60)
        assert blocked.status_code == 409
        assert "acknowledge" in blocked.json()["detail"].lower()

        for i in range(len(segs) - 1):
            assert ds.post(f"{API}/artifacts/{aid}/acknowledge", json={"index": i}, timeout=60).status_code == 200
        assert ds.post(f"{API}/artifacts/{aid}/sign", timeout=60).status_code == 409

        last = ds.post(f"{API}/artifacts/{aid}/acknowledge", json={"index": len(segs) - 1}, timeout=60)
        assert last.status_code == 200
        assert sorted(last.json()["acknowledged_segments"]) == list(range(len(segs)))

        signed = ds.post(f"{API}/artifacts/{aid}/sign", timeout=60)
        assert signed.status_code == 200 and signed.json()["status"] == "signed"

    def test_bad_segment_index_rejected(self, doctor, note):
        ds, _ = doctor
        _, artifact = note
        assert ds.post(f"{API}/artifacts/{artifact['artifact_id']}/acknowledge",
                       json={"index": 99}, timeout=60).status_code == 400

    def test_soap_endpoint_returns_note_and_consent(self, doctor, encounter, note):
        ds, _ = doctor
        r = ds.get(f"{API}/encounters/{encounter['encounter_id']}/soap", timeout=60)
        assert r.status_code == 200
        body = r.json()
        assert body["consent"]["granted"] is True
        assert body["note"]["artifact_type"] == "soap_note"
        assert body["audio"]["transcription_status"] == "complete"


class TestRetention:
    def test_expired_audio_is_purged_but_metadata_survives(self, note, db):
        audio_id, _ = note
        path = db.consultation_audio.find_one({"audio_id": audio_id})["storage_path"]
        db.consultation_audio.update_one(
            {"audio_id": audio_id},
            {"$set": {"retention_expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}},
        )
        adm, _ = login({"email": os.environ.get("ADMIN_EMAIL", "admin@sihha.ai"),
                        "password": os.environ.get("ADMIN_PASSWORD", "Admin@123")})
        r = adm.post(f"{API}/admin/audio/purge", timeout=120)
        assert r.status_code == 200 and r.json()["purged"] >= 1

        row = db.consultation_audio.find_one({"audio_id": audio_id}, {"_id": 0})
        assert row is not None, "the metadata row must survive for audit"
        assert row["storage_path"] is None and row["deleted_at"]
        assert row["consent_recorded_at"] and row["encounter_id"]
        assert not Path(path).exists(), "audio bytes must be gone from storage"

    def test_purge_requires_admin(self, doctor):
        ds, _ = doctor
        assert ds.post(f"{API}/admin/audio/purge", timeout=60).status_code == 403


class TestProviderAbstraction:
    def test_no_vendor_name_in_agent_or_routes(self):
        root = Path(__file__).parent.parent
        for name in ("agents/scribe.py", "server.py"):
            text = (root / name).read_text(encoding="utf-8").lower()
            assert "whisper" not in text, f"{name} names a vendor"
            assert "openaispeechtotext" not in text, f"{name} names a vendor"

    def test_both_providers_expose_the_same_interface(self):
        from agents.transcription.stub import StubTranscriber
        from agents.transcription.hosted import HostedTranscriber
        for impl in (StubTranscriber, HostedTranscriber):
            assert hasattr(impl, "transcribe")

    def test_selection_is_environment_driven(self, monkeypatch):
        from agents.transcription import get_transcriber
        from agents.transcription.stub import StubTranscriber
        monkeypatch.setenv("TRANSCRIPTION_PROVIDER", "stub")
        assert isinstance(get_transcriber(), StubTranscriber)
        monkeypatch.setenv("TRANSCRIPTION_PROVIDER", "nope")
        with pytest.raises(RuntimeError):
            get_transcriber()
