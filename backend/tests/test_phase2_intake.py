"""Phase 2 tests: Intake Agent, patient questionnaire, and intake-aware briefings.

Run:  cd /app/backend && set -a && . ./.env && set +a && \
      REACT_APP_BACKEND_URL=<preview url> python -m pytest tests/test_phase2_intake.py -q
"""
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

API = f"{os.environ['REACT_APP_BACKEND_URL'].rstrip('/')}/api"
LAYLA = {"email": "dr.layla@sihha.ai", "password": "Doctor@123"}
OMAR = {"email": "omar.patient@sihha.ai", "password": "Patient@123"}
DIAGNOSTIC_WORDS = ("diagnos", "you likely have", "your condition is", "prescrib", "treatment plan",
                    "you may have", "suspect")


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


@pytest.fixture(scope="module")
def patient():
    return login(OMAR)


@pytest.fixture(scope="module")
def encounter(doctor, patient, db):
    ds, _ = doctor
    _, p = patient
    r = ds.post(f"{API}/encounters", json={
        "patient_user_id": p["user_id"],
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
        "reason_for_visit": "Blood pressure review and tiredness (intake test)",
    }, timeout=60)
    assert r.status_code == 200, r.text
    enc = r.json()
    yield enc
    db.encounters.delete_one({"encounter_id": enc["encounter_id"]})
    db.intake_forms.delete_one({"encounter_id": enc["encounter_id"]})


@pytest.fixture(scope="module")
def form(doctor, encounter):
    ds, _ = doctor
    r = ds.post(f"{API}/agents/intake/{encounter['encounter_id']}", timeout=180)
    assert r.status_code == 200, r.text
    return r.json()


class TestIntakeGeneration:
    def test_form_shape_and_question_rules(self, form):
        qs = form["questions"]
        assert 5 <= len(qs) <= 8
        assert form["status"] == "pending" and form["responses"] == []
        assert form["expires_at"] > form["created_at"]
        assert sum(1 for q in qs if q["type"] == "text") <= 2
        assert sum(1 for q in qs if q["required"]) <= 4
        for q in qs:
            assert q["type"] in ("text", "single_choice", "multi_choice", "scale")
            assert q["text"].strip()
            if q["type"] in ("single_choice", "multi_choice"):
                assert q["options"] and len(q["options"]) >= 2
            if q["type"] == "scale":
                assert q["options"] is None

    def test_questions_avoid_diagnostic_language(self, form):
        blob = " ".join(q["text"].lower() for q in form["questions"])
        for word in DIAGNOSTIC_WORDS:
            assert word not in blob, f"diagnostic language in questions: {word}"

    def test_agent_run_logged_with_output_ref(self, db, form):
        run = db.agent_runs.find_one({"agent_run_id": form["agent_run_id"]}, {"_id": 0})
        assert run and run["agent_type"] == "intake_form" and run["status"] == "success"
        assert run["prompt_version"] == "v2"
        assert run["output_ref"] == {"collection": "intake_forms", "id": form["intake_form_id"]}

    def test_regeneration_blocked_once_answering_started(self, doctor, patient, encounter, form):
        ps, _ = patient
        ds, _ = doctor
        first = form["questions"][0]
        ps.post(f"{API}/intake/{encounter['encounter_id']}/responses",
                json={"responses": [{"question_id": first["question_id"], "answer": _answer_for(first)}]}, timeout=60)
        r = ds.post(f"{API}/agents/intake/{encounter['encounter_id']}", timeout=60)
        assert r.status_code == 409


def _answer_for(q):
    if q["type"] == "scale":
        return "6"
    if q["type"] == "single_choice":
        return q["options"][0]
    if q["type"] == "multi_choice":
        return [q["options"][0]]
    return "Mild but noticeable most days this week."


class TestPatientAnswers:
    def test_patient_sees_form_and_partial_progress_persists(self, patient, encounter, form):
        ps, _ = patient
        first = form["questions"][0]
        ps.post(f"{API}/intake/{encounter['encounter_id']}/responses",
                json={"responses": [{"question_id": first["question_id"], "answer": _answer_for(first)}]}, timeout=60)
        r = ps.get(f"{API}/intake/{encounter['encounter_id']}", timeout=60)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ("partial", "pending")
        assert len(body["responses"]) >= 1
        assert body["scheduled_at"] == encounter["scheduled_at"]
        # a fresh session resumes with the same answers
        ps2, _ = login(OMAR)
        again = ps2.get(f"{API}/intake/{encounter['encounter_id']}", timeout=60).json()
        assert again["responses"] == body["responses"]

    def test_unknown_question_rejected(self, patient, encounter):
        ps, _ = patient
        r = ps.post(f"{API}/intake/{encounter['encounter_id']}/responses",
                    json={"responses": [{"question_id": "q99", "answer": "x"}]}, timeout=60)
        assert r.status_code == 400

    def test_completion_when_all_required_answered(self, patient, doctor, encounter, form, db):
        ps, _ = patient
        _, doc = doctor
        payload = [{"question_id": q["question_id"], "answer": _answer_for(q)} for q in form["questions"]]
        r = ps.post(f"{API}/intake/{encounter['encounter_id']}/responses", json={"responses": payload}, timeout=60)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "complete"
        assert len(body["responses"]) == len(form["questions"])

        alert = db.alerts.find_one({"user_id": doc["user_id"], "type": "intake"}, sort=[("created_at", -1)])
        assert alert and alert["severity"] == "info" and alert["read"] is False
        assert "completed pre-visit intake" in alert["message"]

    def test_another_patient_cannot_read_or_answer(self, encounter, db):
        email = f"TEST_intake_{uuid.uuid4().hex[:8]}@example.com"
        s = requests.Session()
        u = s.post(f"{API}/auth/register", json={"name": "Nosy", "email": email, "password": "Passw0rd!"},
                   timeout=60).json()
        try:
            assert s.get(f"{API}/intake/{encounter['encounter_id']}", timeout=60).status_code == 403
            assert s.post(f"{API}/intake/{encounter['encounter_id']}/responses",
                          json={"responses": [{"question_id": "q1", "answer": "x"}]}, timeout=60).status_code == 403
        finally:
            db.users.delete_one({"user_id": u["user_id"]})

    def test_submission_after_expiry_returns_409(self, patient, encounter, db, form):
        ps, _ = patient
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        db.intake_forms.update_one({"encounter_id": encounter["encounter_id"]}, {"$set": {"expires_at": past}})
        try:
            r = ps.post(f"{API}/intake/{encounter['encounter_id']}/responses",
                        json={"responses": [{"question_id": form["questions"][0]["question_id"], "answer": "later"}]},
                        timeout=60)
            assert r.status_code == 409
        finally:
            db.intake_forms.update_one({"encounter_id": encounter["encounter_id"]},
                                       {"$set": {"expires_at": encounter["scheduled_at"]}})

    def test_patient_dashboard_feed_exposes_intake_status(self, patient, encounter):
        ps, _ = patient
        rows = ps.get(f"{API}/encounters", timeout=60).json()
        row = next(e for e in rows if e["encounter_id"] == encounter["encounter_id"])
        assert row["intake"]["status"] == "complete"


class TestDoctorViewAndBriefing:
    def test_doctor_reads_answers(self, doctor, encounter):
        ds, _ = doctor
        r = ds.get(f"{API}/doctor/intake/{encounter['encounter_id']}", timeout=60)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "complete" and len(body["responses"]) >= 5

    def test_briefing_uses_intake_and_bumps_prompt_version(self, doctor, encounter, db, form):
        ds, _ = doctor
        r = ds.post(f"{API}/agents/previsit/{encounter['encounter_id']}", timeout=180)
        assert r.status_code == 200, r.text
        artifact = r.json()
        run = db.agent_runs.find_one({"agent_run_id": artifact["agent_run_id"]}, {"_id": 0})
        assert run["prompt_version"] == "v4"
        assert run["input_refs"]["intake_forms"], "briefing must record the intake form it read"
        concerns = artifact["content"]["chief_concerns"]
        blob = " ".join(c["evidence"].lower() for c in concerns) + " " + " ".join(
            p.lower() for p in artifact["content"]["suggested_discussion_points"])
        assert "intake" in blob or "reported" in blob, artifact["content"]

        valid_ids = {q["question_id"] for q in form["questions"]}
        refs = [qid for c in concerns for qid in c.get("intake_refs", [])]
        assert refs, "at least one concern must link the intake answer that supports it"
        assert all(qid in valid_ids for qid in refs), refs

    def test_older_prompt_versions_still_on_disk_for_audit(self):
        from pathlib import Path
        prompts = Path(__file__).parent.parent / "agents" / "prompts"
        for name in ("previsit_v1.md", "previsit_v2.md", "previsit_v3.md", "intake_v1.md"):
            assert (prompts / name).exists(), name
