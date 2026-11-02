# Iteration 27: product analytics (collect + admin endpoints), getting-started checklist, chat screening flow
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = ("admin@sihha.ai", "Admin@123")
TIMEOUT = 60


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=TIMEOUT)
    if r.status_code != 200:
        pytest.skip(f"login failed for {email}: {r.status_code}")
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def patient():
    email = f"test_iter27_{uuid.uuid4().hex[:8]}@example.com"
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "Passw0rd!x", "name": "TEST Iter27"}, timeout=TIMEOUT)
    assert r.status_code in (200, 201), r.text
    return email, s, r.json()


SID = f"as_test27{uuid.uuid4().hex[:10]}"
PATH = "/testpage-" + "".join(chr(97 + int(c, 16) % 26) for c in uuid.uuid4().hex[:6])  # no digits (digits => :id)


# Getting started checklist
class TestGettingStarted:
    def test_initial_state(self, patient):
        r = patient[1].get(f"{BASE_URL}/api/getting-started", timeout=TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert d["steps"] == {"chat": False, "medications": False, "pill_id": False, "find_care": False}
        assert d["done"] == 0 and d["total"] == 4
        assert d["tour_done"] is False and d["dismissed"] is False

    def test_find_care_and_tour_flags_persist(self, patient):
        s = patient[1]
        r = s.post(f"{BASE_URL}/api/getting-started", json={"find_care": True, "tour_done": True}, timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.json()["steps"]["find_care"] is True and r.json()["tour_done"] is True
        g = s.get(f"{BASE_URL}/api/getting-started", timeout=TIMEOUT).json()
        assert g["steps"]["find_care"] is True and g["done"] == 1 and g["tour_done"] is True and g["dismissed"] is False

    def test_medication_ticks_step(self, patient):
        s = patient[1]
        r = s.post(f"{BASE_URL}/api/medications", json={"name": "TEST_Panadol", "dosage": "500mg", "times": ["08:00"]}, timeout=TIMEOUT)
        assert r.status_code in (200, 201), r.text
        g = s.get(f"{BASE_URL}/api/getting-started", timeout=TIMEOUT).json()
        assert g["steps"]["medications"] is True and g["done"] == 2

    def test_chat_ticks_step(self, patient):
        s = patient[1]
        r = s.post(f"{BASE_URL}/api/chat/sessions", json={}, timeout=TIMEOUT)
        assert r.status_code in (200, 201), r.text
        sid = r.json()["chat_session_id"]
        g = s.get(f"{BASE_URL}/api/getting-started", timeout=TIMEOUT).json()
        assert g["steps"]["chat"] is False, "chat should require a user message, not just a session"
        m = s.post(f"{BASE_URL}/api/chat/sessions/{sid}/message", json={"text": "I have a mild headache"}, timeout=120)
        assert m.status_code == 200, m.text
        g = s.get(f"{BASE_URL}/api/getting-started", timeout=TIMEOUT).json()
        assert g["steps"]["chat"] is True and g["done"] == 3

    def test_empty_post_and_dismiss(self, patient):
        s = patient[1]
        assert s.post(f"{BASE_URL}/api/getting-started", json={}, timeout=TIMEOUT).status_code == 200
        r = s.post(f"{BASE_URL}/api/getting-started", json={"dismissed": True}, timeout=TIMEOUT)
        assert r.json()["dismissed"] is True

    def test_unauth(self):
        assert requests.get(f"{BASE_URL}/api/getting-started", timeout=TIMEOUT).status_code == 401


# Analytics collection
class TestCollect:
    def test_collect_patient(self, patient):
        t0 = int(time.time() * 1000)
        body = {"session_id": SID, "seq": 1, "events": [
            {"type": "pageview", "path": PATH, "t": t0, "vw": 1440},
            {"type": "click", "path": PATH, "t": t0 + 1000, "x": 50.5, "y": 300, "vw": 1440, "dh": 1500, "target": "test27-btn"},
            {"type": "rage", "path": PATH, "t": t0 + 1200, "x": 50.5, "y": 300, "vw": 1440, "dh": 1500, "target": "test27-btn"},
            {"type": "dead", "path": PATH, "t": t0 + 1500, "x": 10, "y": 100, "vw": 1440, "dh": 1500, "target": "div"},
            {"type": "pageview", "path": "/dashboard", "t": t0 + 2000, "vw": 1440},
            {"type": "leave", "path": PATH, "t": t0 + 2000, "vw": 1440, "duration": 2000},
            {"type": "bogus", "path": PATH, "t": t0 + 2100},
        ], "replay": [{"type": 4, "timestamp": t0, "data": {"href": "x", "width": 1440, "height": 900}}]}
        r = patient[1].post(f"{BASE_URL}/api/analytics/collect", json=body, timeout=TIMEOUT)
        assert r.status_code == 200 and r.json() == {"ok": True}

    def test_collect_unauth(self):
        r = requests.post(f"{BASE_URL}/api/analytics/collect", json={"session_id": SID, "events": []}, timeout=TIMEOUT)
        assert r.status_code == 401

    def test_collect_bad_session_id_ignored(self, patient):
        r = patient[1].post(f"{BASE_URL}/api/analytics/collect", json={"session_id": "bad id!", "events": [
            {"type": "pageview", "path": "/badsid27", "t": 1}]}, timeout=TIMEOUT)
        assert r.status_code == 200

    def test_admin_generates_no_data(self, admin):
        sid = f"as_admin27{uuid.uuid4().hex[:8]}"
        r = admin.post(f"{BASE_URL}/api/analytics/collect", json={"session_id": sid, "events": [
            {"type": "pageview", "path": "/admin27only", "t": int(time.time() * 1000), "vw": 1440}],
            "replay": [{"type": 4, "timestamp": 1}]}, timeout=TIMEOUT)
        assert r.status_code == 200
        rep = admin.get(f"{BASE_URL}/api/admin/analytics/replays/{sid}", timeout=TIMEOUT)
        assert rep.status_code == 404
        summ = admin.get(f"{BASE_URL}/api/admin/analytics/summary", params={"include_demo": True}, timeout=TIMEOUT).json()
        assert all(p["path"] != "/admin27only" for p in summ["pages"])


# Admin analytics endpoints
class TestAdminAnalytics:
    def test_requires_admin(self, patient):
        for ep in ("summary", "funnel", "journeys", "frustration", "replays"):
            assert patient[1].get(f"{BASE_URL}/api/admin/analytics/{ep}", timeout=TIMEOUT).status_code == 403, ep

    def test_summary_demo_filter(self, admin):
        with_demo = admin.get(f"{BASE_URL}/api/admin/analytics/summary", params={"days": 7, "include_demo": True}, timeout=TIMEOUT).json()
        page = next((p for p in with_demo["pages"] if p["path"] == PATH), None)
        assert page, f"{PATH} missing from summary pages"
        assert page["views"] == 1 and page["clicks"] == 1 and page["frustration"] == 2 and page["avg_ms"] == 2000
        for k in ("sessions", "users", "avg_session_ms", "pageviews", "clicks", "rage_clicks", "dead_clicks", "devices"):
            assert k in with_demo
        no_demo = admin.get(f"{BASE_URL}/api/admin/analytics/summary", params={"days": 7}, timeout=TIMEOUT).json()
        assert all(p["path"] != PATH for p in no_demo["pages"])

    def test_role_filter(self, admin):
        d = admin.get(f"{BASE_URL}/api/admin/analytics/summary", params={"role": "doctor", "include_demo": True}, timeout=TIMEOUT).json()
        assert all(p["path"] != PATH for p in d["pages"])

    def test_heatmap(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/analytics/heatmap", params={"path": PATH, "device": "desktop", "include_demo": True}, timeout=TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert len(d["points"]) == 3
        assert d["top_targets"][0] == {"target": "test27-btn", "clicks": 1}
        assert d["snapshot"] and d["snapshot"]["session_id"] == SID   # until is None since iter28: leave of 2s < 2.5s threshold
        mob = admin.get(f"{BASE_URL}/api/admin/analytics/heatmap", params={"path": PATH, "device": "mobile", "include_demo": True}, timeout=TIMEOUT).json()
        assert mob["points"] == [] and mob["snapshot"] is None

    def test_funnel(self, admin, patient):
        r = admin.get(f"{BASE_URL}/api/admin/analytics/funnel", params={"include_demo": True}, timeout=TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert [s["label"] for s in d["steps"]] == ["Signed up", "Finished profile", "Started a health chat",
                                                     "Added a medication", "Used Pill ID", "Opened Find Care"]
        assert d["steps"][0]["users"] == d["total"] >= 1
        assert "none_after_signup" in d
        users = [s["users"] for s in d["steps"]]
        assert all(u <= d["total"] for u in users)
        # demo excluded -> total smaller or equal
        nd = admin.get(f"{BASE_URL}/api/admin/analytics/funnel", timeout=TIMEOUT).json()
        assert nd["total"] <= d["total"]
        b2b = admin.get(f"{BASE_URL}/api/admin/analytics/funnel", params={"include_demo": True, "b2c_only": False}, timeout=TIMEOUT).json()
        assert b2b["total"] >= d["total"]

    def test_journeys(self, admin):
        d = admin.get(f"{BASE_URL}/api/admin/analytics/journeys", params={"include_demo": True}, timeout=TIMEOUT).json()
        assert any(t["from"] == PATH and t["to"] == "/dashboard" for t in d["transitions"])
        assert isinstance(d["entries"], list) and isinstance(d["exits"], list)

    def test_frustration(self, admin):
        d = admin.get(f"{BASE_URL}/api/admin/analytics/frustration", params={"include_demo": True}, timeout=TIMEOUT).json()
        mine = [r for r in d if r["path"] == PATH]
        assert {r["type"] for r in mine} == {"rage", "dead"}
        assert all(r["session_id"] == SID and r["users"] == 1 for r in mine)

    def test_replays(self, admin, patient):
        d = admin.get(f"{BASE_URL}/api/admin/analytics/replays", params={"include_demo": True, "frustrated": True}, timeout=TIMEOUT).json()
        row = next((r for r in d if r["session_id"] == SID), None)
        assert row and row["email"] == patient[0] and row["rage"] == 1 and row["dead"] == 1 and row["pageviews"] == 2
        assert "_id" not in row
        rep = admin.get(f"{BASE_URL}/api/admin/analytics/replays/{SID}", timeout=TIMEOUT)
        assert rep.status_code == 200 and len(rep.json()["events"]) == 1
        assert admin.get(f"{BASE_URL}/api/admin/analytics/replays/as_nonexistent999", timeout=TIMEOUT).status_code == 404
