# Iteration 25: super-admin Users tab (list/filter/detail/suspend/demo), platform stats demo exclusion, chat language/length rules
import os
import json
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = ("admin@sihha.ai", "Admin@123")
SOLO = ("solo.patient@sihha.ai", "Patient@123")
OMAR = ("omar.patient@sihha.ai", "Patient@123")


def login(email, pw, path="/api/auth/login"):
    s = requests.Session()
    r = s.post(f"{BASE_URL}{path}", json={"email": email, "password": pw})
    return s, r


@pytest.fixture(scope="module")
def admin():
    s, r = login(*ADMIN)
    if r.status_code != 200:
        pytest.skip(f"admin login failed {r.status_code} {r.text}")
    return s


@pytest.fixture(scope="module")
def solo_id(admin):
    r = admin.get(f"{BASE_URL}/api/admin/users", params={"q": "solo.patient", "include_demo": True})
    assert r.status_code == 200
    items = r.json()["items"]
    assert items, "solo.patient not found"
    uid = items[0]["user_id"]
    yield uid
    # restore
    admin.post(f"{BASE_URL}/api/admin/users/{uid}/suspend", json={"suspended": False})
    admin.post(f"{BASE_URL}/api/admin/users/{uid}/demo", json={"is_demo": True})


# --- Users list ---
class TestUsersList:
    def test_requires_admin(self):
        s, r = login(*OMAR)
        assert r.status_code == 200
        assert s.get(f"{BASE_URL}/api/admin/users").status_code == 403
        assert requests.get(f"{BASE_URL}/api/admin/users").status_code == 401

    def test_default_excludes_demo(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/users", params={"limit": 100})
        assert r.status_code == 200
        d = r.json()
        assert d["demo_hidden"] > 0
        emails = [u["email"] for u in d["items"]]
        print("REAL USERS:", d["total"], emails)
        assert all(not u["is_demo"] for u in d["items"])
        assert not any(re.search(r"(sihha\.ai|\.demo|example\.com|test\.com|resend\.dev)$", e) for e in emails)
        assert d["total"] == len(d["items"])

    def test_include_demo(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/users", params={"include_demo": True, "limit": 100})
        d = r.json()
        assert d["demo_hidden"] == 0
        assert any(u["is_demo"] for u in d["items"])
        sa = [u for u in d["items"] if u["email"] == "admin@sihha.ai"]
        assert sa and sa[0]["is_super_admin"] is True
        assert "_id" not in d["items"][0]
        assert "password_hash" not in d["items"][0]

    def test_search_role_status(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/users", params={"include_demo": True, "q": "omar.patient"}).json()
        assert r["total"] == 1 and r["items"][0]["email"] == "omar.patient@sihha.ai"
        r = admin.get(f"{BASE_URL}/api/admin/users", params={"include_demo": True, "role": "doctor", "limit": 100}).json()
        assert r["total"] > 0 and all(u["role"] == "doctor" for u in r["items"])
        r = admin.get(f"{BASE_URL}/api/admin/users", params={"include_demo": True, "status": "active", "limit": 100}).json()
        assert all(not u["suspended"] for u in r["items"])
        r = admin.get(f"{BASE_URL}/api/admin/users", params={"q": ".*"}).json()  # regex escaped
        assert r["total"] == 0

    def test_pagination(self, admin):
        p1 = admin.get(f"{BASE_URL}/api/admin/users", params={"include_demo": True, "limit": 5, "page": 1}).json()
        p2 = admin.get(f"{BASE_URL}/api/admin/users", params={"include_demo": True, "limit": 5, "page": 2}).json()
        assert len(p1["items"]) == 5 and len(p2["items"]) == 5
        assert not ({u["user_id"] for u in p1["items"]} & {u["user_id"] for u in p2["items"]})

    def test_detail_and_404(self, admin, solo_id):
        r = admin.get(f"{BASE_URL}/api/admin/users/{solo_id}")
        assert r.status_code == 200
        d = r.json()
        for k in ("active_days_30", "screenings", "reports", "medications", "vitals", "encounters", "dependents"):
            assert isinstance(d["activity"][k], int)
        assert admin.get(f"{BASE_URL}/api/admin/users/user_nope").status_code == 404


# --- Suspend / demo ---
class TestSuspendDemo:
    def test_super_admin_cannot_be_suspended(self, admin):
        me = admin.get(f"{BASE_URL}/api/auth/me").json()
        uid = me.get("user_id") or me.get("user", {}).get("user_id")
        r = admin.post(f"{BASE_URL}/api/admin/users/{uid}/suspend", json={"suspended": True})
        assert r.status_code == 400

    def test_suspend_flow(self, admin, solo_id):
        sess, r = login(*SOLO)
        assert r.status_code == 200
        assert sess.get(f"{BASE_URL}/api/auth/me").status_code == 200
        r = admin.post(f"{BASE_URL}/api/admin/users/{solo_id}/suspend", json={"suspended": True, "reason": "TEST_iter25"})
        assert r.status_code == 200 and r.json()["suspended"] is True and r.json()["suspended_reason"] == "TEST_iter25"
        # existing session gets 403
        r = sess.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 403 and r.json()["detail"] == "This account has been suspended. Contact Sihha support."
        # refresh 403
        assert sess.post(f"{BASE_URL}/api/auth/refresh").status_code == 403
        # new login 403
        _, r = login(*SOLO)
        assert r.status_code == 403 and "suspended" in r.json()["detail"]
        # status filter
        lst = admin.get(f"{BASE_URL}/api/admin/users", params={"include_demo": True, "status": "suspended"}).json()
        assert solo_id in [u["user_id"] for u in lst["items"]]
        # re-enable
        r = admin.post(f"{BASE_URL}/api/admin/users/{solo_id}/suspend", json={"suspended": False})
        assert r.json()["suspended"] is False and r.json()["suspended_reason"] is None
        _, r = login(*SOLO)
        assert r.status_code == 200

    def test_demo_toggle_counts(self, admin, solo_id):
        before = admin.get(f"{BASE_URL}/api/admin/users").json()["total"]
        st_before = admin.get(f"{BASE_URL}/api/admin/platform-stats").json()["roles"]["patient"]["total"]
        r = admin.post(f"{BASE_URL}/api/admin/users/{solo_id}/demo", json={"is_demo": False})
        assert r.status_code == 200 and r.json()["is_demo"] is False
        after = admin.get(f"{BASE_URL}/api/admin/users").json()
        assert after["total"] == before + 1
        assert solo_id in [u["user_id"] for u in admin.get(f"{BASE_URL}/api/admin/users", params={"q": "solo"}).json()["items"]]
        st_after = admin.get(f"{BASE_URL}/api/admin/platform-stats").json()["roles"]["patient"]["total"]
        assert st_after == st_before + 1
        r = admin.post(f"{BASE_URL}/api/admin/users/{solo_id}/demo", json={"is_demo": True})
        assert r.json()["is_demo"] is True
        assert admin.get(f"{BASE_URL}/api/admin/users").json()["total"] == before
        assert admin.post(f"{BASE_URL}/api/admin/users/user_nope/demo", json={"is_demo": True}).status_code == 404


# --- Platform stats ---
class TestPlatformStats:
    def test_stats_exclude_demo(self, admin):
        d = admin.get(f"{BASE_URL}/api/admin/platform-stats").json()
        real = admin.get(f"{BASE_URL}/api/admin/users", params={"limit": 100}).json()
        print("STATS totals", d["totals"], "real users", real["total"])
        real_non_admin = [u for u in real["items"] if u["role"] in ("patient", "doctor", "pharmacist")]
        assert d["totals"]["total"] == len(real_non_admin)


# --- Chat rules ---
def _stream(sess, sid, text):
    r = sess.post(f"{BASE_URL}/api/chat/sessions/{sid}/message", json={"text": text}, stream=True, timeout=120)
    assert r.status_code == 200, r.text
    out, err = [], None
    for line in r.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            ev = json.loads(line[6:])
            if ev.get("delta"):
                out.append(ev["delta"])
            if ev.get("error"):
                err = ev["error"]
    assert not err, err
    return "".join(out)


class TestChatRules:
    def test_english_conversation_and_cap(self):
        sess, r = login(*OMAR)
        assert r.status_code == 200
        sid = sess.post(f"{BASE_URL}/api/chat/sessions", json={"profile_id": "self"}).json()["chat_session_id"]
        msgs = sess.get(f"{BASE_URL}/api/chat/sessions/{sid}/messages").json()
        print("GREETING:", msgs[-1]["content"] if msgs else None)
        answers = ["I have a headache since yesterday", "It is on the front of my head, moderate",
                   "No fever, no vomiting", "I slept badly and drank little water", "No vision problems",
                   "I took paracetamol, it helped a bit", "Nothing else"]
        replies = []
        for a in answers:
            rep = _stream(sess, sid, a)
            replies.append(rep)
            print("REPLY:", rep)
            assert not re.search(r"[\u0600-\u06FF]", rep), f"Arabic in English chat: {rep}"
        q_counts = [rep.count("?") for rep in replies]
        print("question marks per reply", q_counts)
        # final reply(s) after cap should mention Download Report
        assert any("download report" in rep.lower() for rep in replies[3:]), "No closing summary within budget"
        self.__class__.sid = sid
        self.__class__.sess = sess

    def test_arabic_reply(self):
        sess, r = login(*OMAR)
        sid = sess.post(f"{BASE_URL}/api/chat/sessions", json={"profile_id": "self"}).json()["chat_session_id"]
        rep = _stream(sess, sid, "عندي ألم في المعدة منذ يومين")
        print("AR REPLY:", rep)
        assert re.search(r"[\u0600-\u06FF]", rep)
        rep2 = _stream(sess, sid, "Actually let me write in English. The pain is mild.")
        print("SWITCH REPLY:", rep2)
        assert not re.search(r"[\u0600-\u06FF]", rep2)
