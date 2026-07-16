"""Backend integration tests for Sihha AI.

Uses a MongoDB-inserted test session (see /app/auth_testing.md).
"""
import os
import time
import json
import base64
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ab05f5cb-2f3a-4bd8-b2b4-33cfdc0ac6c8.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "sihha_ai")


@pytest.fixture(scope="session")
def mongo_db():
    c = MongoClient(MONGO_URL)
    return c[DB_NAME]


@pytest.fixture(scope="session")
def patient_session(mongo_db):
    """Create a patient user + session in Mongo."""
    user_id = f"test-user-pt-{uuid.uuid4().hex[:8]}"
    token = f"test_session_pt_{uuid.uuid4().hex}"
    mongo_db.users.insert_one({
        "user_id": user_id,
        "email": f"TEST_pt_{user_id}@example.com",
        "name": "Test Patient",
        "picture": "https://via.placeholder.com/150",
        "role": "patient",
        "sharing_enabled": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    mongo_db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"user_id": user_id, "token": token}
    # cleanup
    mongo_db.users.delete_one({"user_id": user_id})
    mongo_db.user_sessions.delete_one({"session_token": token})
    mongo_db.vitals.delete_many({"user_id": user_id})
    mongo_db.alerts.delete_many({"user_id": user_id})
    mongo_db.chat_sessions.delete_many({"user_id": user_id})
    mongo_db.chat_messages.delete_many({})
    mongo_db.medications.delete_many({"user_id": user_id})
    mongo_db.dose_logs.delete_many({"user_id": user_id})
    mongo_db.dependents.delete_many({"user_id": user_id})
    mongo_db.pill_history.delete_many({"user_id": user_id})
    mongo_db.health_reports.delete_many({"user_id": user_id})


@pytest.fixture(scope="session")
def doctor_session(mongo_db):
    user_id = f"test-user-dr-{uuid.uuid4().hex[:8]}"
    token = f"test_session_dr_{uuid.uuid4().hex}"
    mongo_db.users.insert_one({
        "user_id": user_id,
        "email": f"TEST_dr_{user_id}@example.com",
        "name": "Test Doctor",
        "picture": "https://via.placeholder.com/150",
        "role": "doctor",
        "sharing_enabled": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    mongo_db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"user_id": user_id, "token": token}
    mongo_db.users.delete_one({"user_id": user_id})
    mongo_db.user_sessions.delete_one({"session_token": token})


def h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------- Auth ----------
class TestAuth:
    def test_me_unauthenticated(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_me_bearer(self, patient_session):
        r = requests.get(f"{API}/auth/me", headers=h(patient_session["token"]))
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == patient_session["user_id"]
        assert data["role"] == "patient"
        assert "_id" not in data

    def test_me_cookie(self, patient_session):
        r = requests.get(f"{API}/auth/me", cookies={"session_token": patient_session["token"]})
        assert r.status_code == 200


# ---------- Vitals & Alerts ----------
class TestVitals:
    def test_add_out_of_range_creates_alert(self, patient_session):
        r = requests.post(f"{API}/vitals", headers=h(patient_session["token"]),
                          json={"heart_rate": 150, "profile_id": "self"})
        assert r.status_code == 200
        v = r.json()
        assert v["heart_rate"] == 150
        assert "_id" not in v
        # alert should be created
        time.sleep(0.5)
        a = requests.get(f"{API}/alerts", headers=h(patient_session["token"]))
        assert a.status_code == 200
        alerts = a.json()
        assert any("Heart rate" in x["message"] and not x["read"] for x in alerts)

    def test_list_vitals(self, patient_session):
        r = requests.get(f"{API}/vitals", headers=h(patient_session["token"]))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_latest_vital(self, patient_session):
        r = requests.get(f"{API}/vitals/latest", headers=h(patient_session["token"]))
        assert r.status_code == 200
        data = r.json()
        assert "heart_rate" in data

    def test_simulate(self, patient_session):
        r = requests.post(f"{API}/vitals/simulate", headers=h(patient_session["token"]), json={})
        assert r.status_code == 200
        inserted = r.json()["inserted"]
        assert inserted >= 15  # allow slight variance based on current hour


class TestAlerts:
    def test_mark_read(self, patient_session):
        alerts = requests.get(f"{API}/alerts", headers=h(patient_session["token"])).json()
        assert alerts
        aid = alerts[0]["alert_id"]
        r = requests.post(f"{API}/alerts/{aid}/read", headers=h(patient_session["token"]))
        assert r.status_code == 200
        after = requests.get(f"{API}/alerts", headers=h(patient_session["token"])).json()
        found = [a for a in after if a["alert_id"] == aid][0]
        assert found["read"] is True


# ---------- Medications ----------
class TestMedications:
    med_id = None

    def test_create_med(self, patient_session):
        r = requests.post(f"{API}/medications", headers=h(patient_session["token"]),
                          json={"name": "TEST_Aspirin", "dosage": "100mg", "times": ["08:00", "20:00"]})
        assert r.status_code == 200
        m = r.json()
        assert m["name"] == "TEST_Aspirin"
        assert "_id" not in m
        TestMedications.med_id = m["medication_id"]

    def test_list(self, patient_session):
        r = requests.get(f"{API}/medications", headers=h(patient_session["token"]))
        assert r.status_code == 200
        assert any(m["medication_id"] == TestMedications.med_id for m in r.json())

    def test_today_schedule(self, patient_session):
        r = requests.get(f"{API}/medications/schedule/today", headers=h(patient_session["token"]))
        assert r.status_code == 200
        sch = r.json()
        assert any(s["medication_id"] == TestMedications.med_id for s in sch)

    def test_dose_taken(self, patient_session):
        r = requests.post(f"{API}/medications/{TestMedications.med_id}/dose",
                          headers=h(patient_session["token"]),
                          json={"time": "08:00", "status": "taken"})
        assert r.status_code == 200

    def test_dose_missed_creates_alert(self, patient_session):
        r = requests.post(f"{API}/medications/{TestMedications.med_id}/dose",
                          headers=h(patient_session["token"]),
                          json={"time": "20:00", "status": "missed"})
        assert r.status_code == 200
        alerts = requests.get(f"{API}/alerts", headers=h(patient_session["token"])).json()
        assert any(a["type"] == "medication" for a in alerts)

    def test_adherence(self, patient_session):
        r = requests.get(f"{API}/medications/adherence/stats", headers=h(patient_session["token"]))
        assert r.status_code == 200
        s = r.json()
        assert s["taken"] >= 1 and s["missed"] >= 1

    def test_delete(self, patient_session):
        r = requests.delete(f"{API}/medications/{TestMedications.med_id}", headers=h(patient_session["token"]))
        assert r.status_code == 200
        lst = requests.get(f"{API}/medications", headers=h(patient_session["token"])).json()
        assert not any(m["medication_id"] == TestMedications.med_id for m in lst)


# ---------- Dependents ----------
class TestDependents:
    dep_id = None

    def test_create(self, patient_session):
        r = requests.post(f"{API}/dependents", headers=h(patient_session["token"]),
                          json={"name": "TEST_Child", "relation": "child"})
        assert r.status_code == 200
        TestDependents.dep_id = r.json()["dependent_id"]

    def test_list(self, patient_session):
        r = requests.get(f"{API}/dependents", headers=h(patient_session["token"]))
        assert r.status_code == 200
        assert any(d["dependent_id"] == TestDependents.dep_id for d in r.json())

    def test_vitals_scoped(self, patient_session):
        # add vital for dependent
        r = requests.post(f"{API}/vitals", headers=h(patient_session["token"]),
                          json={"heart_rate": 80, "profile_id": TestDependents.dep_id})
        assert r.status_code == 200
        r2 = requests.get(f"{API}/vitals?profile_id={TestDependents.dep_id}",
                          headers=h(patient_session["token"]))
        assert r2.status_code == 200
        vals = r2.json()
        assert vals and all(v["profile_id"] == TestDependents.dep_id for v in vals)

    def test_delete(self, patient_session):
        r = requests.delete(f"{API}/dependents/{TestDependents.dep_id}", headers=h(patient_session["token"]))
        assert r.status_code == 200


# ---------- Role & Doctor Portal ----------
class TestDoctorPortal:
    def test_patient_forbidden(self, patient_session):
        r = requests.get(f"{API}/doctor/patients", headers=h(patient_session["token"]))
        assert r.status_code == 403

    def test_role_and_sharing(self, patient_session):
        # create a second patient with sharing enabled for doctor to see
        pass  # handled via fixture below in test_doctor_lists_patients

    def test_doctor_lists_patients(self, doctor_session, patient_session, mongo_db):
        # Enable sharing on patient
        r = requests.post(f"{API}/auth/sharing", headers=h(patient_session["token"]),
                          json={"enabled": True})
        assert r.status_code == 200
        assert r.json()["sharing_enabled"] is True

        r = requests.get(f"{API}/doctor/patients", headers=h(doctor_session["token"]))
        assert r.status_code == 200
        patients = r.json()
        assert any(p["user_id"] == patient_session["user_id"] for p in patients)

    def test_doctor_summary(self, doctor_session, patient_session):
        r = requests.get(f"{API}/doctor/patients/{patient_session['user_id']}/summary",
                         headers=h(doctor_session["token"]))
        assert r.status_code == 200
        data = r.json()
        assert data["patient"]["user_id"] == patient_session["user_id"]
        assert "vitals" in data and "alerts" in data and "adherence" in data


# ---------- Chat (real LLM) ----------
class TestChat:
    sid = None

    def test_create_session(self, patient_session):
        r = requests.post(f"{API}/chat/sessions", headers=h(patient_session["token"]),
                          json={"profile_id": "self"})
        assert r.status_code == 200
        s = r.json()
        TestChat.sid = s["chat_session_id"]
        msgs = requests.get(f"{API}/chat/sessions/{TestChat.sid}/messages",
                            headers=h(patient_session["token"])).json()
        assert msgs and msgs[0]["role"] == "assistant"

    def test_stream_message(self, patient_session):
        assert TestChat.sid
        with requests.post(
            f"{API}/chat/sessions/{TestChat.sid}/message",
            headers=h(patient_session["token"]),
            json={"text": "I have a mild headache for 2 days, no fever."},
            stream=True, timeout=120,
        ) as r:
            assert r.status_code == 200
            got_delta = False
            got_done = False
            for line in r.iter_lines():
                if not line:
                    continue
                if line.startswith(b"data: "):
                    payload = json.loads(line[6:].decode())
                    if "delta" in payload:
                        got_delta = True
                    if payload.get("done"):
                        got_done = True
                        break
                    if "error" in payload:
                        pytest.fail(f"stream error: {payload['error']}")
            assert got_delta and got_done
        # persisted
        msgs = requests.get(f"{API}/chat/sessions/{TestChat.sid}/messages",
                            headers=h(patient_session["token"])).json()
        assert len(msgs) >= 3
        assert msgs[-1]["role"] == "assistant"

    def test_generate_report(self, patient_session):
        r = requests.post(f"{API}/chat/sessions/{TestChat.sid}/report",
                          headers=h(patient_session["token"]), timeout=120)
        assert r.status_code == 200
        rep = r.json()
        assert rep["content"] and len(rep["content"]) > 50


# ---------- Pill Identify (real LLM) ----------
def _tiny_pill_jpeg_b64():
    """Generate a synthetic-but-featured JPEG of pill-like shapes for identification.

    Per /app/image_testing.md: base64 JPEG with real visual features.
    """
    try:
        from PIL import Image, ImageDraw, ImageFilter
        import io
        img = Image.new("RGB", (400, 400), (230, 230, 235))
        d = ImageDraw.Draw(img)
        d.ellipse((80, 160, 320, 240), fill=(250, 250, 245), outline=(180, 180, 180), width=3)
        d.line((200, 165, 200, 235), fill=(160, 160, 160), width=2)
        d.text((150, 190), "500", fill=(80, 80, 80))
        d.ellipse((260, 260, 340, 340), fill=(255, 200, 200), outline=(200, 100, 100), width=2)
        d.ellipse((60, 60, 140, 140), fill=(200, 220, 255), outline=(100, 130, 180), width=2)
        img = img.filter(ImageFilter.SMOOTH)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


class TestPills:
    def test_identify(self, patient_session):
        b64 = _tiny_pill_jpeg_b64()
        if not b64:
            pytest.skip("Could not fetch pill image")
        r = requests.post(f"{API}/pills/identify", headers=h(patient_session["token"]),
                          json={"image_base64": b64, "profile_id": "self"}, timeout=120)
        assert r.status_code == 200
        rec = r.json()
        assert "result" in rec and isinstance(rec["result"], dict)
        assert "identified" in rec["result"]

    def test_history(self, patient_session):
        r = requests.get(f"{API}/pills/history", headers=h(patient_session["token"]))
        assert r.status_code == 200
        assert isinstance(r.json(), list) and len(r.json()) >= 1
