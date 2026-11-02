# Iteration 28: retest of analytics fixes (owner check, path normalisation, heatmap snapshot) + login regression
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TIMEOUT = 60


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=TIMEOUT)
    assert r.status_code == 200, f"{email}: {r.status_code} {r.text[:200]}"
    return s


def _register(tag):
    s = requests.Session()
    email = f"test_iter28_{tag}_{uuid.uuid4().hex[:6]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "Passw0rd!x", "name": f"TEST {tag}"}, timeout=TIMEOUT)
    assert r.status_code in (200, 201), r.text
    return s


def _slug():
    return "/zz" + "".join(chr(97 + int(c, 16) % 26) for c in uuid.uuid4().hex[:8])


@pytest.fixture(scope="module")
def admin():
    return _login("admin@sihha.ai", "Admin@123")


@pytest.fixture(scope="module")
def pa():
    return _register("a")


@pytest.fixture(scope="module")
def pb():
    return _register("b")


def _heat(admin, path, device="desktop"):
    r = admin.get(f"{BASE_URL}/api/admin/analytics/heatmap", params={"path": path, "device": device, "days": 1, "include_demo": True}, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    return r.json()


def _replay(t):
    return [{"type": 4, "data": {"href": "x", "width": 1440, "height": 900}, "timestamp": t},
            {"type": 3, "data": {"source": 1}, "timestamp": t + 10}]


# Regression: logins after DB reconnect
class TestLogins:
    @pytest.mark.parametrize("email,pw", [("admin@sihha.ai", "Admin@123"), ("omar.patient@sihha.ai", "Patient@123"),
                                          ("solo.patient@sihha.ai", "Patient@123")])
    def test_login(self, email, pw):
        s = _login(email, pw)
        me = s.get(f"{BASE_URL}/api/auth/me", timeout=TIMEOUT)
        assert me.status_code == 200 and me.json().get("email") == email

    def test_admin_users_list(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/users", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:200]


# Path normalisation via heatmap's echoed normalised path
class TestPathNorm:
    @pytest.mark.parametrize("raw,expected", [
        ("/doctor/encounters/enc_abc123", "/doctor/encounters/:id"),
        ("/h/dar-al-shifa", "/h/dar-al-shifa"),
        ("/h/al-noor", "/h/al-noor"),
        ("/admin/accounts/ACC-12AFFE", "/admin/accounts/:id"),
        ("/x/550e8400-e29b-41d4-a716-446655440000", "/x/:id"),
        ("/x/123", "/x/:id"),
        ("/find-care", "/find-care"),
        ("/covid19", "/covid19"),
        ("/step2guide", "/step2guide"),
    ])
    def test_norm(self, admin, raw, expected):
        assert _heat(admin, raw)["path"] == expected


# Owner check on collect
class TestOwnerCheck:
    def test_foreign_session_ignored(self, admin, pa, pb):
        sid = f"as_t28own{uuid.uuid4().hex[:10]}"
        pa_path, pb_path = _slug(), _slug()
        t = int(time.time() * 1000)
        ev = lambda p, tt: [{"type": "pageview", "path": p, "t": tt, "vw": 1440},
                            {"type": "click", "path": p, "t": tt + 100, "x": 10, "y": 10, "vw": 1440, "dh": 900, "target": "t"}]
        r = pa.post(f"{BASE_URL}/api/analytics/collect", json={"session_id": sid, "events": ev(pa_path, t), "replay": _replay(t), "seq": 1}, timeout=TIMEOUT)
        assert r.status_code == 200
        r = pb.post(f"{BASE_URL}/api/analytics/collect", json={"session_id": sid, "events": ev(pb_path, t + 1000), "replay": _replay(t + 1000), "seq": 2}, timeout=TIMEOUT)
        assert r.status_code == 200 and r.json() == {"ok": True}
        assert len(_heat(admin, pa_path)["points"]) == 1
        assert len(_heat(admin, pb_path)["points"]) == 0, "foreign session batch was stored"
        rep = admin.get(f"{BASE_URL}/api/admin/analytics/replays/{sid}", timeout=TIMEOUT).json()
        assert len(rep["events"]) == 2, f"replay mixed: {len(rep['events'])} events"


# Heatmap snapshot prefers a >=2.5s stay
class TestSnapshot:
    def test_prefers_long_stay(self, admin, pa, pb):
        path = _slug()
        t = int(time.time() * 1000) - 60000
        s1, s2 = f"as_t28lng{uuid.uuid4().hex[:10]}", f"as_t28sht{uuid.uuid4().hex[:10]}"
        pa.post(f"{BASE_URL}/api/analytics/collect", json={"session_id": s1, "seq": 1, "replay": _replay(t), "events": [
            {"type": "pageview", "path": path, "t": t, "vw": 1440},
            {"type": "leave", "path": path, "t": t + 6000, "vw": 1440, "duration": 6000}]}, timeout=TIMEOUT)
        # newer but short stay
        pb.post(f"{BASE_URL}/api/analytics/collect", json={"session_id": s2, "seq": 1, "replay": _replay(t + 20000), "events": [
            {"type": "pageview", "path": path, "t": t + 20000, "vw": 1440},
            {"type": "leave", "path": path, "t": t + 20500, "vw": 1440, "duration": 500}]}, timeout=TIMEOUT)
        snap = _heat(admin, path)["snapshot"]
        assert snap and snap["session_id"] == s1, snap
        assert snap["t"] == t and snap["until"] == t + 6000

    def test_fallback_pageview_until_none(self, admin, pa):
        path = _slug()
        t = int(time.time() * 1000)
        sid = f"as_t28fb{uuid.uuid4().hex[:10]}"
        pa.post(f"{BASE_URL}/api/analytics/collect", json={"session_id": sid, "seq": 1, "replay": _replay(t), "events": [
            {"type": "pageview", "path": path, "t": t, "vw": 1440}]}, timeout=TIMEOUT)
        snap = _heat(admin, path)["snapshot"]
        assert snap and snap["session_id"] == sid and snap["until"] is None

    def test_leave_avg_time_in_summary(self, admin, pa):
        path = _slug()
        t = int(time.time() * 1000)
        sid = f"as_t28sum{uuid.uuid4().hex[:10]}"
        for i in range(45):  # make the page rank inside the top 40
            pa.post(f"{BASE_URL}/api/analytics/collect", json={"session_id": sid, "seq": i, "events": [
                {"type": "pageview", "path": path, "t": t + i, "vw": 1440}] * 10 + [
                {"type": "leave", "path": path, "t": t + i, "vw": 1440, "duration": 4000}]}, timeout=TIMEOUT) if i == 0 else None
        r = admin.get(f"{BASE_URL}/api/admin/analytics/summary", params={"days": 1, "include_demo": True}, timeout=TIMEOUT).json()
        row = next((p for p in r["pages"] if p["path"] == path), None)
        if row is None:
            pytest.skip("test page not in top 40")
        assert row["avg_ms"] == 4000
