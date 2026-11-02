# Iteration 20: retest of iteration-19 fixes (one active hospital on doctor choice, pharmacist 403s,
# patient order unread counts, invite-vs-pending-applicant 409, sponsored impressions only for patients).
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


def _env(path, key):
    for line in open(path):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


MONGO = MongoClient(_env("/app/backend/.env", "MONGO_URL"))[_env("/app/backend/.env", "DB_NAME")]
AL_NOOR, JEDDAH = "ACC-12AFFE", "ACC-2BC6ED"
KHALID, LAYLA = "user_af7cc0803ba9", "user_b1000ae5aad6"
NAHDI, AL_DAWAA = "pharm_8a96b2710089", "pharm_744d6031f418"
OTC_AL_DAWAA = "item_7b3c5dd64c3b"
CREATED = {"users": [], "apps": [], "orders": [], "encounters": []}


def login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def solo():
    return login("solo.patient@sihha.ai", "Patient@123")


@pytest.fixture(scope="module")
def admin():
    return login("admin@sihha.ai", "Admin@123")


@pytest.fixture(scope="module")
def layla():
    return login("dr.layla@sihha.ai", "Doctor@123")


@pytest.fixture(scope="module")
def pharm():
    return login("pharmacist@aldawaa.sihha.ai", "Pharma@123")


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    solo_id = MONGO.users.find_one({"email": "solo.patient@sihha.ai"})["user_id"]
    MONGO.users.update_one({"user_id": solo_id}, {"$set": {"account_id": None, "account_role": None,
                                                           "assigned_doctor_user_id": None}})
    MONGO.care_grants.delete_many({"patient_user_id": solo_id})
    MONGO.alerts.delete_many({"encounter_id": {"$in": CREATED["encounters"]}})
    MONGO.encounters.delete_many({"encounter_id": {"$in": CREATED["encounters"]}})
    MONGO.order_messages.delete_many({"order_id": {"$in": CREATED["orders"]}})
    MONGO.alerts.delete_many({"order_id": {"$in": CREATED["orders"]}})
    MONGO.orders.delete_many({"order_id": {"$in": CREATED["orders"]}})
    MONGO.carts.delete_many({"user_id": solo_id})
    MONGO.pharmacy_applications.delete_many({"application_id": {"$in": CREATED["apps"]}})
    MONGO.users.delete_many({"user_id": {"$in": CREATED["users"]}})
    MONGO.login_attempts.delete_many({"identifier": {"$regex": "^pharmacy-apply:"}})


def _book(sess, doctor_id, share):
    slots = sess.get(f"{API}/booking/slots", params={"doctor_user_id": doctor_id}).json()["slots"]
    assert slots, "no open slots"
    r = sess.post(f"{API}/booking", json={"doctor_user_id": doctor_id, "slot_start": slots[-1]["start"],
                                          "reason_for_visit": "TEST_ iter20", "share_record": share})
    assert r.status_code == 200, r.text
    enc = r.json().get("encounter", r.json())
    CREATED["encounters"].append(enc["encounter_id"])
    return enc


# ---------- (3) one active hospital on PUT /profile/doctor ----------
class TestDoctorChoiceSwitchesHospital:
    def test_cross_hospital_doctor_switch(self, solo):
        enc = _book(solo, LAYLA, True)
        u = MONGO.users.find_one({"email": "solo.patient@sihha.ai"})
        assert u["account_id"] == AL_NOOR
        assert MONGO.care_grants.count_documents({"encounter_id": enc["encounter_id"], "revoked": False}) == 1
        r = solo.put(f"{API}/profile/doctor", json={"doctor_user_id": KHALID})
        assert r.status_code == 200, r.text
        u = MONGO.users.find_one({"email": "solo.patient@sihha.ai"})
        assert u["account_id"] == JEDDAH
        assert u["assigned_doctor_user_id"] == KHALID
        assert MONGO.care_grants.count_documents({"encounter_id": enc["encounter_id"], "revoked": False}) == 0
        assert solo.get(f"{API}/profile/hospital").json()["hospital"]["account_id"] == JEDDAH

    def test_doctors_list_filtered_by_active_hospital(self, solo):
        docs = solo.get(f"{API}/doctors").json()
        ids = {d["user_id"] for d in docs}
        assert KHALID in ids and LAYLA not in ids
        assert all(d.get("account_id") in (None, JEDDAH) for d in docs)

    def test_layla_lost_access(self, solo, layla):
        sid = MONGO.users.find_one({"email": "solo.patient@sihha.ai"})["user_id"]
        assert layla.get(f"{API}/doctor/patients/{sid}/summary").status_code == 403

    def test_standalone_sees_all_doctors(self, solo):
        solo.put(f"{API}/profile/hospital", json={"account_id": None})
        ids = {d["user_id"] for d in solo.get(f"{API}/doctors").json()}
        assert {KHALID, LAYLA} <= ids


# ---------- (4) pharmacist role blocked from patient endpoints ----------
class TestPharmacistBlocked:
    def test_booking(self, pharm):
        r = pharm.post(f"{API}/booking", json={"doctor_user_id": KHALID, "slot_start": "2026-12-01T09:00:00+03:00"})
        assert r.status_code == 403, r.status_code

    def test_chat(self, pharm):
        assert pharm.post(f"{API}/chat/sessions", json={}).status_code == 403

    def test_checkout(self, pharm):
        assert pharm.post(f"{API}/pharmacy/checkout", json={}).status_code == 403

    def test_profile_doctor(self, pharm):
        assert pharm.put(f"{API}/profile/doctor", json={"doctor_user_id": KHALID}).status_code == 403


# ---------- (5) patient order list unread counts ----------
def test_patient_unread_messages(solo, pharm):
    solo.delete(f"{API}/pharmacy/cart")
    assert solo.post(f"{API}/pharmacy/cart/items", json={"item_id": OTC_AL_DAWAA, "qty": 1}).status_code == 200
    r = solo.post(f"{API}/pharmacy/checkout", json={})
    assert r.status_code == 200, r.text
    oid = r.json().get("order", r.json())["order_id"]
    CREATED["orders"].append(oid)
    row = next(o for o in solo.get(f"{API}/pharmacy/orders").json() if o["order_id"] == oid)
    assert row["unread_messages"] == 0
    assert pharm.post(f"{API}/pharmacy-portal/orders/{oid}/messages", json={"text": "TEST_ p1"}).status_code == 200
    assert pharm.post(f"{API}/pharmacy-portal/orders/{oid}/messages", json={"text": "TEST_ p2"}).status_code == 200
    row = next(o for o in solo.get(f"{API}/pharmacy/orders").json() if o["order_id"] == oid)
    assert row["unread_messages"] == 2
    msgs = solo.get(f"{API}/pharmacy/orders/{oid}/messages").json()
    assert [m["text"] for m in msgs] == ["TEST_ p1", "TEST_ p2"]
    row = next(o for o in solo.get(f"{API}/pharmacy/orders").json() if o["order_id"] == oid)
    assert row["unread_messages"] == 0


# ---------- (8) invite with a pending applicant's email -> 409 ----------
def test_invite_pending_applicant_conflict(admin):
    email = f"test_pharm_pend_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/pharmacy-portal/apply", json={
        "pharmacy_name": "TEST_ Pending", "city": "Riyadh", "sfda_license": "SFDA-9", "name": "TEST_ P",
        "phone": "0500000000", "email": email, "password": "Test@1234"})
    assert r.status_code == 200, r.text
    CREATED["apps"].append(r.json()["application_id"])
    uid = MONGO.users.find_one({"email": email})["user_id"]
    CREATED["users"].append(uid)
    r = admin.post(f"{API}/admin/pharmacies/{AL_DAWAA}/staff", json={"name": "x", "email": email})
    assert r.status_code == 409, r.text
    assert MONGO.users.find_one({"user_id": uid}).get("pharmacy_id") is None


# ---------- (9) impressions only for patient calls ----------
def test_impressions_patient_only(solo, pharm, admin):
    imp = lambda: (MONGO.pharmacies.find_one({"pharmacy_id": NAHDI}).get("stats") or {}).get("impressions", 0)
    base = imp()
    assert pharm.get(f"{API}/pharmacy/pharmacies").status_code == 200
    assert admin.get(f"{API}/pharmacy/pharmacies").status_code == 200
    assert imp() == base
    assert solo.get(f"{API}/pharmacy/pharmacies").status_code == 200
    assert imp() == base + 1
