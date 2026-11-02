# Iteration 17: demo inbox, demo alert email, usage report PDFs, cron endpoints
import os, uuid, time, subprocess
import pytest, requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


def _env(key):
    for line in open("/app/backend/.env"):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


SECRET = _env("WEBHOOK_CRON_SECRET")
db = MongoClient(_env("MONGO_URL"))[_env("DB_NAME")]


def login(email, pw, path="/auth/login"):
    s = requests.Session()
    r = s.post(f"{API}{path}", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code} {r.text[:200]}")
    return s


@pytest.fixture(scope="module")
def admin():
    return login("admin@sihha.ai", "Admin@123")


@pytest.fixture(scope="module")
def layla():
    return login("dr.layla@sihha.ai", "Doctor@123")


@pytest.fixture(scope="module")
def omar():
    return login("omar.patient@sihha.ai", "Patient@123")


@pytest.fixture(scope="module")
def alnoor_id(admin):
    r = admin.get(f"{API}/admin/accounts")
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("accounts") or data.get("items")
    return next(a["account_id"] for a in items if a["name"].startswith("Al Noor"))


# ---- Demo alert settings ----
class TestDemoAlert:
    def test_get_put_alert(self, admin):
        orig = admin.get(f"{API}/admin/settings/demo-alert")
        assert orig.status_code == 200 and "email" in orig.json()
        r = admin.put(f"{API}/admin/settings/demo-alert", json={"email": "delivered+sihha-demo@resend.dev"})
        assert r.status_code == 200 and r.json()["email"] == "delivered+sihha-demo@resend.dev"
        assert admin.get(f"{API}/admin/settings/demo-alert").json()["email"] == "delivered+sihha-demo@resend.dev"

    def test_invalid_alert_email(self, admin):
        assert admin.put(f"{API}/admin/settings/demo-alert", json={"email": "notanemail"}).status_code == 422

    def test_non_admin_alert(self, omar, layla):
        assert omar.get(f"{API}/admin/settings/demo-alert").status_code == 403
        assert layla.put(f"{API}/admin/settings/demo-alert", json={"email": "a@example.com"}).status_code == 403


# ---- Demo requests inbox ----
class TestDemoInbox:
    def test_create_and_patch(self, admin, omar):
        db.demo_requests.delete_many({"organization": {"$regex": "^TEST_"}})
        db.demo_requests.delete_many({"ip": {"$exists": True}, "created_at": {"$gte": "2000"}, "organization": {"$regex": "^TEST_"}})
        tag = uuid.uuid4().hex[:6]
        r = requests.post(f"{API}/demo-requests", json={"name": "Test Person", "email": f"test{tag}@example.com",
                                                         "organization": f"TEST_Org {tag}", "role": "CIO", "message": "hi"})
        if r.status_code == 429:
            pytest.skip("rate limited")
        assert r.status_code == 200 and r.json() == {"ok": True}
        lst = admin.get(f"{API}/admin/demo-requests").json()
        item = next(i for i in lst if i["organization"] == f"TEST_Org {tag}")
        assert item["status"] == "new" and "ip" not in item and "_id" not in item
        rid = item["request_id"]
        p = admin.patch(f"{API}/admin/demo-requests/{rid}", json={"status": "contacted", "notes": "Called"})
        assert p.status_code == 200 and p.json()["status"] == "contacted" and p.json()["notes"] == "Called"
        again = next(i for i in admin.get(f"{API}/admin/demo-requests").json() if i["request_id"] == rid)
        assert again["status"] == "contacted" and again["notes"] == "Called"
        assert admin.patch(f"{API}/admin/demo-requests/{rid}", json={"status": "bogus"}).status_code == 422
        assert omar.patch(f"{API}/admin/demo-requests/{rid}", json={"status": "won"}).status_code == 403
        assert admin.patch(f"{API}/admin/demo-requests/demo_nope", json={"status": "won"}).status_code == 404
        assert omar.get(f"{API}/admin/demo-requests").status_code == 403
        time.sleep(4)
        log = subprocess.run(["tail", "-n", "60", "/var/log/supervisor/backend.err.log"], capture_output=True, text=True).stdout
        assert "delivered+sihha-demo@resend.dev" not in log
        db.demo_requests.delete_many({"organization": {"$regex": "^TEST_"}})

    def test_demo_bad_email(self):
        r = requests.post(f"{API}/demo-requests", json={"name": "Xx", "email": "bad@@", "organization": "TEST_O"})
        assert r.status_code == 422


# ---- Usage report PDFs ----
class TestUsageReport:
    def test_admin_report(self, admin, alnoor_id):
        r = admin.get(f"{API}/admin/accounts/{alnoor_id}/report", params={"month": "2026-01"})
        assert r.status_code == 200 and r.headers["content-type"].startswith("application/pdf")
        assert r.content[:4] == b"%PDF" and "attachment" in r.headers.get("content-disposition", "")

    def test_admin_report_default_month(self, admin, alnoor_id):
        r = admin.get(f"{API}/admin/accounts/{alnoor_id}/report")
        assert r.status_code == 200 and r.content[:4] == b"%PDF"

    def test_bad_month(self, admin, alnoor_id):
        assert admin.get(f"{API}/admin/accounts/{alnoor_id}/report", params={"month": "2026-13"}).status_code == 422
        assert admin.get(f"{API}/admin/accounts/ACC-NOPE00/report").status_code == 404

    def test_admin_report_forbidden(self, layla, omar, alnoor_id):
        assert layla.get(f"{API}/admin/accounts/{alnoor_id}/report").status_code == 403
        assert requests.get(f"{API}/admin/accounts/{alnoor_id}/report").status_code == 401

    def test_my_report(self, layla, omar):
        r = layla.get(f"{API}/account/report", params={"month": "2026-10"})
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
        assert omar.get(f"{API}/account/report").status_code == 403


# ---- Cron endpoints ----
class TestCron:
    @pytest.mark.parametrize("path", ["monthly-reports", "audio-purge"])
    def test_auth(self, path):
        assert requests.post(f"{API}/cron/{path}", json={}).status_code == 401
        assert requests.post(f"{API}/cron/{path}", json={}, headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert requests.post(f"{API}/cron/{path}", json={}, headers={"Authorization": SECRET}).status_code == 401

    def test_audio_purge_ok_idempotent(self):
        wid = f"TEST_purge_{uuid.uuid4().hex[:8]}"
        h = {"Authorization": f"Bearer {SECRET}", "X-Webhook-Id": wid}
        for _ in range(2):
            r = requests.post(f"{API}/cron/audio-purge", json={}, headers=h)
            assert r.status_code == 200 and r.json() == {"accepted": True}
        assert db.cron_runs.count_documents({"run_id": wid}) == 1
        db.cron_runs.delete_many({"run_id": wid})

    def test_monthly_reports_sets_last_sent(self):
        wid = f"TEST_monthly_{uuid.uuid4().hex[:8]}"
        h = {"Authorization": f"Bearer {SECRET}", "X-Webhook-Id": wid}
        db.accounts.update_many({}, {"$unset": {"last_report_sent": ""}})
        r1 = requests.post(f"{API}/cron/monthly-reports", json={"run_id": "x"}, headers=h)
        r2 = requests.post(f"{API}/cron/monthly-reports", json={}, headers=h)
        assert r1.status_code == 200 and r2.status_code == 200 and r1.json() == {"accepted": True}
        assert db.cron_runs.count_documents({"run_id": wid}) == 1
        time.sleep(10)
        from datetime import datetime, timezone, timedelta
        first = datetime.now(timezone.utc).replace(day=1)
        prev = (first - timedelta(days=1)).strftime("%Y-%m")
        accts = list(db.accounts.find({"status": {"$ne": "suspended"}}, {"_id": 0, "name": 1, "last_report_sent": 1}))
        assert accts and all(a.get("last_report_sent") == prev for a in accts), accts
        db.cron_runs.delete_many({"run_id": wid})

    def test_invalid_body(self):
        r = requests.post(f"{API}/cron/audio-purge", data="notjson",
                          headers={"Authorization": f"Bearer {SECRET}", "Content-Type": "application/json"})
        assert r.status_code in (200, 400)
