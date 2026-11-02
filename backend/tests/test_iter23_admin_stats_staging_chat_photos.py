# Iteration 23: super-admin platform stats + activity tracking, staging hub + demo reset, tenant slug lookup,
# demo hospital (Dar Al Shifa) logins, branding slug/tagline, health-chat photos (keep / discard), report photo_ids.
import io
import json
import os

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
PHOTO = open(os.path.join(os.path.dirname(__file__), "fixtures", "hand.jpg"), "rb").read()


def _env(path, key):
    for line in open(path):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


MONGO = MongoClient(_env("/app/backend/.env", "MONGO_URL"))[_env("/app/backend/.env", "DB_NAME")]
JEDDAH = "ACC-2BC6ED"
STATE = {}


def login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    s.me = r.json()
    return s


@pytest.fixture(scope="module")
def admin():
    return login("admin@sihha.ai", "Admin@123")


@pytest.fixture(scope="module")
def omar():
    return login("omar.patient@sihha.ai", "Patient@123")


@pytest.fixture(scope="module")
def layla():
    return login("dr.layla@sihha.ai", "Doctor@123")


def stream(s, sid, payload):
    r = s.post(f"{API}/chat/sessions/{sid}/message", json=payload, stream=True, timeout=180)
    if r.status_code != 200:
        return r.status_code, r.text
    out, err = [], None
    for line in r.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            ev = json.loads(line[6:])
            out.append(ev.get("delta", ""))
            err = err or ev.get("error")
    return 200, ("".join(out), err)


# ---- Platform stats + activity ----
class TestPlatformStats:
    def test_admin_stats_shape(self, admin):
        r = admin.get(f"{API}/admin/platform-stats")
        assert r.status_code == 200, r.text
        d = r.json()
        for role in ("patient", "doctor", "pharmacist"):
            row = d["roles"][role]
            for k in ("total", "in_good_standing", "active_today", "active_week", "active_month"):
                assert isinstance(row[k], int)
            assert row["active_today"] <= row["active_week"] <= row["active_month"] <= row["total"]
        assert len(d["daily_active"]) == 30
        assert d["accounts"]["total"] >= 4 and isinstance(d["pharmacies"], int)

    def test_non_admin_forbidden(self, omar, layla):
        assert omar.get(f"{API}/admin/platform-stats").status_code == 403
        assert layla.get(f"{API}/admin/platform-stats").status_code == 403

    def test_login_records_activity(self, admin):
        MONGO.users.update_one({"email": "sultan@darshifa.demo"}, {"$unset": {"last_login_at": "", "last_seen_at": ""}})
        uid = MONGO.users.find_one({"email": "sultan@darshifa.demo"})["user_id"]
        MONGO.user_activity_days.delete_many({"user_id": uid})
        before = admin.get(f"{API}/admin/platform-stats").json()["roles"]["patient"]["active_today"]
        login("sultan@darshifa.demo", "Demo@123")
        u = MONGO.users.find_one({"user_id": uid})
        assert u.get("last_login_at") and u.get("last_seen_at")
        assert MONGO.user_activity_days.count_documents({"user_id": uid}) == 1
        after = admin.get(f"{API}/admin/platform-stats").json()["roles"]["patient"]["active_today"]
        assert after == before + 1


# ---- Staging hub + demo reset ----
class TestStaging:
    def test_hub(self, admin):
        r = admin.get(f"{API}/admin/staging")
        assert r.status_code == 200
        d = r.json()
        assert d["is_staging"] is True
        slugs = {a["slug"]: a for a in d["white_label_accounts"]}
        assert "al-noor" in slugs and "dar-al-shifa" in slugs
        assert len(slugs["dar-al-shifa"]["demo_logins"]) == 3
        assert any(t["email"] == "admin@sihha.ai" for t in d["test_logins"])

    def test_hub_forbidden_non_admin(self, omar):
        assert omar.get(f"{API}/admin/staging").status_code == 403
        assert omar.post(f"{API}/admin/staging/reset-demo").status_code == 403

    def test_reset_idempotent(self, admin):
        for _ in range(2):
            r = admin.post(f"{API}/admin/staging/reset-demo")
            assert r.status_code == 200 and r.json()["slug"] == "dar-al-shifa"
        assert MONGO.accounts.count_documents({"slug": "dar-al-shifa"}) == 1
        assert MONGO.users.count_documents({"email": {"$regex": "@darshifa\\.demo$"}}) == 4
        reem = MONGO.users.find_one({"email": "reem@darshifa.demo"})
        assert MONGO.vitals.count_documents({"profile_id": reem["user_id"]}) == 21
        assert MONGO.medications.count_documents({"profile_id": reem["user_id"]}) == 1


# ---- Tenant lookup + demo logins ----
class TestTenant:
    def test_slug_lookup(self):
        t = requests.get(f"{API}/tenant", params={"slug": "dar-al-shifa"}).json()["tenant"]
        assert t["name"] == "Dar Al Shifa" and t["primary_color"].upper() == "#7A1F3D"
        assert t["city"] == "Riyadh" and t["tagline"]
        assert {d["email"] for d in t["demo_logins"]} == {"admin@darshifa.demo", "dr.faris@darshifa.demo", "reem@darshifa.demo"}
        STATE["dar_id"] = t["account_id"]
        assert requests.get(f"{API}/tenant", params={"slug": "al-noor"}).json()["tenant"]["account_id"] == "ACC-12AFFE"
        assert requests.get(f"{API}/tenant", params={"slug": "unknown-slug"}).json()["tenant"] is None

    def test_demo_logins(self):
        dar = requests.get(f"{API}/tenant", params={"slug": "dar-al-shifa"}).json()["tenant"]["account_id"]
        reem = login("reem@darshifa.demo", "Demo@123")
        assert reem.me["role"] == "patient" and reem.me["account_id"] == dar
        faris = login("dr.faris@darshifa.demo", "Demo@123")
        assert faris.me["role"] == "doctor"
        adm = login("admin@darshifa.demo", "Demo@123")
        assert adm.me["account_role"] == "account_admin" and adm.me["account_id"] == dar
        vit = sorted(MONGO.vitals.find({"profile_id": reem.me["user_id"]}), key=lambda v: v["recorded_at"])
        assert vit[-1]["systolic"] > vit[0]["systolic"]
        # faris sees reem
        r = faris.get(f"{API}/doctor/patients")
        assert r.status_code == 200 and any(p.get("user_id") == reem.me["user_id"] for p in r.json())


# ---- Branding slug / tagline ----
class TestBranding:
    def test_slug_validation_and_conflict(self, admin):
        orig = MONGO.accounts.find_one({"account_id": JEDDAH}, {"_id": 0, "slug": 1, "tagline": 1})
        try:
            for bad in ("AB", "Upper-Case", "ab", "-abc", "a" * 41, "has space"):
                assert admin.patch(f"{API}/admin/accounts/{JEDDAH}/branding", json={"slug": bad}).status_code == 422, bad
            assert admin.patch(f"{API}/admin/accounts/{JEDDAH}/branding", json={"slug": "al-noor"}).status_code == 409
            r = admin.patch(f"{API}/admin/accounts/{JEDDAH}/branding", json={"slug": "test-jeddah-23", "tagline": "TEST_ tagline"})
            assert r.status_code == 200, r.text
            assert r.json().get("slug") == "test-jeddah-23" and r.json().get("tagline") == "TEST_ tagline"
            # Jeddah has white_label off -> public tenant lookup must stay hidden
            assert requests.get(f"{API}/tenant", params={"slug": "test-jeddah-23"}).json()["tenant"] is None
        finally:
            MONGO.accounts.update_one({"account_id": JEDDAH}, {"$unset": {"slug": "", "tagline": ""}})
            if orig.get("slug") or orig.get("tagline"):
                MONGO.accounts.update_one({"account_id": JEDDAH}, {"$set": {k: v for k, v in orig.items() if v}})


# ---- Health chat photos ----
class TestChatPhotos:
    @pytest.fixture(scope="class", autouse=True)
    def session(self, omar):
        sid = omar.post(f"{API}/chat/sessions", json={}).json()["chat_session_id"]
        STATE["sid"] = sid
        yield sid
        MONGO.chat_sessions.delete_many({"chat_session_id": sid})
        MONGO.chat_messages.delete_many({"chat_session_id": sid})
        MONGO.chat_photos.delete_many({"chat_session_id": sid})
        for rep in MONGO.health_reports.find({"chat_session_id": sid}):
            MONGO.agent_runs.delete_many({"report_id": rep["report_id"]})
            MONGO.alerts.delete_many({"report_id": rep["report_id"]})
        MONGO.health_reports.delete_many({"chat_session_id": sid})

    def up(self, s, keep, data=PHOTO, name="hand.jpg", ctype="image/jpeg"):
        return s.post(f"{API}/chat/sessions/{STATE['sid']}/photos", files={"file": (name, data, ctype)},
                      data={"keep": "true" if keep else "false"})

    def test_reject_non_image_and_big(self, omar):
        assert self.up(omar, True, b"hello world", "a.txt", "text/plain").status_code == 422
        assert self.up(omar, True, b"0" * (10 * 1024 * 1024 + 10)).status_code == 413

    def test_empty_message_rejected(self, omar):
        assert omar.post(f"{API}/chat/sessions/{STATE['sid']}/message", json={"text": "  "}).status_code == 422

    def test_kept_photo_access(self, omar, layla):
        r = self.up(omar, True)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["kept"] is True and d["url"] == f"/api/chat/photos/{d['photo_id']}"
        STATE["kept"] = d["photo_id"]
        g = omar.get(f"{API}/chat/photos/{d['photo_id']}")
        assert g.status_code == 200 and g.headers["content-type"] == "image/jpeg" and g.content[:2] == b"\xff\xd8"
        assert layla.get(f"{API}/chat/photos/{d['photo_id']}").status_code == 200
        noura = login("noura.patient@sihha.ai", "Patient@123")
        assert noura.get(f"{API}/chat/photos/{d['photo_id']}").status_code == 404
        ph = login("pharmacist@aldawaa.sihha.ai", "Pharma@123")
        assert ph.get(f"{API}/chat/photos/{d['photo_id']}").status_code == 404
        faris = login("dr.faris@darshifa.demo", "Demo@123")
        assert faris.get(f"{API}/chat/photos/{d['photo_id']}").status_code in (403, 404)
        assert requests.get(f"{API}/chat/photos/{d['photo_id']}").status_code == 401

    def test_pharmacist_cannot_upload(self):
        ph = login("pharmacist@aldawaa.sihha.ai", "Pharma@123")
        r = ph.post(f"{API}/chat/sessions/{STATE['sid']}/photos", files={"file": ("h.jpg", PHOTO, "image/jpeg")})
        assert r.status_code in (403, 404)

    def test_send_kept_photo_llm_sees_it(self, omar):
        code, (text, err) = stream(omar, STATE["sid"], {"text": "I have pain in my hand knuckles, what do you see?",
                                                         "photo_id": STATE["kept"]})
        assert code == 200 and not err, err
        print("AI kept reply:", text[:400])
        assert len(text) > 20
        assert any(w in text.lower() for w in ("hand", "finger", "knuckle", "ring", "skin")), text
        msgs = omar.get(f"{API}/chat/sessions/{STATE['sid']}/messages").json()
        user_msgs = [m for m in msgs if m["role"] == "user"]
        assert user_msgs[-1]["photo_id"] == STATE["kept"] and user_msgs[-1]["photo_discarded"] is False

    def test_discarded_photo(self, omar):
        r = self.up(omar, False)
        assert r.status_code == 200 and r.json()["kept"] is False and r.json()["url"] is None
        pid = r.json()["photo_id"]
        assert omar.get(f"{API}/chat/photos/{pid}").status_code == 404
        code, (text, err) = stream(omar, STATE["sid"], {"text": "", "photo_id": pid})
        assert code == 200 and not err, err
        print("AI discard reply:", text[:400])
        assert len(text) > 20
        code2, body = stream(omar, STATE["sid"], {"text": "again", "photo_id": pid})
        assert code2 == 404 and "expired" in body
        msgs = omar.get(f"{API}/chat/sessions/{STATE['sid']}/messages").json()
        last_user = [m for m in msgs if m["role"] == "user"][-1]
        assert last_user["photo_id"] is None and last_user["photo_discarded"] is True
        assert MONGO.chat_photos.count_documents({"photo_id": pid}) == 0

    def test_report_includes_photo_and_doctor_sees(self, omar, layla):
        r = omar.post(f"{API}/chat/sessions/{STATE['sid']}/report", timeout=240)
        assert r.status_code == 200, r.text
        rep = r.json()
        assert rep["photo_ids"] == [STATE["kept"]]
        STATE["report"] = rep["report_id"]
        s = layla.get(f"{API}/doctor/patients/{omar.me['user_id']}/summary")
        assert s.status_code == 200
        reports = s.json().get("reports") or s.json().get("recent_reports") or []
        match = [x for x in reports if x["report_id"] == rep["report_id"]]
        assert match and match[0]["photo_ids"] == [STATE["kept"]]
