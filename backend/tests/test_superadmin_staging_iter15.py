# Iteration 15: staging env, super admin accounts, feature flags, white-label tenant, account admin, demo requests, PWA, lockout
import os
import uuid
import pytest
import requests
from pymongo import MongoClient
from dotenv import dotenv_values

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', dotenv_values('/app/frontend/.env').get('REACT_APP_BACKEND_URL')).rstrip('/')
API = f"{BASE_URL}/api"
BENV = dotenv_values('/app/backend/.env')


def login(email, pw, page="clinician"):
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
def layla():
    return login("dr.layla@sihha.ai", "Doctor@123")


@pytest.fixture(scope="module")
def alnoor(admin):
    r = admin.get(f"{API}/admin/accounts", params={"q": "Al Noor"})
    items = r.json()["items"]
    assert items, "Al Noor account not seeded"
    return items[0]


@pytest.fixture(scope="module")
def qa_account(admin, db):
    r = admin.post(f"{API}/admin/accounts", json={"name": f"QA Test {uuid.uuid4().hex[:4]}", "type": "clinic"})
    assert r.status_code == 200, r.text
    acc = r.json()
    yield acc
    db.users.delete_many({"account_id": acc["account_id"], "email": {"$regex": "(example.com|resend.dev)$"}})
    db.imported_records.delete_many({"account_id": acc["account_id"]})
    db.accounts.delete_one({"account_id": acc["account_id"]})


# Env
def test_env_staging():
    r = requests.get(f"{API}/env")
    assert r.status_code == 200
    assert r.json() == {"env": "staging", "is_staging": True}


# Access control
def test_non_admin_forbidden(omar):
    for path in ["/admin/accounts", "/admin/flags", "/admin/search?q=a", "/admin/demo-requests", "/account/overview"]:
        assert omar.get(f"{API}{path}").status_code == 403, path


# Accounts list/search/filter
def test_accounts_list_search(admin, alnoor):
    r = admin.get(f"{API}/admin/accounts")
    d = r.json()
    assert d["total"] >= 3
    assert alnoor["account_id"].startswith("ACC-") and len(alnoor["account_id"]) == 10
    frag = alnoor["account_id"][4:8]
    r = admin.get(f"{API}/admin/accounts", params={"q": frag})
    assert any(a["account_id"] == alnoor["account_id"] for a in r.json()["items"])
    r = admin.get(f"{API}/admin/accounts", params={"type": "clinic"})
    assert all(a["type"] == "clinic" for a in r.json()["items"])
    r = admin.get(f"{API}/admin/accounts", params={"status": "subscribed"})
    assert all(a["status"] == "subscribed" for a in r.json()["items"])
    assert alnoor["staff_count"] >= 1 and alnoor["customer_count"] >= 1


def test_accounts_export(admin):
    r = admin.get(f"{API}/admin/accounts/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert r.text.startswith("account_id,name,type,status")


def test_create_account_validation(admin):
    assert admin.post(f"{API}/admin/accounts", json={"name": "Q"}).status_code == 422
    assert admin.post(f"{API}/admin/accounts", json={"name": "QA x", "type": "bad"}).status_code == 422


def test_account_get_patch_status(admin, qa_account):
    aid = qa_account["account_id"]
    assert aid.startswith("ACC-")
    r = admin.patch(f"{API}/admin/accounts/{aid}", json={"status": "subscribed"})
    assert r.status_code == 200 and r.json()["status"] == "subscribed"
    assert admin.get(f"{API}/admin/accounts/{aid.lower()}").json()["status"] == "subscribed"
    assert admin.get(f"{API}/admin/accounts/ACC-ZZZZZZ").status_code == 404


def test_overview(admin, alnoor):
    r = admin.get(f"{API}/admin/accounts/{alnoor['account_id']}/overview")
    assert r.status_code == 200
    d = r.json()
    assert len(d["checklist"]) == 8 and d["customer_count"] >= 1


# Staff / invite
def test_invite_and_role(admin, qa_account):
    aid = qa_account["account_id"]
    email = f"delivered+qa{uuid.uuid4().hex[:6]}@resend.dev"
    r = admin.post(f"{API}/admin/accounts/{aid}/users", json={"email": email, "name": "QA Staff", "role": "doctor"})
    assert r.status_code == 200 and r.json()["invited"] is True
    uid = r.json()["user_id"]
    staff = admin.get(f"{API}/admin/accounts/{aid}/users", params={"kind": "staff"}).json()["items"]
    row = next(u for u in staff if u["user_id"] == uid)
    assert row["status"] == "invited"
    r = admin.patch(f"{API}/admin/accounts/{aid}/users/{uid}", json={"account_role": "account_admin"})
    assert r.status_code == 200
    staff = admin.get(f"{API}/admin/accounts/{aid}/users", params={"kind": "staff", "q": "QA Staff"}).json()["items"]
    assert staff[0]["account_role"] == "account_admin"
    # invite someone in another account -> 409
    r = admin.post(f"{API}/admin/accounts/{aid}/users", json={"email": "omar.patient@sihha.ai", "name": "x"})
    assert r.status_code == 409
    assert admin.post(f"{API}/admin/accounts/{aid}/users", json={"email": "bad", "name": "x"}).status_code == 422


# Branding / domain
def test_branding_and_domain(admin, qa_account, alnoor):
    aid = qa_account["account_id"]
    r = admin.patch(f"{API}/admin/accounts/{aid}/branding", json={"display_name": "QA Brand", "primary_color": "#112233", "default_language": "en"})
    assert r.status_code == 200
    d = r.json()
    assert d["branding"]["display_name"] == "QA Brand" and d["default_language"] == "en"
    assert admin.patch(f"{API}/admin/accounts/{aid}/branding", json={"primary_color": "red"}).status_code == 422
    assert admin.patch(f"{API}/admin/accounts/{aid}/branding", json={"custom_domain": "not a domain"}).status_code == 422
    dom = f"qa{uuid.uuid4().hex[:6]}.example.com"
    assert admin.patch(f"{API}/admin/accounts/{aid}/branding", json={"custom_domain": dom}).status_code == 200
    # duplicate on another account
    r = admin.patch(f"{API}/admin/accounts/{alnoor['account_id']}/branding", json={"custom_domain": dom})
    assert r.status_code == 409
    v = admin.post(f"{API}/admin/accounts/{aid}/domain/verify")
    assert v.status_code == 200 and v.json()["verified"] is False


def test_logo_upload(admin, qa_account):
    aid = qa_account["account_id"]
    png = bytes.fromhex("89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4890000000D4944415478DA63F8FFFF3F0005FE02FEA7D6A0D30000000049454E44AE426082")
    r = admin.post(f"{API}/admin/accounts/{aid}/logo", files={"file": ("l.png", png, "image/png")})
    assert r.status_code == 200, r.text
    assert r.json()["logo_url"]
    lg = requests.get(f"{BASE_URL}{r.json()['logo_url']}")
    assert lg.status_code == 200 and lg.content == png
    bad = admin.post(f"{API}/admin/accounts/{aid}/logo", files={"file": ("l.txt", b"hi", "text/plain")})
    assert bad.status_code == 415


# Import
def test_import(admin, qa_account):
    aid = qa_account["account_id"]
    e1 = f"qa.imp{uuid.uuid4().hex[:6]}@example.com"
    csv_text = f"name,email,conditions,medications,last_visit\nQA Imp One,{e1},Diabetes;Asthma,Metformin,2025-10-01\nNo Email,,x,,\n"
    r = admin.post(f"{API}/admin/accounts/{aid}/import", files={"file": ("p.csv", csv_text.encode(), "text/csv")})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["created"] == 1 and d["error_count"] == 1
    cust = admin.get(f"{API}/admin/accounts/{aid}/users", params={"kind": "customers"}).json()["items"]
    row = next(u for u in cust if u["email"] == e1)
    assert row["history"]["conditions"] == ["Diabetes", "Asthma"]
    r = admin.post(f"{API}/admin/accounts/{aid}/import", files={"file": ("p.csv", b"foo,bar\n1,2\n", "text/csv")})
    assert r.status_code == 422


# Quick search
def test_admin_search(admin):
    d = admin.get(f"{API}/admin/search", params={"q": "omar"}).json()
    assert any(u["email"] == "omar.patient@sihha.ai" for u in d["users"])
    d = admin.get(f"{API}/admin/search", params={"q": "ACC-"}).json()
    assert len(d["accounts"]) >= 1


# Flags
def test_flags_global_toggle(admin, omar, db):
    r = admin.get(f"{API}/admin/flags")
    flags = {f["key"]: f for f in r.json()["flags"]}
    assert flags["white_label"]["enabled"] is False
    try:
        r = admin.put(f"{API}/admin/flags/pharmacy_marketplace", json={"enabled": False})
        assert r.status_code == 200
        # omar belongs to Al Noor; account override may exist
        acc = db.accounts.find_one({"account_id": omar.get(f"{API}/auth/me").json().get("account_id")}) or {}
        expected = (acc.get("features") or {}).get("pharmacy_marketplace", False)
        assert omar.get(f"{API}/flags").json()["pharmacy_marketplace"] is expected
        assert admin.put(f"{API}/admin/flags/nope", json={"enabled": False}).status_code == 404
    finally:
        admin.put(f"{API}/admin/flags/pharmacy_marketplace", json={"enabled": True})
    assert omar.get(f"{API}/flags").json()["pharmacy_marketplace"] is True


# Tenant
def test_tenant(alnoor, qa_account):
    t = requests.get(f"{API}/tenant", params={"account": alnoor["account_id"]}).json()["tenant"]
    assert t["name"] == "Al Noor Care" and t["primary_color"] == "#0F4C5C"
    assert requests.get(f"{API}/tenant", params={"account": qa_account["account_id"]}).json()["tenant"] is None


def test_register_on_tenant(alnoor, db, admin):
    email = f"qa.tenant{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"name": "QA Tenant Pt", "email": email, "password": "Passw0rd!",
                                                    "tenant_account_id": alnoor["account_id"]})
    try:
        assert r.status_code == 200, r.text
        cust = admin.get(f"{API}/admin/accounts/{alnoor['account_id']}/users", params={"kind": "customers", "q": email}).json()["items"]
        assert len(cust) == 1
    finally:
        db.users.delete_one({"email": email})


# Hospital admin
def test_account_overview_layla(layla):
    r = layla.get(f"{API}/account/overview")
    assert r.status_code == 200
    assert r.json()["account"]["name"].startswith("Al Noor")
    assert layla.get(f"{API}/account/users", params={"kind": "customers"}).status_code == 200
    assert layla.get(f"{API}/admin/accounts").status_code == 403


# Demo requests
def test_demo_requests(admin, db):
    email = f"qa.demo{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/demo-requests", json={"name": "QA Demo", "email": email, "organization": "QA Org"})
    assert r.status_code == 200
    rows = admin.get(f"{API}/admin/demo-requests").json()
    assert any(x["email"] == email for x in rows)
    assert all("ip" not in x for x in rows)
    assert requests.post(f"{API}/demo-requests", json={"name": "Q", "email": "x", "organization": "QA"}).status_code == 422
    db.demo_requests.delete_one({"email": email})


# PWA
def test_pwa_assets():
    m = requests.get(f"{BASE_URL}/manifest.json")
    assert m.status_code == 200
    j = m.json()
    sizes = {i["sizes"] for i in j["icons"]}
    assert "192x192" in sizes and "512x512" in sizes
    assert j["display"] == "standalone" and j["start_url"] and j["name"]
    sw = requests.get(f"{BASE_URL}/sw.js")
    assert sw.status_code == 200 and "javascript" in sw.headers.get("content-type", "")
    ic = requests.get(f"{BASE_URL}/icon-192.png")
    assert ic.status_code == 200 and ic.headers["content-type"].startswith("image/")


# Security: lockout vs XFF spoofing
def test_lockout_xff_spoof(db):
    email = f"spoofcheck-{uuid.uuid4().hex[:8]}@example.com"
    codes = []
    try:
        for i in range(7):
            r = requests.post(f"{API}/auth/login", json={"email": email, "password": "wrong"},
                              headers={"X-Forwarded-For": f"10.9.{i}.{i+1}"})
            codes.append(r.status_code)
        assert codes[:5] == [401] * 5, codes
        assert codes[5] == 429 and codes[6] == 429, codes
    finally:
        db.login_attempts.delete_many({"identifier": {"$regex": f"{email}$"}})
