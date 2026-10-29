# Regression tests: forgot/reset password, Google session hardening, health/503, secrets exposure, live transcription
import asyncio
import hashlib
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
GENERIC = "If an account exists for that email, a reset link is on its way."


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


async def _insert_token(email, minutes=60):
    db = _db()
    user = await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1})
    raw = secrets.token_urlsafe(32)
    await db.password_reset_tokens.insert_one({
        "token_hash": hashlib.sha256(raw.encode()).hexdigest(), "user_id": user["user_id"], "email": email,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=minutes), "used_at": None,
        "created_at": datetime.now(timezone.utc).isoformat()})
    return raw


async def _tokens_for(email):
    return await _db().password_reset_tokens.find({"email": email}, {"_id": 0}).to_list(50)


async def _clear_google():
    await _db().login_attempts.delete_many({"identifier": {"$regex": "^google:"}})


async def _cleanup(email):
    db = _db()
    await db.password_reset_tokens.delete_many({"email": email})
    await db.users.delete_many({"email": email})
    await db.login_attempts.delete_many({"identifier": {"$regex": re.escape(email)}})


@pytest.fixture(scope="module")
def test_user():
    email = f"test_reset_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"name": "TEST Reset", "email": email, "password": "OldPass1"})
    assert r.status_code == 200, r.text
    assert "password_hash" not in r.json()
    yield email
    run(_cleanup(email))


# Health
class TestHealth:
    def test_health(self):
        r = requests.get(f"{API}/health")
        assert r.status_code == 200 and r.json() == {"ok": True}


# Forgot password
class TestForgot:
    def test_generic_for_nonexistent(self):
        r = requests.post(f"{API}/auth/forgot-password", json={"email": f"nobody_{uuid.uuid4().hex[:6]}@example.com"})
        assert r.status_code == 200 and r.json()["message"] == GENERIC

    def test_generic_existing_and_rate_limit_and_supersede(self, test_user):
        for i in range(4):
            r = requests.post(f"{API}/auth/forgot-password", json={"email": test_user.upper()})
            assert r.status_code == 200 and r.json()["message"] == GENERIC, (i, r.text)
        toks = run(_tokens_for(test_user))
        assert len(toks) == 3, f"expected 3 tokens, got {len(toks)}"
        unused = [t for t in toks if t.get("used_at") is None]
        assert len(unused) == 1
        assert all("token" not in t and len(t["token_hash"]) == 64 for t in toks)
        assert sum(1 for t in toks if t.get("superseded")) == 2

    def test_undeliverable_seeded_still_generic(self):
        r = requests.post(f"{API}/auth/forgot-password", json={"email": "sami.patient@sihha.ai"})
        assert r.status_code == 200 and r.json()["message"] == GENERIC


# Reset password
class TestReset:
    def test_invalid_token(self):
        r = requests.post(f"{API}/auth/reset-password", json={"token": "x" * 40, "password": "Whatever1"})
        assert r.status_code == 400 and "invalid or has expired" in r.json()["detail"]

    def test_short_password_422(self, test_user):
        raw = run(_insert_token(test_user))
        r = requests.post(f"{API}/auth/reset-password", json={"token": raw, "password": "abc"})
        assert r.status_code == 422

    def test_expired_token(self, test_user):
        raw = run(_insert_token(test_user, minutes=-5))
        r = requests.post(f"{API}/auth/reset-password", json={"token": raw, "password": "Whatever1"})
        assert r.status_code == 400

    def test_full_reset_flow(self, test_user):
        raw = run(_insert_token(test_user))
        r = requests.post(f"{API}/auth/reset-password", json={"token": raw, "password": "NewPass9"})
        assert r.status_code == 200 and r.json() == {"ok": True}
        r = requests.post(f"{API}/auth/reset-password", json={"token": raw, "password": "Another9"})
        assert r.status_code == 400
        assert requests.post(f"{API}/auth/login", json={"email": test_user, "password": "OldPass1"}).status_code == 401
        r = requests.post(f"{API}/auth/login", json={"email": test_user, "password": "NewPass9"})
        assert r.status_code == 200 and r.json()["email"] == test_user
        assert "password_hash" not in r.text
        sc = r.headers.get("set-cookie", "").lower()
        assert "httponly" in sc and "secure" in sc


# Google session (429 lock test is last; it cleans up its rows)
class TestGoogle:
    def test_short_session_422(self):
        assert requests.post(f"{API}/auth/google/session", json={"session_id": "abc"}).status_code == 422

    def test_fake_session_401(self):
        r = requests.post(f"{API}/auth/google/session", json={"session_id": "fake_session_123456"})
        assert r.status_code == 401
        run(_clear_google())


# Secrets exposure
class TestSecrets:
    def test_bundle_has_no_secrets(self):
        html = requests.get(BASE_URL + "/").text
        scripts = re.findall(r'src="([^"]+\.js)"', html)
        assert scripts, "no scripts found"
        needles = ["sk-emergent", "ek_", os.environ["JWT_SECRET"].strip('"')[:16], "mongodb+srv",
                   os.environ["EMERGENT_EMAIL_KEY"].strip('"')[:12]]
        for s in scripts:
            body = requests.get(s if s.startswith("http") else BASE_URL + s).text
            for n in needles:
                if n == "ek_":
                    assert not re.search(r"ek_[0-9a-f]{16,}", body), f"ek_ key in {s}"
                else:
                    assert n not in body, f"{n[:6]}.. found in {s}"

    def test_me_no_password_hash(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": "omar.patient@sihha.ai", "password": "Patient@123"})
        r = s.get(f"{API}/auth/me")
        assert r.status_code == 200 and "password_hash" not in r.text and "_id" not in r.json()


# Live transcription (stub provider; restored after)
@pytest.fixture(scope="class")
def live_ctx():
    admin = requests.Session()
    assert admin.post(f"{API}/auth/login", json={"email": "admin@sihha.ai", "password": "Admin@123"}).status_code == 200
    before = admin.get(f"{API}/admin/transcription").json()["provider"]
    admin.put(f"{API}/admin/transcription", json={"provider": "stub"})
    d = requests.Session()
    assert d.post(f"{API}/auth/login", json={"email": "dr.layla@sihha.ai", "password": "Doctor@123"}).status_code == 200
    enc = d.get(f"{API}/encounters").json()[0]["encounter_id"]
    assert d.post(f"{API}/encounters/{enc}/consent", json={"granted": True}).status_code == 200
    yield d, enc
    admin.put(f"{API}/admin/transcription", json={"provider": before})
    assert admin.get(f"{API}/admin/transcription").json()["provider"] == before


class TestLive:
    def test_small_chunk_empty(self, live_ctx):
        d, enc = live_ctx
        r = d.post(f"{API}/encounters/{enc}/audio/live", data={"offset_seconds": 0},
                   files={"chunk": ("a.webm", b"x" * 100, "audio/webm")})
        assert r.status_code == 200 and r.json()["segments"] == []

    def test_stub_window(self, live_ctx):
        d, enc = live_ctx
        r = d.post(f"{API}/encounters/{enc}/audio/live", data={"offset_seconds": 0, "window_seconds": 10},
                   files={"chunk": ("a.webm", os.urandom(4096), "audio/webm")})
        assert r.status_code == 200, r.text
        segs = r.json()["segments"]
        assert isinstance(segs, list)
        assert all(0 <= s["start"] < 10 for s in segs)
        print("stub segments", len(segs), segs[:2])

    def test_patient_forbidden(self, live_ctx):
        _, enc = live_ctx
        p = requests.Session()
        p.post(f"{API}/auth/login", json={"email": "omar.patient@sihha.ai", "password": "Patient@123"})
        r = p.post(f"{API}/encounters/{enc}/audio/live", data={"offset_seconds": 0},
                   files={"chunk": ("a.webm", os.urandom(4096), "audio/webm")})
        assert r.status_code == 403


# Google lockout — runs last, clears the lock afterwards
class TestZGoogleLockout:
    def test_lock_after_10(self):
        run(_clear_google())
        try:
            codes = [requests.post(f"{API}/auth/google/session", json={"session_id": f"fake_sess_{i:04d}"}).status_code
                     for i in range(11)]
            assert codes[:10] == [401] * 10, codes
            assert codes[10] == 429, codes
        finally:
            run(_clear_google())
