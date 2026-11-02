# Iteration 16: server-side feature flag enforcement, checklist language, invite existing patient as staff
import os
import time
import uuid
import pytest
import requests
from pymongo import MongoClient
from dotenv import dotenv_values

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', dotenv_values('/app/frontend/.env').get('REACT_APP_BACKEND_URL')).rstrip('/')
API = f"{BASE_URL}/api"
BENV = dotenv_values('/app/backend/.env')

GATED = ["/chat/sessions", "/pills/history", "/booking/doctors", "/prescriptions", "/patient/visit-summaries",
         "/pharmacy/pharmacies", "/pharmacy/cart"]


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def db():
    c = MongoClient(BENV["MONGO_URL"])
    yield c[BENV["DB_NAME"]]
    c.close()


@pytest.fixture(scope="module")
def admin():
    return login("admin@sihha.ai", "Admin@123")


@pytest.fixture(scope="module")
def omar():
    return login("omar.patient@sihha.ai", "Patient@123")


@pytest.fixture(scope="module")
def sami():
    return login("sami.patient@sihha.ai", "Patient@123")


@pytest.fixture(scope="module")
def alnoor(admin):
    items = admin.get(f"{API}/admin/accounts", params={"q": "Al Noor"}).json()["items"]
    assert items
    return items[0]


@pytest.fixture(scope="module")
def restore(admin, alnoor):
    original = dict(alnoor.get("features") or {})
    yield
    admin.put(f"{API}/admin/flags/pharmacy_marketplace", json={"enabled": True})
    admin.patch(f"{API}/admin/accounts/{alnoor['account_id']}", json={"features": original})


# Baseline: all gated endpoints reachable when flags on
def test_gated_endpoints_ok_when_on(omar, restore):
    for p in GATED:
        r = omar.get(f"{API}{p}")
        assert r.status_code != 403 or r.json().get("code") != "feature_disabled", (p, r.text)


# Global off -> 403 feature_disabled for omar (Al Noor) and sami (no override)
def test_pharmacy_off_globally(admin, omar, sami, alnoor, restore):
    assert admin.put(f"{API}/admin/flags/pharmacy_marketplace", json={"enabled": False}).status_code == 200
    for s in (omar, sami):
        for p in ["/pharmacy/pharmacies", "/pharmacy/cart", "/pharmacy/catalog"]:
            r = s.get(f"{API}{p}")
            assert r.status_code == 403, (p, r.status_code)
            assert r.json()["code"] == "feature_disabled"
        assert s.get(f"{API}/flags").json()["pharmacy_marketplace"] is False
        # other features still OK
        assert s.get(f"{API}/prescriptions").status_code == 200
    # unauthenticated falls through to auth (401)
    assert requests.get(f"{API}/pharmacy/cart").status_code == 401


# Account override ON re-enables for Al Noor only
def test_account_override_reenables(admin, omar, sami, alnoor, restore):
    feats = {**(alnoor.get("features") or {}), "pharmacy_marketplace": True}
    r = admin.patch(f"{API}/admin/accounts/{alnoor['account_id']}", json={"features": feats})
    assert r.status_code == 200 and r.json()["effective_flags"]["pharmacy_marketplace"] is True
    assert omar.get(f"{API}/pharmacy/cart").status_code == 200
    assert omar.get(f"{API}/flags").json()["pharmacy_marketplace"] is True
    sami_acc = sami.get(f"{API}/auth/me").json().get("account_id")
    if sami_acc != alnoor["account_id"]:
        assert sami.get(f"{API}/pharmacy/cart").status_code == 403


# Account override OFF while global ON
def test_account_override_off(admin, omar, alnoor, restore):
    admin.put(f"{API}/admin/flags/pharmacy_marketplace", json={"enabled": True})
    feats = {**(alnoor.get("features") or {}), "health_chat": False}
    admin.patch(f"{API}/admin/accounts/{alnoor['account_id']}", json={"features": feats})
    r = omar.get(f"{API}/chat/sessions")
    assert r.status_code == 403 and r.json()["code"] == "feature_disabled"
    admin.patch(f"{API}/admin/accounts/{alnoor['account_id']}", json={"features": alnoor.get("features") or {}})
    assert omar.get(f"{API}/chat/sessions").status_code == 200


# Restore verify
def test_restored(admin, omar, alnoor, restore):
    admin.put(f"{API}/admin/flags/pharmacy_marketplace", json={"enabled": True})
    admin.patch(f"{API}/admin/accounts/{alnoor['account_id']}", json={"features": {"white_label": True}})
    assert omar.get(f"{API}/pharmacy/cart").status_code == 200
    flags = {f["key"]: f for f in admin.get(f"{API}/admin/flags").json()["flags"]}
    assert all(f["enabled"] for k, f in flags.items() if k != "white_label")
    assert flags["white_label"]["enabled"] is False


# Checklist language
def test_checklist_language(admin, db):
    acc = admin.post(f"{API}/admin/accounts", json={"name": f"QA Lang {uuid.uuid4().hex[:4]}", "type": "clinic"}).json()
    aid = acc["account_id"]
    try:
        ov = admin.get(f"{API}/admin/accounts/{aid}/overview").json()
        lang = next(c for c in ov["checklist"] if c["key"] == "language")
        assert lang["done"] is False
        assert ov["checklist_done"] == 1
        admin.patch(f"{API}/admin/accounts/{aid}/branding", json={"default_language": "en"})
        ov = admin.get(f"{API}/admin/accounts/{aid}/overview").json()
        assert next(c for c in ov["checklist"] if c["key"] == "language")["done"] is True
        assert ov["checklist_done"] == 2
    finally:
        db.accounts.delete_one({"account_id": aid})


# Invite existing patient as staff -> 409, role unchanged
def test_invite_existing_patient_as_staff(admin, alnoor, db):
    before = db.users.find_one({"email": "omar.patient@sihha.ai"}, {"_id": 0, "role": 1, "account_id": 1, "account_role": 1})
    r = admin.post(f"{API}/admin/accounts/{alnoor['account_id']}/users",
                   json={"email": "omar.patient@sihha.ai", "name": "Omar", "role": "doctor"})
    assert r.status_code == 409
    assert "Approve clinician access" in r.json()["detail"]
    after = db.users.find_one({"email": "omar.patient@sihha.ai"}, {"_id": 0, "role": 1, "account_id": 1, "account_role": 1})
    assert after == before and after["role"] == "patient"
    # doctor invited as patient -> 409 too
    r = admin.post(f"{API}/admin/accounts/{alnoor['account_id']}/users",
                   json={"email": "dr.layla@sihha.ai", "name": "Layla", "role": "patient"})
    assert r.status_code == 409
    assert db.users.find_one({"email": "dr.layla@sihha.ai"})["role"] == "doctor"
