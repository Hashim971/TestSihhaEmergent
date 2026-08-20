"""Doctor-patient assignment tests: patients pick their doctor, admin assigns the rest.

Run:  cd /app/backend && set -a && . ./.env && set +a && \
      REACT_APP_BACKEND_URL=<preview url> python -m pytest tests/test_assignments.py -q
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


@pytest.fixture(scope="module")
def db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=60)
    r.raise_for_status()
    return s, r.json()


@pytest.fixture(scope="module")
def admin():
    return login(ADMIN)


@pytest.fixture(scope="module")
def layla():
    return login(LAYLA)


@pytest.fixture
def fresh_patient(db):
    email = f"TEST_assign_{uuid.uuid4().hex[:8]}@example.com"
    s = requests.Session()
    u = s.post(f"{API}/auth/register", json={"name": "Assign Test", "email": email, "password": "Passw0rd!"},
               timeout=60).json()
    yield s, u
    db.users.delete_one({"user_id": u["user_id"]})


class TestCapabilities:
    def test_admin_flagged_and_doctor_is_not(self, admin, layla):
        _, a = admin
        _, l = layla
        assert a["is_admin"] is True and a["role"] == "doctor"
        assert l["is_admin"] is False

    def test_non_admin_doctor_cannot_use_admin_routes(self, layla, fresh_patient):
        ls, _ = layla
        _, p = fresh_patient
        assert ls.get(f"{API}/admin/patients", timeout=60).status_code == 403
        assert ls.put(f"{API}/admin/patients/{p['user_id']}/doctor",
                      json={"doctor_user_id": None}, timeout=60).status_code == 403

    def test_patient_cannot_use_admin_routes(self, fresh_patient):
        s, _ = fresh_patient
        assert s.get(f"{API}/admin/patients", timeout=60).status_code == 403


class TestPatientChoosesDoctor:
    def test_unassigned_patient_is_invisible_to_doctors_but_visible_to_admin(self, layla, admin, fresh_patient):
        ls, _ = layla
        adm, _ = admin
        _, p = fresh_patient
        panel = [x["user_id"] for x in ls.get(f"{API}/doctor/patients", timeout=60).json()]
        assert p["user_id"] not in panel
        assert ls.get(f"{API}/doctor/patients/{p['user_id']}/summary", timeout=60).status_code == 403
        admin_list = [x["user_id"] for x in adm.get(f"{API}/admin/patients", timeout=60).json()]
        assert p["user_id"] in admin_list
        # the admin account keeps full clinical visibility so it can manage assignments
        assert adm.get(f"{API}/doctor/patients/{p['user_id']}/summary", timeout=60).status_code == 200

    def test_choosing_a_doctor_adds_the_patient_to_that_panel(self, layla, fresh_patient):
        ls, doc = layla
        ps, p = fresh_patient
        r = ps.put(f"{API}/profile/doctor", json={"doctor_user_id": doc["user_id"]}, timeout=60)
        assert r.status_code == 200
        assert r.json()["assigned_doctor_user_id"] == doc["user_id"]
        panel = [x["user_id"] for x in ls.get(f"{API}/doctor/patients", timeout=60).json()]
        assert p["user_id"] in panel
        assert ls.get(f"{API}/doctor/patients/{p['user_id']}/summary", timeout=60).status_code == 200

    def test_choosing_another_doctor_transfers_and_revokes(self, layla, admin, fresh_patient):
        ls, layla_doc = layla
        adm, admin_doc = admin
        ps, p = fresh_patient
        ps.put(f"{API}/profile/doctor", json={"doctor_user_id": layla_doc["user_id"]}, timeout=60)
        ps.put(f"{API}/profile/doctor", json={"doctor_user_id": admin_doc["user_id"]}, timeout=60)
        assert ls.get(f"{API}/doctor/patients/{p['user_id']}/summary", timeout=60).status_code == 403
        panel = [x["user_id"] for x in ls.get(f"{API}/doctor/patients", timeout=60).json()]
        assert p["user_id"] not in panel

    def test_unknown_doctor_is_rejected(self, fresh_patient):
        ps, _ = fresh_patient
        assert ps.put(f"{API}/profile/doctor", json={"doctor_user_id": "user_doesnotexist"},
                      timeout=60).status_code == 404

    def test_doctors_directory_hides_password_hash(self, fresh_patient):
        ps, _ = fresh_patient
        r = ps.get(f"{API}/doctors", timeout=60)
        assert r.status_code == 200 and "password_hash" not in r.text
        allowed = {"user_id", "name", "email", "specialty", "clinic", "city", "bio", "clinic_phone"}
        assert all(set(d) <= allowed for d in r.json())


class TestAdminAssigns:
    def test_admin_assigns_and_clears(self, admin, layla, fresh_patient):
        adm, _ = admin
        ls, layla_doc = layla
        _, p = fresh_patient
        r = adm.put(f"{API}/admin/patients/{p['user_id']}/doctor",
                    json={"doctor_user_id": layla_doc["user_id"]}, timeout=60)
        assert r.status_code == 200
        assert r.json()["assigned_doctor_user_id"] == layla_doc["user_id"]
        assert r.json()["assigned_by"] == "admin"
        assert ls.get(f"{API}/doctor/patients/{p['user_id']}/summary", timeout=60).status_code == 200

        cleared = adm.put(f"{API}/admin/patients/{p['user_id']}/doctor", json={"doctor_user_id": None}, timeout=60)
        assert cleared.status_code == 200 and cleared.json()["assigned_doctor_user_id"] is None
        assert ls.get(f"{API}/doctor/patients/{p['user_id']}/summary", timeout=60).status_code == 403

    def test_admin_list_shows_assignment_state(self, admin, layla, fresh_patient):
        adm, _ = admin
        _, layla_doc = layla
        _, p = fresh_patient
        adm.put(f"{API}/admin/patients/{p['user_id']}/doctor",
                json={"doctor_user_id": layla_doc["user_id"]}, timeout=60)
        row = next(x for x in adm.get(f"{API}/admin/patients", timeout=60).json() if x["user_id"] == p["user_id"])
        assert row["assigned_doctor_name"] == "Dr. Layla Haddad"
        assert row["sharing_enabled"] is True
        assert "password_hash" not in str(row)

    def test_admin_rejects_unknown_patient(self, admin):
        adm, _ = admin
        assert adm.put(f"{API}/admin/patients/user_nope/doctor",
                       json={"doctor_user_id": None}, timeout=60).status_code == 404


class TestAssignmentGatesClinicalRoutes:
    def test_encounter_creation_requires_assignment(self, layla, fresh_patient):
        ls, layla_doc = layla
        ps, p = fresh_patient
        assert ls.post(f"{API}/encounters", json={"patient_user_id": p["user_id"]}, timeout=60).status_code == 403
        ps.put(f"{API}/profile/doctor", json={"doctor_user_id": layla_doc["user_id"]}, timeout=60)
        assert ls.post(f"{API}/encounters", json={"patient_user_id": p["user_id"]}, timeout=60).status_code == 200

    def test_seeded_patients_remain_in_layla_panel(self, layla):
        ls, _ = layla
        emails = [x["email"] for x in ls.get(f"{API}/doctor/patients", timeout=60).json()]
        assert "omar.patient@sihha.ai" in emails
        assert "hashim@gmail.com" in emails
