"""Screening findings tests: structured extraction, symptom timeline, staleness, sharing, doctor view.

Run:  cd /app/backend && set -a && . ./.env && set +a && \
      REACT_APP_BACKEND_URL=<preview url> python -m pytest tests/test_screening_findings.py -q
"""
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

API = f"{os.environ['REACT_APP_BACKEND_URL'].rstrip('/')}/api"
LAYLA = {"email": "dr.layla@sihha.ai", "password": "Doctor@123"}
NOURA = {"email": "noura.patient@sihha.ai", "password": "Patient@123"}
DIAGNOSTIC_WORDS = ("diagnos", "hypertension", "migraine", "angina", "you likely have")


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
    return login(NOURA)


@pytest.fixture(scope="module")
def screening(patient, db):
    """Runs a real screening chat to completion and returns the generated report."""
    ps, u = patient
    sid = ps.post(f"{API}/chat/sessions", json={"profile_id": "self"}, timeout=60).json()["chat_session_id"]
    turns = [
        "I have had a tight feeling in my chest for about five days, mostly in the afternoons.",
        "It is moderate, maybe a 6 out of 10, and it eases when I sit down and rest.",
        "I also get short of breath walking up the stairs since about two weeks ago.",
    ]
    for t in turns:
        r = ps.post(f"{API}/chat/sessions/{sid}/message", json={"text": t}, timeout=120, stream=True)
        assert r.status_code == 200, r.text
        for _ in r.iter_lines():
            pass
    report = ps.post(f"{API}/chat/sessions/{sid}/report", timeout=240)
    assert report.status_code == 200, report.text
    body = report.json()
    yield body
    db.health_reports.delete_one({"report_id": body["report_id"]})
    db.chat_messages.delete_many({"chat_session_id": sid})
    db.chat_sessions.delete_one({"chat_session_id": sid})


class TestAutomaticExtraction:
    def test_findings_extracted_on_report_generation(self, screening):
        assert screening["findings_extracted_at"], "extraction must run when the report is generated"
        findings = screening["findings"]
        assert findings, "a screening describing symptoms must yield findings"
        for f in findings:
            assert f["finding_id"].startswith("find_")
            assert f["report_id"] == screening["report_id"]
            assert f["symptom"] and len(f["symptom"].split()) <= 5
            assert f["severity"] in ("mild", "moderate", "severe", "unclear")
            assert f["patient_words"] and len(f["patient_words"]) <= 400

    def test_findings_quote_the_patient_not_a_diagnosis(self, screening):
        blob = " ".join(f["symptom"].lower() for f in screening["findings"])
        for word in DIAGNOSTIC_WORDS:
            assert word not in blob, f"diagnostic label in symptom: {word}"

    def test_source_message_ids_point_at_real_messages(self, screening, db):
        ids = [mid for f in screening["findings"] for mid in f["source_message_ids"]]
        assert ids, "findings from a live chat must cite transcript messages"
        assert db.chat_messages.count_documents({"message_id": {"$in": ids}}) == len(set(ids))

    def test_extraction_logged_as_agent_run(self, screening, db):
        run = db.agent_runs.find_one({"agent_run_id": screening["findings_agent_run_id"]}, {"_id": 0})
        assert run and run["agent_type"] == "screening_extract" and run["status"] == "success"
        assert run["output_ref"] == {"collection": "health_reports", "id": screening["report_id"]}
        assert run["input_refs"]["health_reports"] == [screening["report_id"]]


class TestSharingAndDoctorView:
    @pytest.fixture(scope="class")
    def encounter(self, doctor, patient, db):
        ds, _ = doctor
        _, p = patient
        r = ds.post(f"{API}/encounters", json={
            "patient_user_id": p["user_id"],
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "reason_for_visit": "Chest tightness (screening test)",
        }, timeout=60)
        assert r.status_code == 200, r.text
        enc = r.json()
        yield enc
        db.encounters.delete_one({"encounter_id": enc["encounter_id"]})

    def test_patient_shares_report_for_a_visit(self, patient, screening, encounter):
        ps, _ = patient
        r = ps.put(f"{API}/reports/{screening['report_id']}/share",
                   json={"encounter_id": encounter["encounter_id"]}, timeout=60)
        assert r.status_code == 200
        assert r.json()["shared_encounter_id"] == encounter["encounter_id"]

    def test_sharing_rejects_someone_elses_visit(self, screening, encounter, db):
        email = f"TEST_share_{uuid.uuid4().hex[:8]}@example.com"
        s = requests.Session()
        u = s.post(f"{API}/auth/register", json={"name": "Other", "email": email, "password": "Passw0rd!"},
                   timeout=60).json()
        try:
            assert s.put(f"{API}/reports/{screening['report_id']}/share",
                         json={"encounter_id": encounter["encounter_id"]}, timeout=60).status_code == 404
        finally:
            db.users.delete_one({"user_id": u["user_id"]})

    def test_doctor_screening_view_has_findings_excerpts_and_timeline(self, doctor, screening, encounter):
        ds, _ = doctor
        r = ds.get(f"{API}/doctor/screening/{encounter['encounter_id']}", timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        row = next(x for x in body["reports"] if x["report_id"] == screening["report_id"])
        assert row["shared_for_this_visit"] is True
        assert row["findings"] and row["stale"] is False and row["age_days"] == 0
        cited = [mid for f in row["findings"] for mid in f["source_message_ids"]]
        assert all(mid in body["excerpts"] for mid in cited)
        assert isinstance(body["symptom_timeline"], list)

    def test_stale_reports_are_flagged(self, doctor, screening, encounter, db):
        ds, _ = doctor
        old = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        db.health_reports.update_one({"report_id": screening["report_id"]}, {"$set": {"generated_at": old}})
        try:
            body = ds.get(f"{API}/doctor/screening/{encounter['encounter_id']}", timeout=60).json()
            row = next(x for x in body["reports"] if x["report_id"] == screening["report_id"])
            assert row["stale"] is True and row["age_days"] >= 200
        finally:
            db.health_reports.update_one({"report_id": screening["report_id"]},
                                         {"$set": {"generated_at": screening["generated_at"]}})

    def test_doctor_can_restructure_on_demand(self, doctor, screening):
        ds, _ = doctor
        r = ds.post(f"{API}/doctor/reports/{screening['report_id']}/findings", timeout=240)
        assert r.status_code == 200, r.text
        assert r.json()["findings"]

    def test_unassigned_doctor_cannot_read_screening(self, screening, encounter, db):
        """A doctor account with no claim on this patient must be refused."""
        email = f"TEST_doc_{uuid.uuid4().hex[:8]}@example.com"
        s = requests.Session()
        u = s.post(f"{API}/auth/register", json={"name": "Dr Nobody", "email": email, "password": "Passw0rd!"},
                   timeout=60).json()
        db.users.update_one({"user_id": u["user_id"]}, {"$set": {"role": "doctor"}})
        try:
            assert s.get(f"{API}/doctor/screening/{encounter['encounter_id']}", timeout=60).status_code == 403
            assert s.post(f"{API}/doctor/reports/{screening['report_id']}/findings", timeout=60).status_code == 403
        finally:
            db.users.delete_one({"user_id": u["user_id"]})

    def test_briefing_cites_screening_findings(self, doctor, screening, encounter, db):
        ds, _ = doctor
        current = ds.get(f"{API}/doctor/screening/{encounter['encounter_id']}", timeout=60).json()
        row = next(x for x in current["reports"] if x["report_id"] == screening["report_id"])
        # The briefing may cite any of the patient's recent screenings, not only this one.
        valid = {f["finding_id"] for rep in current["reports"] for f in rep["findings"]}
        assert {f["finding_id"] for f in row["findings"]} <= valid
        r = ds.post(f"{API}/agents/previsit/{encounter['encounter_id']}", timeout=240)
        assert r.status_code == 200, r.text
        artifact = r.json()
        run = db.agent_runs.find_one({"agent_run_id": artifact["agent_run_id"]}, {"_id": 0})
        assert run["prompt_version"] == "v4"
        refs = [fid for c in artifact["content"]["chief_concerns"] for fid in c.get("screening_refs", [])]
        assert refs, "a concern must link the screening finding behind it"
        assert all(fid in valid for fid in refs), refs

    def test_reextraction_keeps_finding_ids_stable(self, doctor, screening, encounter):
        """Old briefings cite finding_ids — re-structuring must not orphan those citations."""
        ds, _ = doctor
        before = ds.get(f"{API}/doctor/screening/{encounter['encounter_id']}", timeout=60).json()
        row_before = next(x for x in before["reports"] if x["report_id"] == screening["report_id"])
        ids_by_symptom = {f["symptom"].strip().lower(): f["finding_id"] for f in row_before["findings"]}

        assert ds.post(f"{API}/doctor/reports/{screening['report_id']}/findings",
                       timeout=240).status_code == 200
        after = ds.get(f"{API}/doctor/screening/{encounter['encounter_id']}", timeout=60).json()
        row_after = next(x for x in after["reports"] if x["report_id"] == screening["report_id"])
        for f in row_after["findings"]:
            key = f["symptom"].strip().lower()
            if key in ids_by_symptom:
                assert f["finding_id"] == ids_by_symptom[key], f"finding_id changed for {key}"
