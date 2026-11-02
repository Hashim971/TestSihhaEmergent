# Iteration 26: retest of iter25 fixes — register sets last_login_at, sign_in_method in admin users, google suspended check (code)
import os
import re
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = ("admin@sihha.ai", "Admin@123")


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
    if r.status_code != 200:
        pytest.skip(f"admin login failed {r.status_code}")
    return s


@pytest.fixture(scope="module")
def new_user():
    email = f"test_iter26_{uuid.uuid4().hex[:8]}@example.com"
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "Passw0rd!x", "name": "TEST Iter26"})
    assert r.status_code in (200, 201), r.text
    return email, s, r.json()


# Register -> last_login_at
class TestRegisterLastLogin:
    def test_register_sets_last_login(self, admin, new_user):
        email = new_user[0]
        r = admin.get(f"{BASE_URL}/api/admin/users", params={"q": email, "include_demo": True})
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        u = items[0]
        assert u["last_login_at"], "last_login_at missing after register"
        assert u["is_demo"] is True
        assert u["sign_in_method"] == "Email & password"

    def test_new_example_user_hidden_by_default(self, admin, new_user):
        r = admin.get(f"{BASE_URL}/api/admin/users", params={"q": new_user[0]})
        assert r.status_code == 200
        assert r.json()["total"] == 0


# sign_in_method on detail + list
class TestSignInMethod:
    def test_detail_sign_in_method(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/users", params={"q": "omar.patient", "include_demo": True})
        uid = r.json()["items"][0]["user_id"]
        d = admin.get(f"{BASE_URL}/api/admin/users/{uid}")
        assert d.status_code == 200
        j = d.json()
        assert j["sign_in_method"] in ("Email & password", "Google", "Email & password + Google")
        assert "password_hash" not in j and "auth_providers" not in j and "_id" not in j

    def test_list_all_have_sign_in_method(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/users", params={"include_demo": True, "limit": 100})
        assert r.status_code == 200
        items = r.json()["items"]
        methods = {u["sign_in_method"] for u in items}
        print("METHODS:", methods)
        assert all(u.get("sign_in_method") for u in items)
        assert all("password_hash" not in u for u in items)


# Google session suspended check (static code check)
def test_google_session_suspended_check_present():
    src = open("/app/backend/server.py").read()
    i = src.index('@api.post("/auth/google/session")')
    block = src[i:i + 3000]
    assert re.search(r'user\.get\("suspended"\)\s*:\s*\n\s*raise HTTPException\(status_code=403, detail=SUSPENDED_MSG\)', block)
