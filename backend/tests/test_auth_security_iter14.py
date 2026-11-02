# Retest of iteration_13 security fixes: client_ip rate limiting, forgot-password timing/per-IP throttle,
# session invalidation after reset, regression login/me/refresh.
import asyncio
import hashlib
import os
import re
import secrets
import statistics
import time
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
RESET_USER = "delivered+sihha-reset@resend.dev"
RESET_PW = "NewPass1"


def run(coro):
    return asyncio.run(coro)


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


async def _del_attempts(prefix_regex):
    return (await _db().login_attempts.delete_many({"identifier": {"$regex": prefix_regex}})).deleted_count


async def _attempts(prefix_regex):
    return await _db().login_attempts.find({"identifier": {"$regex": prefix_regex}}, {"_id": 0}).to_list(100)


async def _insert_token(email, minutes=60):
    db = _db()
    user = await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1})
    raw = secrets.token_urlsafe(32)
    await db.password_reset_tokens.insert_one({
        "token_hash": hashlib.sha256(raw.encode()).hexdigest(), "user_id": user["user_id"], "email": email,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=minutes), "used_at": None,
        "created_at": datetime.now(timezone.utc).isoformat()})
    return raw


async def _del_tokens(email):
    await _db().password_reset_tokens.delete_many({"email": email})


async def _count_tokens(email):
    return await _db().password_reset_tokens.count_documents({"email": email})


async def _cleanup_user(email):
    db = _db()
    await db.password_reset_tokens.delete_many({"email": email})
    await db.users.delete_many({"email": email})
    await db.login_attempts.delete_many({"identifier": {"$regex": re.escape(email)}})


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    return s, r


# Regression: normal login / me / refresh
class TestRegression:
    @pytest.mark.parametrize("email,pw,role", [("omar.patient@sihha.ai", "Patient@123", "patient"),
                                               ("dr.layla@sihha.ai", "Doctor@123", "doctor")])
    def test_login_me_refresh(self, email, pw, role):
        s, r = _login(email, pw)
        assert r.status_code == 200, r.text
        assert r.json()["email"] == email and r.json()["role"] == role
        assert "password_hash" not in r.text
        me = s.get(f"{API}/auth/me")
        assert me.status_code == 200 and me.json()["email"] == email
        rf = s.post(f"{API}/auth/refresh")
        assert rf.status_code == 200 and rf.json() == {"ok": True}
        assert s.get(f"{API}/auth/me").status_code == 200


# Google lockout keyed on real client IP
class TestGoogleLockout:
    def test_lock_after_10_then_cleanup(self):
        run(_del_attempts("^google:"))
        try:
            codes = [requests.post(f"{API}/auth/google/session",
                                   json={"session_id": f"fake_sess_{i:04d}"}).status_code for i in range(11)]
            rows = run(_attempts("^google:"))
            print("codes", codes, "rows", rows)
            assert codes[:10] == [401] * 10, codes
            assert codes[10] == 429, codes
            assert len(rows) == 1, rows
            assert not rows[0]["identifier"].startswith("google:10."), rows
        finally:
            run(_del_attempts("^google:"))

    def test_spoofed_header_bypass(self):
        """Security probe: can a client rotate X-Real-IP / CF-Connecting-IP to avoid lockout?"""
        run(_del_attempts("^google:"))
        try:
            results = {}
            for hdr in ("X-Real-IP", "CF-Connecting-IP", "X-Forwarded-For"):
                r = requests.post(f"{API}/auth/google/session", json={"session_id": "fake_sess_spoof"},
                                  headers={hdr: f"203.0.113.{len(results) + 7}"})
                results[hdr] = r.status_code
            rows = [x["identifier"] for x in run(_attempts("^google:"))]
            print("spoof results", results, "identifiers", rows)
            spoofed = [i for i in rows if "203.0.113." in i]
            assert not spoofed, f"client-controlled header used as rate-limit key: {spoofed}"
        finally:
            run(_del_attempts("^google:"))


# Forgot-password timing
class TestForgotTiming:
    def test_timing_similar(self):
        run(_del_attempts("^reset:"))
        unknown, known = [], []
        try:
            for i in range(3):
                t = time.time()
                r = requests.post(f"{API}/auth/forgot-password", json={"email": f"nobody_{uuid.uuid4().hex[:6]}@example.com"})
                unknown.append(time.time() - t)
                assert r.json()["message"] == GENERIC
                t = time.time()
                r = requests.post(f"{API}/auth/forgot-password", json={"email": "noura.patient@sihha.ai"})
                known.append(time.time() - t)
                assert r.status_code == 200 and r.json()["message"] == GENERIC
            print("unknown", unknown, "known", known)
            assert statistics.median(known) < statistics.median(unknown) + 1.0, (unknown, known)
        finally:
            run(_del_tokens("noura.patient@sihha.ai"))
            run(_del_attempts("^reset:"))


# Per-IP throttle on forgot-password
class TestForgotPerIp:
    def test_ip_throttle(self):
        run(_del_attempts("^reset:"))
        emails = [f"test_ipthr_{uuid.uuid4().hex[:6]}@example.com" for _ in range(3)]
        for e in emails:
            assert requests.post(f"{API}/auth/register",
                                 json={"name": "TEST thr", "email": e, "password": "OldPass1"}).status_code == 200
        try:
            # 9 filler requests to unknown emails; 10th to emails[0] -> should create token
            for i in range(9):
                assert requests.post(f"{API}/auth/forgot-password",
                                     json={"email": f"nobody_{i}_{uuid.uuid4().hex[:4]}@example.com"}).status_code == 200
            r = requests.post(f"{API}/auth/forgot-password", json={"email": emails[0]})
            assert r.status_code == 200 and r.json()["message"] == GENERIC
            assert run(_count_tokens(emails[0])) == 1
            # 11th, 12th requests: generic but no new tokens
            for e in emails[1:]:
                r = requests.post(f"{API}/auth/forgot-password", json={"email": e})
                assert r.status_code == 200 and r.json()["message"] == GENERIC
                assert run(_count_tokens(e)) == 0, f"token created for {e} after IP throttle"
            rows = run(_attempts("^reset:"))
            print("reset rows", rows)
            assert len(rows) == 1 and rows[0]["count"] >= 10
        finally:
            run(_del_attempts("^reset:"))
            for e in emails:
                run(_cleanup_user(e))


# Sessions invalidated after password reset
class TestSessionInvalidation:
    def test_old_cookies_rejected_after_reset(self):
        run(_del_attempts("^reset:"))
        s_old, r = _login(RESET_USER, RESET_PW)
        assert r.status_code == 200, r.text
        assert s_old.get(f"{API}/auth/me").status_code == 200
        time.sleep(1.2)  # iat is second-granular
        raw = run(_insert_token(RESET_USER))
        try:
            r = requests.post(f"{API}/auth/reset-password", json={"token": raw, "password": "TempPass9"})
            assert r.status_code == 200 and r.json() == {"ok": True}
            assert s_old.get(f"{API}/auth/me").status_code == 401
            assert s_old.post(f"{API}/auth/refresh").status_code == 401
            s_new, r = _login(RESET_USER, "TempPass9")
            assert r.status_code == 200
            assert s_new.get(f"{API}/auth/me").status_code == 200
            assert s_new.post(f"{API}/auth/refresh").status_code == 200
            assert s_new.get(f"{API}/auth/me").status_code == 200
        finally:
            time.sleep(1.2)
            raw2 = run(_insert_token(RESET_USER))
            r = requests.post(f"{API}/auth/reset-password", json={"token": raw2, "password": RESET_PW})
            assert r.status_code == 200
            _, r = _login(RESET_USER, RESET_PW)
            assert r.status_code == 200, "failed to restore reset user password"
            run(_del_tokens(RESET_USER))
