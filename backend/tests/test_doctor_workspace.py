"""Clinician workspace tests: doctor dashboard, clinician access requests, admin role approval.

Run:  cd /app/backend && set -a && . ./.env && set +a && \
      REACT_APP_BACKEND_URL=<preview url> python -m pytest tests/test_doctor_workspace.py -q
"""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

API = f"{os.environ['REACT_APP_BACKEND_URL'].rstrip('/')}/api"
ADMIN = {"email": os.environ.get("ADMIN_EMAIL", "admin@sihha.ai"),
         "password": os.environ.get("ADMIN_PASSWORD", "Admin@123")}
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


@pytest.fixture(scope="module")
def admin():
    return login(ADMIN)


@pytest.fixture(scope="module")
def patient():
    return login(OMAR)


class TestDoctorDashboard:
    def test_payload_shape(self, doctor):
        ds, _ = doctor
        r = ds.get(f"{API}/doctor/dashboard", timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ("stats", "todays_visits", "upcoming_visits", "needs_briefing",
                    "awaiting_signature", "awaiting_intake", "alerts", "recent_runs"):
            assert key in body, key
        stats = body["stats"]
        for key in ("patients", "today", "this_week", "needs_briefing",
                    "awaiting_signature", "awaiting_intake", "unread_alerts"):
            assert isinstance(stats[key], int), key
        assert stats["patients"] >= 1
        assert "password_hash" not in r.text

    def test_visits_carry_patient_name_and_states(self, doctor):
        ds, _ = doctor
        body = ds.get(f"{API}/doctor/dashboard", timeout=60).json()
        rows = body["upcoming_visits"] + body["todays_visits"]
        for row in rows:
            assert row["patient_name"]
            assert row["briefing_status"] in (None, "draft", "reviewed", "signed")
            assert row["intake_status"] in (None, "pending", "partial", "complete")

    def test_counts_match_the_lists(self, doctor):
        ds, _ = doctor
        body = ds.get(f"{API}/doctor/dashboard", timeout=60).json()
        assert body["stats"]["today"] == len(body["todays_visits"])
        assert body["stats"]["needs_briefing"] >= len(body["needs_briefing"])

    def test_patient_is_refused(self, patient):
        ps, _ = patient
        assert ps.get(f"{API}/doctor/dashboard", timeout=60).status_code == 403

    def test_admin_sees_at_least_as_many_patients(self, doctor, admin):
        ds, _ = doctor
        adm, _ = admin
        mine = ds.get(f"{API}/doctor/dashboard", timeout=60).json()["stats"]["patients"]
        all_of_them = adm.get(f"{API}/doctor/dashboard", timeout=60).json()["stats"]["patients"]
        assert all_of_them >= mine


class TestClinicianAccessRequest:
    @pytest.fixture
    def applicant(self, db):
        email = f"TEST_clin_{uuid.uuid4().hex[:8]}@example.com"
        s = requests.Session()
        r = s.post(f"{API}/auth/register", json={
            "name": "Dr Applicant", "email": email, "password": "Passw0rd!", "requested_role": "doctor",
        }, timeout=60)
        assert r.status_code == 200, r.text
        yield s, r.json(), email
        db.users.delete_one({"email": email})

    def test_request_creates_a_patient_pending_approval(self, applicant, admin, db):
        _, u, email = applicant
        assert u["role"] == "patient", "a self-service request must never grant the doctor role"
        adm, _ = admin
        row = next(x for x in adm.get(f"{API}/admin/patients", timeout=60).json() if x["user_id"] == u["user_id"])
        assert row["clinician_requested"] is True

    def test_applicant_cannot_reach_clinician_routes_before_approval(self, applicant):
        s, _, _ = applicant
        assert s.get(f"{API}/doctor/dashboard", timeout=60).status_code == 403
        assert s.get(f"{API}/doctor/patients", timeout=60).status_code == 403

    def test_admin_approves_then_the_account_works(self, applicant, admin):
        s, u, email = applicant
        adm, _ = admin
        r = adm.put(f"{API}/admin/users/{u['user_id']}/role", json={"role": "doctor"}, timeout=60)
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "doctor" and r.json()["clinician_requested"] is False

        s2, me = login({"email": email, "password": "Passw0rd!"})
        assert me["role"] == "doctor" and me["is_admin"] is False
        dash = s2.get(f"{API}/doctor/dashboard", timeout=60)
        assert dash.status_code == 200
        assert dash.json()["stats"]["patients"] == 0, "a new clinician starts with an empty panel"

    def test_non_admin_cannot_change_roles(self, doctor, applicant):
        ds, _ = doctor
        s, u, _ = applicant
        assert ds.put(f"{API}/admin/users/{u['user_id']}/role", json={"role": "doctor"}, timeout=60).status_code == 403
        assert s.put(f"{API}/admin/users/{u['user_id']}/role", json={"role": "doctor"}, timeout=60).status_code == 403

    def test_demoting_a_doctor_with_patients_is_blocked(self, admin, doctor):
        adm, _ = admin
        _, layla = doctor
        r = adm.put(f"{API}/admin/users/{layla['user_id']}/role", json={"role": "patient"}, timeout=60)
        assert r.status_code == 409
        assert "assigned" in r.json()["detail"]

    def test_invalid_role_rejected(self, admin, applicant):
        adm, _ = admin
        _, u, _ = applicant
        assert adm.put(f"{API}/admin/users/{u['user_id']}/role",
                       json={"role": "wizard"}, timeout=60).status_code == 400

    def test_plain_registration_does_not_flag_a_request(self, admin, db):
        email = f"TEST_plain_{uuid.uuid4().hex[:8]}@example.com"
        s = requests.Session()
        u = s.post(f"{API}/auth/register", json={"name": "Plain", "email": email, "password": "Passw0rd!"},
                   timeout=60).json()
        try:
            adm, _ = admin
            row = next(x for x in adm.get(f"{API}/admin/patients", timeout=60).json()
                       if x["user_id"] == u["user_id"])
            assert row["clinician_requested"] is False
        finally:
            db.users.delete_one({"user_id": u["user_id"]})
