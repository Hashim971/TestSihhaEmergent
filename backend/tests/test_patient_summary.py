"""Note to the patient: plain-language visit summary drafted from a signed SOAP note.

Run:  cd /app/backend && set -a && . ./.env && set +a && \
      REACT_APP_BACKEND_URL=<preview url> python -m pytest tests/test_patient_summary.py -q
"""
import io
import os
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

API = f"{os.environ['REACT_APP_BACKEND_URL'].rstrip('/')}/api"
LAYLA = {"email": "dr.layla@sihha.ai", "password": "Doctor@123"}
OMAR = {"email": "omar.patient@sihha.ai", "password": "Patient@123"}
ADMIN = {"email": os.environ.get("ADMIN_EMAIL", "admin@sihha.ai"),
         "password": os.environ.get("ADMIN_PASSWORD", "Admin@123")}


def login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=60)
    r.raise_for_status()
    return s, r.json()


@pytest.fixture(scope="module")
def db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module", autouse=True)
def stub_provider():
    adm, _ = login(ADMIN)
    before = adm.get(f"{API}/admin/transcription", timeout=60).json()["provider"]
    adm.put(f"{API}/admin/transcription", json={"provider": "stub"}, timeout=60)
    yield
    restore, _ = login(ADMIN)
    restore.put(f"{API}/admin/transcription", json={"provider": before}, timeout=60)


@pytest.fixture(scope="module")
def signed_note(db):
    ds, _ = login(LAYLA)
    ps, patient = login(OMAR)
    enc = ds.post(f"{API}/encounters", json={
        "patient_user_id": patient["user_id"],
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat(),
        "reason_for_visit": "Patient summary test consultation",
    }, timeout=60).json()
    eid = enc["encounter_id"]
    ds.post(f"{API}/encounters/{eid}/consent", json={"granted": True}, timeout=60)
    audio_id = ds.post(f"{API}/encounters/{eid}/audio/init", timeout=60).json()["audio_id"]
    ds.post(f"{API}/audio/{audio_id}/chunk", data={"index": 0},
            files={"chunk": ("part-0.webm", io.BytesIO(b"\x1aE\xdf\xa3fake-webm"), "audio/webm")}, timeout=60)
    note = ds.post(f"{API}/audio/{audio_id}/complete", data={"duration_seconds": 61.0}, timeout=240).json()
    aid = note["artifact_id"]
    for i in range(len(note["content"].get("low_confidence_segments") or [])):
        ds.post(f"{API}/artifacts/{aid}/acknowledge", json={"index": i}, timeout=60)
    signed = ds.post(f"{API}/artifacts/{aid}/sign", timeout=60)
    assert signed.status_code == 200, signed.text
    yield ds, ps, enc, signed.json()
    db.encounters.delete_one({"encounter_id": eid})
    db.consultation_audio.delete_many({"encounter_id": eid})
    db.clinical_artifacts.delete_many({"encounter_id": eid})
    db.alerts.delete_many({"type": "visit_summary", "user_id": patient["user_id"]})


@pytest.fixture(scope="module")
def summary(signed_note):
    ds, _, _, note = signed_note
    r = ds.post(f"{API}/artifacts/{note['artifact_id']}/patient-summary", timeout=240)
    assert r.status_code == 200, r.text
    return r.json()


class TestDraftGate:
    def test_unsigned_note_cannot_be_summarised(self, db):
        ds, _ = login(LAYLA)
        draft = db.clinical_artifacts.find_one(
            {"artifact_type": "soap_note", "status": {"$ne": "signed"}}, {"_id": 0})
        if not draft:
            pytest.skip("no unsigned soap note available")
        r = ds.post(f"{API}/artifacts/{draft['artifact_id']}/patient-summary", timeout=120)
        assert r.status_code == 409 and "sign" in r.json()["detail"].lower()

    def test_patient_cannot_draft_a_summary(self, signed_note):
        _, ps, _, note = signed_note
        assert ps.post(f"{API}/artifacts/{note['artifact_id']}/patient-summary",
                       timeout=120).status_code == 403


class TestSummaryContent:
    def test_both_languages_are_written(self, summary):
        for lang in ("ar", "en"):
            body = summary["content"][lang]
            assert body["what_we_discussed"].strip(), f"{lang} discussion missing"
            assert body["red_flags"], f"{lang} red flags missing"
            assert len(body["red_flags"]) <= 4

    def test_arabic_is_actually_arabic(self, summary):
        text = summary["content"]["ar"]["what_we_discussed"]
        assert any("\u0600" <= ch <= "\u06ff" for ch in text), text

    def test_starts_as_an_unpublished_draft(self, summary):
        assert summary["artifact_type"] == "patient_summary"
        assert summary["status"] == "draft" and summary["published_at"] is None

    def test_run_is_audited_with_source_reference(self, summary, db):
        run = db.agent_runs.find_one({"agent_run_id": summary["agent_run_id"]}, {"_id": 0})
        assert run["agent_type"] == "patient_summary" and run["status"] == "success"
        assert summary["source_artifact_id"] in run["input_refs"]["clinical_artifacts"]


class TestReviewAndPublish:
    def test_patient_sees_nothing_before_publishing(self, signed_note, summary):
        _, ps, enc, _ = signed_note
        rows = ps.get(f"{API}/patient/visit-summaries", timeout=60).json()
        assert not [r for r in rows if r["encounter_id"] == enc["encounter_id"]]

    def test_doctor_edit_is_kept(self, signed_note, summary):
        ds, _, _, _ = signed_note
        edited = {**summary["content"]}
        edited["en"] = {**edited["en"], "what_we_discussed": "Edited by the doctor before sending."}
        r = ds.patch(f"{API}/artifacts/{summary['artifact_id']}",
                     json={"edited_content": edited}, timeout=60)
        assert r.status_code == 200
        assert r.json()["edited_content"]["en"]["what_we_discussed"].startswith("Edited by the doctor")

    def test_publish_makes_it_visible_and_alerts_the_patient(self, signed_note, summary, db):
        ds, ps, enc, _ = signed_note
        pub = ds.post(f"{API}/artifacts/{summary['artifact_id']}/publish", timeout=60)
        assert pub.status_code == 200
        assert pub.json()["status"] == "published" and pub.json()["published_at"]

        rows = ps.get(f"{API}/patient/visit-summaries", timeout=60).json()
        mine = [r for r in rows if r["encounter_id"] == enc["encounter_id"]]
        assert mine, "the published summary must reach the patient"
        assert mine[0]["reason_for_visit"] == "Patient summary test consultation"
        assert mine[0]["doctor_name"]
        assert mine[0]["edited_content"]["en"]["what_we_discussed"].startswith("Edited by the doctor")

        alerts = list(db.alerts.find({"user_id": mine[0]["patient_user_id"], "type": "visit_summary"}))
        assert alerts and alerts[-1]["severity"] == "info"

    def test_published_summary_is_locked(self, signed_note, summary):
        ds, _, _, note = signed_note
        r = ds.patch(f"{API}/artifacts/{summary['artifact_id']}",
                     json={"edited_content": {"ar": {}, "en": {}}}, timeout=60)
        assert r.status_code == 409
        again = ds.post(f"{API}/artifacts/{summary['artifact_id']}/publish", timeout=60)
        assert again.status_code == 409
        redraft = ds.post(f"{API}/artifacts/{note['artifact_id']}/patient-summary", timeout=120)
        assert redraft.status_code == 409 and "already sent" in redraft.json()["detail"].lower()

    def test_another_patient_cannot_read_it(self, summary):
        os_, _ = login({"email": "sami.patient@sihha.ai", "password": "Patient@123"})
        rows = os_.get(f"{API}/patient/visit-summaries", timeout=60).json()
        assert summary["artifact_id"] not in [r["artifact_id"] for r in rows]


class TestProviderSwitch:
    def test_provider_switch_is_admin_only(self):
        ds, _ = login(LAYLA)
        assert ds.put(f"{API}/admin/transcription", json={"provider": "stub"}, timeout=60).status_code == 403

    def test_unknown_provider_rejected(self):
        adm, _ = login(ADMIN)
        assert adm.put(f"{API}/admin/transcription", json={"provider": "nope"},
                       timeout=60).status_code == 400
