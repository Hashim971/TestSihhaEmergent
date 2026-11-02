import os
import json
import uuid
import logging
import re
import random
import base64
import asyncio
import tempfile
import csv
import io
import socket
from urllib.parse import urlparse
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, NetworkTimeout, ConfigurationError
import httpx
from pydantic import BaseModel, Field
from cryptography.fernet import Fernet
from typing import Optional, List, Any

from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent, TextDelta, StreamDone
from gradio_client import Client as GradioClient, handle_file

from agents import tools as agent_tools, load_prompt
from agents.runner import run_agent, AgentRunFailed
from agents.previsit import PreVisitBriefingAgent
from agents.briefing_qa import BriefingQAAgent
from agents.intake import IntakeAgent
from agents.screening import ScreeningExtractionAgent
from agents.scribe import ScribeAgent
from agents.transcription import get_transcriber, default_provider
from agents.patient_summary import PatientSummaryAgent

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from emailer import send_email, password_reset_email, account_invite_email, usage_report_email, demo_alert_email, notice_email
from usage_report import render_usage_report

client = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000)
db = client[os.environ["DB_NAME"]]
LLM_KEY = os.environ["EMERGENT_LLM_KEY"]

app = FastAPI(title="Sihha AI")
api = APIRouter(prefix="/api")

SCREENING_SYSTEM_PROMPT, SCREENING_PROMPT_VERSION = load_prompt("screening_chat_v1.md")
SCREENING_REPORT_PROMPT, SCREENING_REPORT_VERSION = load_prompt("screening_report_v1.md")

PILL_ID_PROMPT = (
    "You are a pharmaceutical identification expert for the Sihha AI healthcare platform. "
    "Analyze the provided image of a pill/medication. Respond ONLY with strict JSON (no markdown fences) with keys: "
    '"identified" (boolean), "name" (string), "generic_name" (string), "description" (string), '
    '"uses" (string), "dosage_info" (string), "side_effects" (array of strings), '
    '"warnings" (array of strings), "confidence" ("low"|"medium"|"high"), "reason" (string, why identification failed if not identified). '
    "If the image does not contain a medication, set identified to false and explain in reason. "
    "Always include a note in warnings that this is AI identification and a pharmacist should verify."
)


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt=None):
    return (dt or now_utc()).isoformat()


# ---------- Auth (JWT email/password) ----------
JWT_ALGORITHM = "HS256"
JWT_SECRET = os.environ["JWT_SECRET"]
USER_PROJECTION = {"_id": 0, "password_hash": 0}
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()


def with_capabilities(user):
    """Marks the configured admin account. Admins manage doctor-patient assignments."""
    if user is not None:
        user["is_admin"] = bool(ADMIN_EMAIL) and (user.get("email") or "").lower() == ADMIN_EMAIL
    return user


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "email": email, "type": "access", "iat": now,
               "exp": now + timedelta(minutes=15)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "type": "refresh", "iat": now,
               "exp": now + timedelta(days=7)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


TRUSTED_PROXY_HOPS = 2


def client_ip(request: Request) -> str:
    """The edge appends [client, cloudflare, load balancer]; entries left of the client are spoofable."""
    hops = [h.strip() for h in (request.headers.get("x-forwarded-for") or "").split(",") if h.strip()]
    if len(hops) > TRUSTED_PROXY_HOPS:
        return hops[-(TRUSTED_PROXY_HOPS + 1)]
    return request.client.host


def token_predates_password_change(payload: dict, user: dict) -> bool:
    changed = user.get("password_changed_at")
    if not changed:
        return False
    return payload.get("iat", 0) < int(datetime.fromisoformat(changed).timestamp())


def set_auth_cookies(response: Response, access: str, refresh: str):
    response.set_cookie("access_token", access, httponly=True, secure=True,
                        samesite="lax", max_age=900, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True,
                        samesite="lax", max_age=604800, path="/")


async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = await db.users.find_one({"user_id": payload["sub"]}, USER_PROJECTION)
    if not user or token_predates_password_change(payload, user):
        raise HTTPException(status_code=401, detail="User not found")
    return with_capabilities(user)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1)
    email: str
    password: str = Field(min_length=6)
    requested_role: Optional[str] = None
    tenant_account_id: Optional[str] = Field(default=None, max_length=20)


class LoginRequest(BaseModel):
    email: str
    password: str


@api.post("/auth/register")
async def register(body: RegisterRequest, response: Response):
    email = body.email.strip().lower()
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Invalid email address")
    existing = await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    tenant = await _active_tenant(body.tenant_account_id) if body.tenant_account_id else None
    await db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "name": body.name.strip(),
        "password_hash": hash_password(body.password),
        "picture": None,
        "role": "patient",
        "clinician_requested": body.requested_role == "doctor",
        "sharing_enabled": True,
        "assigned_doctor_user_id": None,
        "onboarding_completed": False,
        "account_id": tenant["account_id"] if tenant else None,
        "created_at": iso(),
    })
    set_auth_cookies(response, create_access_token(user_id, email), create_refresh_token(user_id))
    return with_capabilities(await db.users.find_one({"user_id": user_id}, USER_PROJECTION))


@api.post("/auth/login")
async def login(body: LoginRequest, request: Request, response: Response):
    email = body.email.strip().lower()
    identifier = f"{client_ip(request)}:{email}"
    account_key = f"acct:{email}"
    attempt = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0})
    account = await db.login_attempts.find_one({"identifier": account_key}, {"_id": 0})
    for row in (attempt, account):
        if row and row.get("locked_until") and datetime.fromisoformat(row["locked_until"]) > now_utc():
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash") or not verify_password(body.password, user["password_hash"]):
        for key, row, limit in ((identifier, attempt, 5), (account_key, account, 10)):
            count = (row.get("count", 0) + 1) if row else 1
            update = {"identifier": key, "count": count, "updated_at": iso()}
            if count >= limit:
                update["locked_until"] = iso(now_utc() + timedelta(minutes=15))
                update["count"] = 0
            await db.login_attempts.update_one({"identifier": key}, {"$set": update}, upsert=True)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    await db.login_attempts.delete_many({"identifier": {"$in": [identifier, account_key]}})
    set_auth_cookies(response, create_access_token(user["user_id"], email), create_refresh_token(user["user_id"]))
    return with_capabilities(await db.users.find_one({"user_id": user["user_id"]}, USER_PROJECTION))


EMERGENT_AUTH_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
GOOGLE_SESSION_DAYS = 7


class GoogleSessionIn(BaseModel):
    session_id: str = Field(min_length=8, max_length=512)


@api.post("/auth/google/session")
async def google_session(body: GoogleSessionIn, request: Request, response: Response):
    """Exchanges an Emergent-managed Google session for this app's own signed-in session (patients only)."""
    identifier = f"google:{client_ip(request)}"
    attempt = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0})
    if attempt and attempt.get("locked_until") and datetime.fromisoformat(attempt["locked_until"]) > now_utc():
        raise HTTPException(status_code=429, detail="Too many sign-in attempts. Try again in 15 minutes.")
    try:
        async with httpx.AsyncClient(timeout=20) as http:
            resp = await http.get(EMERGENT_AUTH_SESSION_URL, headers={"X-Session-ID": body.session_id})
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Could not reach the sign-in service. Try again.")
    if resp.status_code != 200:
        count = (attempt.get("count", 0) + 1) if attempt else 1
        update = {"identifier": identifier, "count": count, "updated_at": iso()}
        if count >= 10:
            update.update(locked_until=iso(now_utc() + timedelta(minutes=15)), count=0)
        await db.login_attempts.update_one({"identifier": identifier}, {"$set": update}, upsert=True)
        raise HTTPException(status_code=401, detail="That Google sign-in link has expired. Try again.")
    profile = resp.json()
    email = (profile.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Google did not return an email address")

    user = await db.users.find_one({"email": email})
    if user:
        if user.get("role") not in (None, "patient"):
            raise HTTPException(status_code=403,
                                detail="Clinician accounts sign in through the clinician portal")
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"google_id": profile.get("id"), "auth_providers.google": True,
                      "picture": user.get("picture") or profile.get("picture"),
                      "name": user.get("name") or profile.get("name") or email.split("@")[0],
                      "last_login_at": iso()}},
        )
        user_id = user["user_id"]
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": profile.get("name") or email.split("@")[0],
            "password_hash": None,
            "google_id": profile.get("id"),
            "auth_providers": {"google": True},
            "picture": profile.get("picture"),
            "role": "patient",
            "clinician_requested": False,
            "sharing_enabled": True,
            "assigned_doctor_user_id": None,
            "onboarding_completed": False,
            "created_at": iso(),
            "last_login_at": iso(),
        })

    await db.login_attempts.delete_one({"identifier": identifier})
    await db.user_sessions.insert_one({
        "session_id": f"sess_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "provider": "google",
        "expires_at": iso(now_utc() + timedelta(days=GOOGLE_SESSION_DAYS)),
        "created_at": iso(),
    })
    set_auth_cookies(response, create_access_token(user_id, email), create_refresh_token(user_id))
    return with_capabilities(await db.users.find_one({"user_id": user_id}, USER_PROJECTION))


@api.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = await db.users.find_one({"user_id": payload["sub"]}, USER_PROJECTION)
    if not user or token_predates_password_change(payload, user):
        raise HTTPException(status_code=401, detail="User not found")
    response.set_cookie("access_token", create_access_token(user["user_id"], user["email"]),
                        httponly=True, secure=True, samesite="lax", max_age=900, path="/")
    return {"ok": True}


@api.get("/auth/me")
async def auth_me(user=Depends(get_current_user)):
    return user


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


RESET_TOKEN_MINUTES = 60
RESET_REQUESTS_PER_WINDOW = 3
RESET_REQUESTS_PER_IP = 10
_background_tasks = set()
GENERIC_RESET_REPLY = {"ok": True, "message": "If an account exists for that email, a reset link is on its way."}


class ForgotPasswordIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=6, max_length=128)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _app_origin(request: Request) -> str:
    origin = (request.headers.get("origin") or "").rstrip("/")
    if origin in CORS_ORIGINS:
        return origin
    return next(o for o in CORS_ORIGINS if o.startswith("https://"))


async def _deliver_reset_email(user_id: str, email: str, subject: str, html: str, kind: str = "email") -> bool:
    try:
        await send_email(to=email, subject=subject, html=html)
        return True
    except Exception:
        logging.getLogger(__name__).warning("%s not delivered to %s (%s)", kind.capitalize(), email, user_id)
        return False


@api.post("/auth/forgot-password")
async def forgot_password(body: ForgotPasswordIn, request: Request):
    email = body.email.strip().lower()
    ip_key = f"reset:{client_ip(request)}"
    window_start = iso(now_utc() - timedelta(minutes=15))
    ip_row = await db.login_attempts.find_one({"identifier": ip_key}, {"_id": 0})
    if ip_row and ip_row.get("window_start", "") >= window_start and ip_row.get("count", 0) >= RESET_REQUESTS_PER_IP:
        return GENERIC_RESET_REPLY
    if ip_row and ip_row.get("window_start", "") >= window_start:
        await db.login_attempts.update_one({"identifier": ip_key}, {"$inc": {"count": 1}})
    else:
        await db.login_attempts.update_one({"identifier": ip_key},
                                           {"$set": {"window_start": iso(), "count": 1}}, upsert=True)
    recent = await db.password_reset_tokens.count_documents({"email": email, "created_at": {"$gte": window_start}})
    if recent >= RESET_REQUESTS_PER_WINDOW:
        return GENERIC_RESET_REPLY
    user = await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1, "name": 1})
    if not user:
        return GENERIC_RESET_REPLY
    token = await _issue_password_token(user["user_id"], email, RESET_TOKEN_MINUTES)
    subject, html = password_reset_email(user.get("name") or "there",
                                         f"{_app_origin(request)}/auth/reset?token={token}")
    _send_in_background(user["user_id"], email, subject, html)
    return GENERIC_RESET_REPLY


async def _issue_password_token(user_id: str, email: str, minutes: int) -> str:
    token = secrets.token_urlsafe(32)
    await db.password_reset_tokens.update_many({"user_id": user_id, "used_at": None},
                                               {"$set": {"used_at": iso(), "superseded": True}})
    await db.password_reset_tokens.insert_one({
        "token_hash": _hash_token(token),
        "user_id": user_id,
        "email": email,
        "expires_at": now_utc() + timedelta(minutes=minutes),
        "used_at": None,
        "created_at": iso(),
    })
    return token


def _send_in_background(user_id: str, email: str, subject: str, html: str):
    task = asyncio.create_task(_deliver_reset_email(user_id, email, subject, html))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@api.post("/auth/reset-password")
async def reset_password(body: ResetPasswordIn):
    row = await db.password_reset_tokens.find_one({"token_hash": _hash_token(body.token)}, {"_id": 0})
    expires = row and row["expires_at"].replace(tzinfo=row["expires_at"].tzinfo or timezone.utc)
    if not row or row.get("used_at") or expires < now_utc():
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired. Request a new one.")
    claimed = await db.password_reset_tokens.update_one({"token_hash": row["token_hash"], "used_at": None},
                                                        {"$set": {"used_at": iso()}})
    if claimed.modified_count != 1:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired. Request a new one.")
    await db.users.update_one({"user_id": row["user_id"]},
                              {"$set": {"password_hash": hash_password(body.password),
                                        "auth_providers.password": True, "password_changed_at": iso()}})
    await db.login_attempts.delete_many({"identifier": {"$regex": f":{re.escape(row['email'])}$"}})
    return {"ok": True}


@api.get("/health")
async def health():
    await client.admin.command("ping")
    return {"ok": True}


DB_DOWN_ERRORS = (ConnectionFailure, ServerSelectionTimeoutError, NetworkTimeout, ConfigurationError)


@app.exception_handler(ConnectionFailure)
@app.exception_handler(ServerSelectionTimeoutError)
@app.exception_handler(NetworkTimeout)
@app.exception_handler(ConfigurationError)
async def database_unavailable(request: Request, exc: Exception):
    logging.getLogger(__name__).error("Database unreachable: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable",
                                                  "code": "service_unavailable"})


@app.on_event("startup")
async def startup_seed():
    try:
        await seed_and_index()
    except DB_DOWN_ERRORS:
        logging.getLogger(__name__).exception("Database unreachable at startup; serving 503s until it returns")


async def seed_and_index():
    await db.users.create_index("email", unique=True)
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.password_reset_tokens.create_index("token_hash", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.encounters.create_index([("doctor_user_id", 1), ("scheduled_at", -1)])
    await db.encounters.create_index([("patient_user_id", 1), ("scheduled_at", -1)])
    await db.agent_runs.create_index([("patient_user_id", 1), ("created_at", -1)])
    await db.clinical_artifacts.create_index("encounter_id")
    await db.briefing_threads.create_index("artifact_id", unique=True)
    await db.intake_forms.create_index("encounter_id", unique=True)
    await db.intake_forms.create_index([("patient_user_id", 1), ("status", 1)])
    await db.consultation_audio.create_index("encounter_id")
    await db.accounts.create_index("account_id", unique=True)
    await db.accounts.create_index("custom_domain", unique=True,
                                   partialFilterExpression={"custom_domain": {"$type": "string"}})
    await db.users.create_index("account_id")
    await db.health_reports.create_index([("user_id", 1), ("generated_at", -1)])
    await db.imported_records.create_index([("account_id", 1), ("user_id", 1)])
    await db.feature_flags.create_index("key", unique=True)
    if IS_STAGING:
        await seed_demo_accounts()
    await db.consultation_audio.create_index([("deleted_at", 1), ("retention_expires_at", 1)])
    await db.catalog_items.create_index([("pharmacy_id", 1), ("active", 1)])
    await db.catalog_items.create_index([("name_en", "text"), ("name_ar", "text"), ("generic_name", "text")])
    await db.orders.create_index([("profile_id", 1), ("created_at", -1)])
    await db.carts.create_index("profile_id", unique=True)
    await db.prescriptions.create_index([("profile_id", 1), ("verification_status", 1)])
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@sihha.ai").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin@123")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one({
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "email": admin_email,
            "name": "Dr. Admin",
            "password_hash": hash_password(admin_password),
            "picture": None,
            "role": "doctor",
            "sharing_enabled": False,
            "onboarding_completed": True,
            "created_at": iso(),
        })
    elif not existing.get("password_hash") or not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})


ALLOW_SELF_ROLE_CHANGE = os.environ.get("ALLOW_SELF_ROLE_CHANGE", "false").lower() == "true"


class RoleUpdate(BaseModel):
    role: str


@api.post("/auth/role")
async def set_role(body: RoleUpdate, user=Depends(get_current_user)):
    if not ALLOW_SELF_ROLE_CHANGE:
        raise HTTPException(status_code=403, detail="Role changes are administered, not self-service.")
    if body.role not in ("patient", "doctor"):
        raise HTTPException(status_code=400, detail="Invalid role")
    if user.get("role") == "doctor" and body.role == "patient":
        assigned = await db.users.count_documents({"assigned_doctor_user_id": user["user_id"]})
        if assigned:
            raise HTTPException(
                status_code=409,
                detail=f"{assigned} patient(s) are assigned to you. Reassign them before leaving the doctor role.",
            )
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"role": body.role}})
    return await db.users.find_one({"user_id": user["user_id"]}, USER_PROJECTION)


class SharingUpdate(BaseModel):
    enabled: bool


@api.post("/auth/sharing")
async def set_sharing(body: SharingUpdate, user=Depends(get_current_user)):
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"sharing_enabled": body.enabled}})
    return await db.users.find_one({"user_id": user["user_id"]}, USER_PROJECTION)


# ---------- Health Profile (onboarding) ----------
class HealthProfileUpdate(BaseModel):
    skip: bool = False
    height: Optional[float] = None
    height_unit: str = "cm"
    weight: Optional[float] = None
    weight_unit: str = "kg"
    date_of_birth: Optional[str] = None
    calendar: str = "gregorian"
    chronic_conditions: Optional[bool] = None
    chronic_conditions_details: Optional[str] = None
    family_history: Optional[bool] = None
    family_history_details: Optional[str] = None
    allergies: Optional[bool] = None
    allergies_details: Optional[str] = None
    surgical_history: Optional[bool] = None
    surgical_history_details: Optional[str] = None
    current_medications: Optional[bool] = None
    current_medications_details: Optional[str] = None
    recent_medications: Optional[bool] = None
    recent_medications_details: Optional[str] = None
    smoker: Optional[bool] = None
    dietary_habits: Optional[bool] = None
    dietary_habits_details: Optional[str] = None
    physical_activity: Optional[bool] = None
    physical_activity_details: Optional[str] = None
    sleep_pattern: Optional[bool] = None
    sleep_pattern_details: Optional[str] = None
    stress_level: Optional[bool] = None
    stress_level_details: Optional[str] = None


@api.put("/profile/health")
async def update_health_profile(body: HealthProfileUpdate, user=Depends(get_current_user)):
    update = {"onboarding_completed": True}
    if not body.skip:
        profile = body.model_dump(exclude={"skip"})
        profile["updated_at"] = iso()
        update["health_profile"] = profile
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": update})
    return await db.users.find_one({"user_id": user["user_id"]}, USER_PROJECTION)


def health_profile_context(user) -> str:
    hp = user.get("health_profile")
    if not hp:
        return ""
    lines = []
    if hp.get("height"):
        lines.append(f"Height: {hp['height']} {hp.get('height_unit', 'cm')}")
    if hp.get("weight"):
        lines.append(f"Weight: {hp['weight']} {hp.get('weight_unit', 'kg')}")
    if hp.get("date_of_birth"):
        lines.append(f"Date of birth: {hp['date_of_birth']} ({hp.get('calendar', 'gregorian')} calendar)")
    yn = [
        ("chronic_conditions", "Chronic/past health conditions"),
        ("family_history", "Family health history of note"),
        ("allergies", "Allergies (foods, medications, other)"),
        ("surgical_history", "Surgical history"),
        ("current_medications", "Currently taking daily medications"),
        ("recent_medications", "Medications taken in the last 6 months"),
        ("smoker", "Smoker"),
        ("dietary_habits", "Follows specific dietary habits"),
        ("physical_activity", "Regular weekly physical activity"),
        ("sleep_pattern", "Consistent daily sleep pattern"),
        ("stress_level", "Experiences notable stress"),
    ]
    for key, label in yn:
        val = hp.get(key)
        if val is None:
            continue
        detail = hp.get(f"{key}_details")
        lines.append(f"{label}: {'Yes' if val else 'No'}" + (f" — {detail}" if val and detail else ""))
    if not lines:
        return ""
    return (
        "\n\nPatient health profile (collected during onboarding — use it to personalize questions, "
        "risk assessment and advice; account for allergies and current medications before suggesting anything):\n- "
        + "\n- ".join(lines)
    )


# ---------- Dependents ----------
async def screening_subject_context(user, profile_id: str) -> str:
    """Who the screening is about: the user's own health profile, or the dependent a caregiver is speaking for."""
    if profile_id == user["user_id"]:
        return health_profile_context(user)
    dep = await db.dependents.find_one({"dependent_id": profile_id, "user_id": user["user_id"]}, {"_id": 0})
    if not dep:
        return ""
    details = [f"name {dep.get('name')}", f"relation to the person typing: {dep.get('relation')}"]
    if dep.get("date_of_birth"):
        details.append(f"date of birth {dep['date_of_birth']}")
    if dep.get("gender"):
        details.append(f"sex {dep['gender']}")
    return ("\n\nThis screening is for a dependent. The person typing is their caregiver (" + user.get("name", "caregiver")
            + "). Dependent: " + "; ".join(details) + ". No health profile is on file for the dependent.")


class DependentCreate(BaseModel):
    name: str
    relation: str
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None


@api.post("/dependents")
async def add_dependent(body: DependentCreate, user=Depends(get_current_user)):
    dep = {
        "dependent_id": f"dep_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "name": body.name,
        "relation": body.relation,
        "date_of_birth": body.date_of_birth,
        "gender": body.gender,
        "created_at": iso(),
    }
    await db.dependents.insert_one(dep)
    dep.pop("_id", None)
    return dep


@api.get("/dependents")
async def list_dependents(user=Depends(get_current_user)):
    return await db.dependents.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(100)


@api.delete("/dependents/{dependent_id}")
async def delete_dependent(dependent_id: str, user=Depends(get_current_user)):
    await db.dependents.delete_one({"dependent_id": dependent_id, "user_id": user["user_id"]})
    return {"ok": True}


def profile_key(user, profile_id: Optional[str]):
    return profile_id if profile_id and profile_id != "self" else user["user_id"]


# ---------- Vitals ----------
VITAL_RANGES = {
    "heart_rate": (55, 105, "bpm", "Heart rate"),
    "systolic": (90, 135, "mmHg", "Systolic BP"),
    "diastolic": (60, 90, "mmHg", "Diastolic BP"),
    "glucose": (70, 140, "mg/dL", "Blood glucose"),
    "spo2": (94, 100, "%", "Oxygen saturation"),
    "temperature": (36.1, 37.5, "°C", "Body temperature"),
}


class VitalCreate(BaseModel):
    profile_id: Optional[str] = None
    heart_rate: Optional[float] = None
    systolic: Optional[float] = None
    diastolic: Optional[float] = None
    glucose: Optional[float] = None
    spo2: Optional[float] = None
    temperature: Optional[float] = None
    weight: Optional[float] = None
    source: str = "manual"
    recorded_at: Optional[str] = None


async def check_vital_alerts(user_id, profile, vital):
    for field, (lo, hi, unit, label) in VITAL_RANGES.items():
        val = vital.get(field)
        if val is None:
            continue
        if val < lo or val > hi:
            direction = "low" if val < lo else "high"
            await db.alerts.insert_one({
                "alert_id": f"alert_{uuid.uuid4().hex[:12]}",
                "user_id": user_id,
                "profile_id": profile,
                "type": "vital",
                "severity": "critical" if (val < lo * 0.85 or val > hi * 1.15) else "warning",
                "message": f"{label} is {direction}: {val} {unit} (normal {lo}-{hi} {unit})",
                "read": False,
                "created_at": iso(),
            })


@api.post("/vitals")
async def add_vital(body: VitalCreate, user=Depends(get_current_user)):
    profile = profile_key(user, body.profile_id)
    vital = body.model_dump()
    vital.pop("profile_id", None)
    vital.update({
        "vital_id": f"vital_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "profile_id": profile,
        "recorded_at": body.recorded_at or iso(),
        "created_at": iso(),
    })
    await db.vitals.insert_one(vital)
    await check_vital_alerts(user["user_id"], profile, vital)
    vital.pop("_id", None)
    return vital


@api.get("/vitals")
async def list_vitals(profile_id: Optional[str] = None, days: int = 7, user=Depends(get_current_user)):
    profile = profile_key(user, profile_id)
    since = iso(now_utc() - timedelta(days=days))
    return await db.vitals.find(
        {"profile_id": profile, "recorded_at": {"$gte": since}}, {"_id": 0}
    ).sort("recorded_at", 1).to_list(1000)


@api.get("/vitals/latest")
async def latest_vital(profile_id: Optional[str] = None, user=Depends(get_current_user)):
    profile = profile_key(user, profile_id)
    docs = await db.vitals.find({"profile_id": profile}, {"_id": 0}).sort("recorded_at", -1).to_list(20)
    latest = {}
    for field in list(VITAL_RANGES.keys()) + ["weight"]:
        for d in docs:
            if d.get(field) is not None:
                latest[field] = {"value": d[field], "recorded_at": d["recorded_at"]}
                break
    return latest


@api.post("/vitals/simulate")
async def simulate_vitals(body: dict = None, user=Depends(get_current_user)):
    body = body or {}
    profile = profile_key(user, body.get("profile_id"))
    docs = []
    for day in range(7):
        for hour in (8, 13, 19):
            ts = now_utc() - timedelta(days=6 - day)
            ts = ts.replace(hour=hour, minute=random.randint(0, 59))
            if ts > now_utc():
                continue
            docs.append({
                "vital_id": f"vital_{uuid.uuid4().hex[:12]}",
                "user_id": user["user_id"],
                "profile_id": profile,
                "heart_rate": round(random.gauss(74, 8), 0),
                "systolic": round(random.gauss(118, 8), 0),
                "diastolic": round(random.gauss(76, 6), 0),
                "glucose": round(random.gauss(100, 14), 0),
                "spo2": round(min(100, random.gauss(97.5, 1.2)), 1),
                "temperature": round(random.gauss(36.7, 0.3), 1),
                "weight": None,
                "source": "wearable_sim",
                "recorded_at": iso(ts),
                "created_at": iso(),
            })
    if docs:
        await db.vitals.insert_many(docs)
        last = dict(docs[-1])
        await check_vital_alerts(user["user_id"], profile, last)
    return {"inserted": len(docs)}


# ---------- Alerts ----------
@api.get("/alerts")
async def list_alerts(user=Depends(get_current_user)):
    return await db.alerts.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)


@api.post("/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: str, user=Depends(get_current_user)):
    await db.alerts.update_one({"alert_id": alert_id, "user_id": user["user_id"]}, {"$set": {"read": True}})
    return {"ok": True}


class AlertGroupRead(BaseModel):
    type: str
    severity: Optional[str] = None


@api.post("/alerts/read-group")
async def mark_alert_group_read(body: AlertGroupRead, user=Depends(get_current_user)):
    """Clears a whole group of alerts at once, not just the few shown in the card."""
    query = {"user_id": user["user_id"], "type": body.type, "read": False}
    if body.severity:
        query["severity"] = body.severity
    result = await db.alerts.update_many(query, {"$set": {"read": True, "read_at": iso()}})
    return {"cleared": result.modified_count}


# ---------- Health Chat / Screening ----------
class ChatSessionCreate(BaseModel):
    profile_id: Optional[str] = None


@api.post("/chat/sessions")
async def create_chat_session(body: ChatSessionCreate, user=Depends(get_current_user)):
    profile = profile_key(user, body.profile_id)
    session = {
        "chat_session_id": f"chat_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "profile_id": profile,
        "status": "active",
        "title": "Health Screening",
        "started_at": iso(),
    }
    await db.chat_sessions.insert_one(session)
    greeting = ("Hello, I'm the Sihha screening assistant. I'll ask you one question at a time so your doctor gets a "
                "clear picture — I can't diagnose. If you have chest pain, trouble breathing or another emergency, "
                "call 997 now. What is bothering you today?")
    await db.chat_messages.insert_one({
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "chat_session_id": session["chat_session_id"],
        "role": "assistant",
        "content": greeting,
        "created_at": iso(),
    })
    session.pop("_id", None)
    return session


@api.get("/chat/sessions")
async def list_chat_sessions(user=Depends(get_current_user)):
    return await db.chat_sessions.find({"user_id": user["user_id"]}, {"_id": 0}).sort("started_at", -1).to_list(50)


@api.get("/chat/sessions/{sid}/messages")
async def list_chat_messages(sid: str, user=Depends(get_current_user)):
    session = await db.chat_sessions.find_one({"chat_session_id": sid, "user_id": user["user_id"]}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return await db.chat_messages.find({"chat_session_id": sid}, {"_id": 0}).sort("created_at", 1).to_list(500)


class ChatMessageIn(BaseModel):
    text: str


@api.post("/chat/sessions/{sid}/message")
async def send_chat_message(sid: str, body: ChatMessageIn, user=Depends(get_current_user)):
    session = await db.chat_sessions.find_one({"chat_session_id": sid, "user_id": user["user_id"]}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.chat_messages.insert_one({
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "chat_session_id": sid,
        "role": "user",
        "content": body.text,
        "created_at": iso(),
    })

    history = await db.chat_messages.find({"chat_session_id": sid}, {"_id": 0}).sort("created_at", 1).to_list(100)
    context = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history[:-1]][-30:])
    system = SCREENING_SYSTEM_PROMPT + await screening_subject_context(user, session["profile_id"])
    if context:
        system += "\n\nConversation so far:\n" + context

    chat = LlmChat(api_key=LLM_KEY, session_id=sid, system_message=system).with_model("openai", "gpt-5.5")

    async def event_generator():
        full = []
        try:
            async for ev in chat.stream_message(UserMessage(text=body.text)):
                if isinstance(ev, TextDelta):
                    full.append(ev.content)
                    yield f"data: {json.dumps({'delta': ev.content})}\n\n"
                elif isinstance(ev, StreamDone):
                    break
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        content = "".join(full)
        if content:
            await db.chat_messages.insert_one({
                "message_id": f"msg_{uuid.uuid4().hex[:12]}",
                "chat_session_id": sid,
                "role": "assistant",
                "content": content,
                "created_at": iso(),
            })
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        event_generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@api.post("/chat/sessions/{sid}/report")
async def generate_report(sid: str, user=Depends(get_current_user)):
    session = await db.chat_sessions.find_one({"chat_session_id": sid, "user_id": user["user_id"]}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    history = await db.chat_messages.find({"chat_session_id": sid}, {"_id": 0}).sort("created_at", 1).to_list(200)
    convo = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history])
    chat = LlmChat(
        api_key=LLM_KEY, session_id=f"report_{sid}", system_message=SCREENING_REPORT_PROMPT,
    ).with_model("openai", "gpt-5.5")
    context = await screening_subject_context(user, session["profile_id"])
    result = await chat.send_message(UserMessage(
        text=(context.strip() or "No health profile on file.") + "\n\nConversation:\n" + convo))
    report = {
        "report_id": f"report_{uuid.uuid4().hex[:12]}",
        "chat_session_id": sid,
        "user_id": user["user_id"],
        "profile_id": session["profile_id"],
        "content": result,
        "prompt_version": f"report-{SCREENING_REPORT_VERSION}/chat-{SCREENING_PROMPT_VERSION}",
        "generated_at": iso(),
    }
    await db.health_reports.insert_one(report)
    await db.chat_sessions.update_one(
        {"chat_session_id": sid}, {"$set": {"status": "completed", "ended_at": iso()}}
    )
    report.pop("_id", None)
    await extract_report_findings(report, invoked_by=user["user_id"])
    await run_report_triage(report["report_id"], invoked_by=user["user_id"])
    return await db.health_reports.find_one({"report_id": report["report_id"]}, {"_id": 0})


@api.get("/reports")
async def list_reports(user=Depends(get_current_user)):
    return await db.health_reports.find({"user_id": user["user_id"]}, {"_id": 0}).sort("generated_at", -1).to_list(50)


# ---------- Pill Identification (HF Space CNN + LLM details) ----------
HF_TOKEN = os.environ.get("HF_TOKEN")
HF_PILLS_SPACE = os.environ.get("HF_PILLS_SPACE", "Hashim971/Tessihha")
_pills_client = None

PILL_DETAILS_PROMPT = (
    "You are a pharmaceutical information expert for the Sihha AI healthcare platform. "
    "A CNN pill-classifier model has identified a medication from a photo. Given the predicted class name, "
    "respond ONLY with strict JSON (no markdown fences) with keys: "
    '"name" (string, proper medication name), "generic_name" (string), "description" (string), '
    '"uses" (string), "dosage_info" (string), "side_effects" (array of strings), '
    '"warnings" (array of strings). '
    "Always include a warning that this is AI identification and a pharmacist should verify before taking anything. "
    "If the class name is not a known medication, still describe what it most likely refers to."
)


def classify_pill_sync(image_path: str):
    global _pills_client
    if _pills_client is None:
        _pills_client = GradioClient(HF_PILLS_SPACE, token=HF_TOKEN, verbose=False)
    cam_path, label_raw = _pills_client.predict(image=handle_file(image_path), api_name="/classify_pill")
    return cam_path, label_raw


class PillIdentifyRequest(BaseModel):
    image_base64: str
    profile_id: Optional[str] = None


@api.post("/pills/identify")
async def identify_pill(body: PillIdentifyRequest, user=Depends(get_current_user)):
    parsed, cam_b64, label = None, None, None
    tmp_path = None
    try:
        raw = base64.b64decode(body.image_base64)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(raw)
            tmp_path = f.name
        cam_path, label_raw = await asyncio.wait_for(asyncio.to_thread(classify_pill_sync, tmp_path), timeout=120)
        label = label_raw.replace("Predicted Class:", "").strip()
        try:
            with open(cam_path, "rb") as cf:
                cam_b64 = base64.b64encode(cf.read()).decode()
        except Exception:
            cam_b64 = None
    except Exception:
        global _pills_client
        _pills_client = None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if label:
        chat = LlmChat(
            api_key=LLM_KEY, session_id=f"pill_{uuid.uuid4().hex[:8]}", system_message=PILL_DETAILS_PROMPT
        ).with_model("openai", "gpt-5.5")
        result = await chat.send_message(UserMessage(
            text=f"The pill classifier predicted the class: '{label}'. Return the JSON."
        ))
        parsed = parse_llm_json(result)
        if parsed is not None:
            parsed["identified"] = True
            parsed["name"] = parsed.get("name") or label
        else:
            parsed = {"identified": True, "name": label}
        parsed["classifier_label"] = label
        parsed["source"] = "cnn_classifier"
    else:
        # Fallback: GPT-5.5 vision if the HF Space is unreachable
        chat = LlmChat(
            api_key=LLM_KEY, session_id=f"pill_{uuid.uuid4().hex[:8]}", system_message=PILL_ID_PROMPT
        ).with_model("openai", "gpt-5.5")
        img = ImageContent(image_base64=body.image_base64)
        result = await chat.send_message(UserMessage(
            text="Identify this medication and return the JSON.", file_contents=[img]
        ))
        parsed = parse_llm_json(result) or {"identified": False, "reason": "Could not parse AI response", "raw": result}
        parsed["source"] = "vision_fallback"

    record = {
        "pill_id": f"pill_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "profile_id": profile_key(user, body.profile_id),
        "result": parsed,
        "created_at": iso(),
    }
    await db.pill_history.insert_one(record)
    record.pop("_id", None)
    record["cam_image_base64"] = cam_b64
    return record


def parse_llm_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text.strip())
    except Exception:
        return None


@api.get("/pills/history")
async def pill_history(user=Depends(get_current_user)):
    return await db.pill_history.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)


# ---------- Medications & Adherence ----------
class MedicationCreate(BaseModel):
    name: str
    dosage: str
    times: List[str]
    instructions: Optional[str] = None
    profile_id: Optional[str] = None
    quantity_dispensed: Optional[int] = None
    units_per_dose: float = 1
    dispensed_on: Optional[str] = None


@api.post("/medications")
async def add_medication(body: MedicationCreate, user=Depends(get_current_user)):
    med = {
        "medication_id": f"med_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "profile_id": profile_key(user, body.profile_id),
        "name": body.name,
        "dosage": body.dosage,
        "times": body.times,
        "instructions": body.instructions,
        "quantity_dispensed": body.quantity_dispensed,
        "units_per_dose": body.units_per_dose,
        "dispensed_on": body.dispensed_on,
        "active": True,
        "created_at": iso(),
    }
    await db.medications.insert_one(med)
    med.pop("_id", None)
    return med


@api.get("/medications")
async def list_medications(profile_id: Optional[str] = None, user=Depends(get_current_user)):
    profile = profile_key(user, profile_id)
    return await db.medications.find({"profile_id": profile, "active": True}, {"_id": 0}).to_list(100)


@api.delete("/medications/{medication_id}")
async def delete_medication(medication_id: str, user=Depends(get_current_user)):
    await db.medications.update_one(
        {"medication_id": medication_id, "user_id": user["user_id"]}, {"$set": {"active": False}}
    )
    return {"ok": True}


class DoseLog(BaseModel):
    time: str
    status: str
    date: Optional[str] = None


@api.post("/medications/{medication_id}/dose")
async def log_dose(medication_id: str, body: DoseLog, user=Depends(get_current_user)):
    med = await db.medications.find_one({"medication_id": medication_id, "user_id": user["user_id"]}, {"_id": 0})
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")
    date = body.date or now_utc().strftime("%Y-%m-%d")
    await db.dose_logs.update_one(
        {"medication_id": medication_id, "date": date, "time": body.time},
        {"$set": {
            "dose_log_id": f"dose_{uuid.uuid4().hex[:12]}",
            "medication_id": medication_id,
            "user_id": user["user_id"],
            "profile_id": med["profile_id"],
            "date": date,
            "time": body.time,
            "status": body.status,
            "logged_at": iso(),
        }},
        upsert=True,
    )
    if body.status == "missed":
        await db.alerts.insert_one({
            "alert_id": f"alert_{uuid.uuid4().hex[:12]}",
            "user_id": user["user_id"],
            "profile_id": med["profile_id"],
            "type": "medication",
            "severity": "warning",
            "message": f"Missed dose: {med['name']} ({med['dosage']}) scheduled at {body.time}",
            "read": False,
            "created_at": iso(),
        })
    return {"ok": True}


@api.get("/medications/schedule/today")
async def today_schedule(profile_id: Optional[str] = None, user=Depends(get_current_user)):
    profile = profile_key(user, profile_id)
    meds = await db.medications.find({"profile_id": profile, "active": True}, {"_id": 0}).to_list(100)
    date = now_utc().strftime("%Y-%m-%d")
    logs = await db.dose_logs.find({"profile_id": profile, "date": date}, {"_id": 0}).to_list(500)
    log_map = {(l["medication_id"], l["time"]): l["status"] for l in logs}
    schedule = []
    for med in meds:
        for t in med["times"]:
            schedule.append({
                "medication_id": med["medication_id"],
                "name": med["name"],
                "dosage": med["dosage"],
                "instructions": med.get("instructions"),
                "time": t,
                "status": log_map.get((med["medication_id"], t), "pending"),
            })
    schedule.sort(key=lambda x: x["time"])
    return schedule


@api.get("/medications/adherence/stats")
async def adherence_stats(profile_id: Optional[str] = None, user=Depends(get_current_user)):
    profile = profile_key(user, profile_id)
    logs = await db.dose_logs.find({"profile_id": profile}, {"_id": 0}).to_list(2000)
    taken = sum(1 for l in logs if l["status"] == "taken")
    missed = sum(1 for l in logs if l["status"] == "missed")
    total = taken + missed
    return {
        "taken": taken,
        "missed": missed,
        "total": total,
        "rate": round(taken / total * 100, 1) if total else None,
    }


# ---------- Doctor Portal ----------
async def require_doctor(user=Depends(get_current_user)):
    if user.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="Doctor access required")
    return user


async def require_admin(user=Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


class DoctorAssignment(BaseModel):
    doctor_user_id: Optional[str] = None


async def _resolve_doctor(doctor_user_id: Optional[str]):
    if not doctor_user_id:
        return None
    doctor = await db.users.find_one({"user_id": doctor_user_id, "role": "doctor"}, USER_PROJECTION)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor


@api.get("/doctors")
async def list_doctors(specialty: Optional[str] = None, city: Optional[str] = None,
                       user=Depends(get_current_user)):
    query = {"role": "doctor", "email": {"$ne": ADMIN_EMAIL}}
    if specialty:
        query["specialty"] = {"$regex": re.escape(specialty), "$options": "i"}
    if city:
        query["city"] = {"$regex": re.escape(city), "$options": "i"}
    doctors = await db.users.find(
        query,
        {"_id": 0, "user_id": 1, "name": 1, "email": 1, "specialty": 1, "clinic": 1, "city": 1, "bio": 1,
         "clinic_phone": 1},
    ).to_list(200)
    return doctors


class ClinicianProfile(BaseModel):
    specialty: str = ""
    clinic: str = ""
    city: str = ""
    bio: str = ""
    clinic_phone: str = ""


@api.put("/profile/clinician")
async def update_clinician_profile(body: ClinicianProfile, user=Depends(require_doctor)):
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": body.model_dump()})
    return with_capabilities(await db.users.find_one({"user_id": user["user_id"]}, USER_PROJECTION))


@api.put("/profile/doctor")
async def choose_my_doctor(body: DoctorAssignment, user=Depends(get_current_user)):
    """A patient picks the one doctor who may see their record. Choosing a new doctor transfers care."""
    await _resolve_doctor(body.doctor_user_id)
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"assigned_doctor_user_id": body.doctor_user_id, "assigned_at": iso(),
                  "assigned_by": "patient" if body.doctor_user_id else None}},
    )
    return with_capabilities(await db.users.find_one({"user_id": user["user_id"]}, USER_PROJECTION))


class RoleAssignment(BaseModel):
    role: str


@api.put("/admin/users/{user_id}/role")
async def admin_set_role(user_id: str, body: RoleAssignment, user=Depends(require_admin)):
    """The only way an account becomes a clinician."""
    if body.role not in ("patient", "doctor"):
        raise HTTPException(status_code=400, detail="Invalid role")
    target = await db.users.find_one({"user_id": user_id}, USER_PROJECTION)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if body.role == "patient":
        assigned = await db.users.count_documents({"assigned_doctor_user_id": user_id})
        if assigned:
            raise HTTPException(status_code=409, detail=f"{assigned} patient(s) are assigned to this doctor")
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"role": body.role, "clinician_requested": False,
                  "assigned_doctor_user_id": None if body.role == "doctor" else target.get("assigned_doctor_user_id")}},
    )
    return await db.users.find_one({"user_id": user_id}, USER_PROJECTION)


@api.get("/admin/patients")
async def admin_list_patients(user=Depends(require_admin)):
    patients = await db.users.find({"role": "patient"}, USER_PROJECTION).sort("created_at", -1).to_list(500)
    doctors = await db.users.find({"role": "doctor"}, {"_id": 0, "user_id": 1, "name": 1}).to_list(200)
    names = {d["user_id"]: d["name"] for d in doctors}
    return [{
        "user_id": p["user_id"], "name": p.get("name"), "email": p.get("email"),
        "sharing_enabled": p.get("sharing_enabled", False),
        "assigned_doctor_user_id": p.get("assigned_doctor_user_id"),
        "assigned_doctor_name": names.get(p.get("assigned_doctor_user_id")),
        "assigned_by": p.get("assigned_by"),
        "clinician_requested": bool(p.get("clinician_requested")),
        "created_at": p.get("created_at"),
    } for p in patients]


@api.put("/admin/patients/{patient_user_id}/doctor")
async def admin_assign_doctor(patient_user_id: str, body: DoctorAssignment, user=Depends(require_admin)):
    patient = await db.users.find_one({"user_id": patient_user_id, "role": "patient"}, USER_PROJECTION)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    await _resolve_doctor(body.doctor_user_id)
    await db.users.update_one(
        {"user_id": patient_user_id},
        {"$set": {"assigned_doctor_user_id": body.doctor_user_id, "assigned_at": iso(),
                  "assigned_by": "admin" if body.doctor_user_id else None}},
    )
    return await db.users.find_one({"user_id": patient_user_id}, USER_PROJECTION)


@api.get("/doctor/patients")
async def doctor_patients(user=Depends(require_doctor)):
    query = {"sharing_enabled": True, "role": "patient"}
    if not user.get("is_admin"):
        query["assigned_doctor_user_id"] = user["user_id"]
    patients = await db.users.find(query, USER_PROJECTION).to_list(200)
    out = []
    for p in patients:
        alerts = await db.alerts.count_documents({"user_id": p["user_id"], "read": False})
        out.append({**p, "unread_alerts": alerts})
    return out


@api.get("/doctor/patients/{patient_id}/summary")
async def doctor_patient_summary(patient_id: str, user=Depends(require_doctor)):
    patient = await assert_doctor_can_access_patient(db, user, patient_id)
    vitals = await db.vitals.find({"profile_id": patient_id}, {"_id": 0}).sort("recorded_at", -1).to_list(30)
    alerts = await db.alerts.find({"user_id": patient_id}, {"_id": 0}).sort("created_at", -1).to_list(20)
    reports = await db.health_reports.find({"user_id": patient_id}, {"_id": 0}).sort("generated_at", -1).to_list(10)
    logs = await db.dose_logs.find({"profile_id": patient_id}, {"_id": 0}).to_list(2000)
    taken = sum(1 for l in logs if l["status"] == "taken")
    missed = sum(1 for l in logs if l["status"] == "missed")
    total = taken + missed
    meds = await db.medications.find({"profile_id": patient_id, "active": True}, {"_id": 0}).to_list(100)
    return {
        "patient": patient,
        "vitals": vitals[::-1],
        "alerts": alerts,
        "reports": reports,
        "medications": meds,
        "adherence": {"taken": taken, "missed": missed, "total": total,
                      "rate": round(taken / total * 100, 1) if total else None},
    }


# ---------- Clinical Agents: Encounters, Pre-Visit Briefings, Artifacts ----------
PREVISIT_AGENT = PreVisitBriefingAgent()
BRIEFING_QA_AGENT = BriefingQAAgent()
INTAKE_AGENT = IntakeAgent()


async def assert_doctor_can_access_patient(db, doctor, patient_user_id: str):
    """Single gate for every doctor-facing clinical route: consent + assignment (admins see all).

    A patient who books a visit with a doctor other than their own grants that doctor time-boxed access
    to their record — that booking is the consent, and it expires with the grant.
    """
    patient = await db.users.find_one({"user_id": patient_user_id, "sharing_enabled": True}, USER_PROJECTION)
    if not patient:
        raise HTTPException(status_code=403, detail="Patient is not sharing data or is not assigned to you")
    if doctor.get("is_admin") or patient.get("assigned_doctor_user_id") == doctor["user_id"]:
        return patient
    grant = await db.care_grants.find_one(
        {"patient_user_id": patient_user_id, "doctor_user_id": doctor["user_id"],
         "revoked": False, "expires_at": {"$gt": iso()}}, {"_id": 0})
    if not grant:
        raise HTTPException(status_code=403, detail="Patient is not sharing data or is not assigned to you")
    return patient


def _agent_http_error(exc: AgentRunFailed):
    if exc.status == "timeout":
        return HTTPException(status_code=504, detail="The agent timed out. Try again.")
    return HTTPException(status_code=502, detail=f"Agent run failed: {exc.message}")


class EncounterCreate(BaseModel):
    patient_user_id: Optional[str] = None
    doctor_user_id: Optional[str] = None
    profile_id: Optional[str] = None
    scheduled_at: Optional[str] = None
    reason_for_visit: str = ""


class EncounterUpdate(BaseModel):
    status: Optional[str] = None
    scheduled_at: Optional[str] = None
    reason_for_visit: Optional[str] = None


@api.post("/encounters")
async def create_encounter(body: EncounterCreate, user=Depends(get_current_user)):
    if user.get("role") == "doctor":
        if not body.patient_user_id:
            raise HTTPException(status_code=400, detail="patient_user_id is required")
        patient = await assert_doctor_can_access_patient(db, user, body.patient_user_id)
        patient_user_id, doctor_user_id = body.patient_user_id, user["user_id"]
        profile_id = body.profile_id or patient["user_id"]
    else:
        if not body.doctor_user_id:
            raise HTTPException(status_code=400, detail="doctor_user_id is required")
        doctor = await db.users.find_one({"user_id": body.doctor_user_id, "role": "doctor"}, USER_PROJECTION)
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
        patient_user_id, doctor_user_id = user["user_id"], body.doctor_user_id
        profile_id = profile_key(user, body.profile_id)

    encounter = {
        "encounter_id": f"enc_{uuid.uuid4().hex[:12]}",
        "patient_user_id": patient_user_id,
        "profile_id": profile_id,
        "doctor_user_id": doctor_user_id,
        "scheduled_at": body.scheduled_at or iso(),
        "started_at": None,
        "ended_at": None,
        "status": "scheduled",
        "reason_for_visit": body.reason_for_visit,
        "created_at": iso(),
        "updated_at": iso(),
    }
    await db.encounters.insert_one(dict(encounter))
    return encounter


async def _decorate_encounters(encounters):
    if not encounters:
        return []
    user_ids = {e["patient_user_id"] for e in encounters} | {e["doctor_user_id"] for e in encounters}
    enc_ids = [e["encounter_id"] for e in encounters]
    users = await db.users.find({"user_id": {"$in": list(user_ids)}}, USER_PROJECTION).to_list(400)
    artifacts = await db.clinical_artifacts.find(
        {"encounter_id": {"$in": enc_ids}, "artifact_type": "previsit_brief"},
        {"_id": 0, "artifact_id": 1, "status": 1, "encounter_id": 1, "created_at": 1},
    ).sort("created_at", 1).to_list(400)
    names = {u["user_id"]: u.get("name") for u in users}
    briefings = {a["encounter_id"]: {"artifact_id": a["artifact_id"], "status": a["status"]} for a in artifacts}
    forms = await db.intake_forms.find(
        {"encounter_id": {"$in": enc_ids}}, {"_id": 0, "encounter_id": 1, "status": 1, "expires_at": 1}
    ).to_list(400)
    intakes = {f["encounter_id"]: {"status": f["status"], "expires_at": f["expires_at"]} for f in forms}
    return [{
        **enc,
        "patient_name": names.get(enc["patient_user_id"]),
        "doctor_name": names.get(enc["doctor_user_id"]),
        "briefing": briefings.get(enc["encounter_id"]),
        "intake": intakes.get(enc["encounter_id"]),
    } for enc in encounters]


@api.get("/encounters")
async def list_encounters(user=Depends(get_current_user)):
    field = "doctor_user_id" if user.get("role") == "doctor" else "patient_user_id"
    encounters = await db.encounters.find({field: user["user_id"]}, {"_id": 0}).sort("scheduled_at", -1).to_list(200)
    return await _decorate_encounters(encounters)


@api.get("/encounters/{encounter_id}")
async def get_encounter(encounter_id: str, user=Depends(get_current_user)):
    enc = await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")
    if user["user_id"] not in (enc["patient_user_id"], enc["doctor_user_id"]):
        raise HTTPException(status_code=403, detail="Not a participant in this encounter")
    patient = await db.users.find_one({"user_id": enc["patient_user_id"]}, USER_PROJECTION)
    artifact = None
    if user.get("role") == "doctor":
        latest = await db.clinical_artifacts.find(
            {"encounter_id": encounter_id, "artifact_type": "previsit_brief"}, {"_id": 0}
        ).sort("created_at", -1).to_list(1)
        artifact = latest[0] if latest else None
    return {"encounter": enc, "patient": patient, "artifact": artifact}


@api.patch("/encounters/{encounter_id}")
async def update_encounter(encounter_id: str, body: EncounterUpdate, user=Depends(require_doctor)):
    enc = await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")
    await assert_doctor_can_access_patient(db, user, enc["patient_user_id"])
    update = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if "status" in update:
        if update["status"] not in ("scheduled", "in_progress", "completed", "cancelled"):
            raise HTTPException(status_code=400, detail="Invalid status")
        if update["status"] == "in_progress" and not enc.get("started_at"):
            update["started_at"] = iso()
        if update["status"] == "completed":
            update["ended_at"] = iso()
    update["updated_at"] = iso()
    await db.encounters.update_one({"encounter_id": encounter_id}, {"$set": update})
    return await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0})


@api.post("/agents/previsit/{encounter_id}")
async def generate_previsit_brief(encounter_id: str, user=Depends(require_doctor)):
    enc = await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")
    await assert_doctor_can_access_patient(db, user, enc["patient_user_id"])

    try:
        content, run_id = await run_agent(
            db, PREVISIT_AGENT,
            patient_user_id=enc["patient_user_id"],
            encounter_id=encounter_id,
            invoked_by=user["user_id"],
            profile_id=enc["profile_id"],
            encounter=enc,
        )
    except AgentRunFailed as exc:
        raise _agent_http_error(exc)

    reference_flags, _ = await agent_tools.get_interaction_flags(db, enc["profile_id"])
    artifact = {
        "artifact_id": f"art_{uuid.uuid4().hex[:12]}",
        "artifact_type": "previsit_brief",
        "encounter_id": encounter_id,
        "patient_user_id": enc["patient_user_id"],
        "doctor_user_id": user["user_id"],
        "content": content,
        "edited_content": None,
        "reference_flags": reference_flags,
        "status": "draft",
        "signed_by": None,
        "signed_at": None,
        "agent_run_id": run_id,
        "created_at": iso(),
        "updated_at": iso(),
    }
    await db.clinical_artifacts.insert_one(dict(artifact))
    await db.agent_runs.update_one(
        {"agent_run_id": run_id},
        {"$set": {"output_ref": {"collection": "clinical_artifacts", "id": artifact["artifact_id"]}}},
    )
    return artifact


async def _load_artifact_for_doctor(artifact_id: str, doctor):
    artifact = await db.clinical_artifacts.find_one({"artifact_id": artifact_id}, {"_id": 0})
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    await assert_doctor_can_access_patient(db, doctor, artifact["patient_user_id"])
    return artifact


class ArtifactUpdate(BaseModel):
    edited_content: dict


@api.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str, user=Depends(require_doctor)):
    artifact = await _load_artifact_for_doctor(artifact_id, user)
    await db.agent_runs.update_one(
        {"agent_run_id": artifact["agent_run_id"], "human_action": "none"},
        {"$set": {"human_action": "viewed", "human_action_at": iso()}},
    )
    return artifact


@api.patch("/artifacts/{artifact_id}")
async def update_artifact(artifact_id: str, body: ArtifactUpdate, user=Depends(require_doctor)):
    artifact = await _load_artifact_for_doctor(artifact_id, user)
    if artifact["status"] == "signed":
        raise HTTPException(status_code=409, detail="Artifact is signed and cannot be modified")
    if artifact["status"] == "published":
        raise HTTPException(status_code=409, detail="This summary was already sent to the patient")
    await db.clinical_artifacts.update_one(
        {"artifact_id": artifact_id},
        {"$set": {"edited_content": body.edited_content, "status": "reviewed", "updated_at": iso()}},
    )
    await db.agent_runs.update_one(
        {"agent_run_id": artifact["agent_run_id"]},
        {"$set": {"human_action": "edited", "human_action_at": iso()}},
    )
    return await db.clinical_artifacts.find_one({"artifact_id": artifact_id}, {"_id": 0})


@api.post("/artifacts/{artifact_id}/sign")
async def sign_artifact(artifact_id: str, user=Depends(require_doctor)):
    artifact = await _load_artifact_for_doctor(artifact_id, user)
    if artifact["status"] == "signed":
        raise HTTPException(status_code=409, detail="Artifact is already signed")
    if artifact["artifact_type"] == "soap_note":
        content = artifact.get("edited_content") or artifact["content"]
        pending = [i for i in range(len(content.get("low_confidence_segments") or []))
                   if i not in (artifact.get("acknowledged_segments") or [])]
        if pending:
            raise HTTPException(
                status_code=409,
                detail=f"{len(pending)} low-confidence segment(s) still need acknowledgement before signing",
            )
    await db.clinical_artifacts.update_one(
        {"artifact_id": artifact_id},
        {"$set": {"status": "signed", "signed_by": user["user_id"], "signed_at": iso(), "updated_at": iso()}},
    )
    await db.agent_runs.update_one(
        {"agent_run_id": artifact["agent_run_id"]},
        {"$set": {"human_action": "approved", "human_action_at": iso()}},
    )
    return await db.clinical_artifacts.find_one({"artifact_id": artifact_id}, {"_id": 0})


class ThreadMessageIn(BaseModel):
    question: str = Field(min_length=1)


@api.get("/artifacts/{artifact_id}/thread")
async def get_briefing_thread(artifact_id: str, user=Depends(require_doctor)):
    artifact = await _load_artifact_for_doctor(artifact_id, user)
    thread = await db.briefing_threads.find_one({"artifact_id": artifact_id}, {"_id": 0})
    return thread or {"artifact_id": artifact_id, "encounter_id": artifact["encounter_id"], "messages": []}


@api.post("/artifacts/{artifact_id}/thread")
async def ask_briefing_question(artifact_id: str, body: ThreadMessageIn, user=Depends(require_doctor)):
    artifact = await _load_artifact_for_doctor(artifact_id, user)
    enc = await db.encounters.find_one({"encounter_id": artifact["encounter_id"]}, {"_id": 0})
    thread = await db.briefing_threads.find_one({"artifact_id": artifact_id}, {"_id": 0})
    if not thread:
        thread = {
            "thread_id": f"thr_{uuid.uuid4().hex[:12]}",
            "artifact_id": artifact_id,
            "encounter_id": artifact["encounter_id"],
            "patient_user_id": artifact["patient_user_id"],
            "doctor_user_id": user["user_id"],
            "messages": [],
            "created_at": iso(),
            "updated_at": iso(),
        }
        await db.briefing_threads.insert_one(dict(thread))

    doctor_msg = {
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "role": "doctor",
        "content": body.question,
        "cited_records": [],
        "refused": False,
        "refusal_reason": None,
        "agent_run_id": None,
        "created_at": iso(),
    }

    try:
        answer, run_id = await run_agent(
            db, BRIEFING_QA_AGENT,
            patient_user_id=artifact["patient_user_id"],
            encounter_id=artifact["encounter_id"],
            invoked_by=user["user_id"],
            profile_id=(enc or {}).get("profile_id") or artifact["patient_user_id"],
            artifact=artifact,
            question=body.question,
            history=thread["messages"],
        )
    except AgentRunFailed as exc:
        raise _agent_http_error(exc)

    assistant_msg = {
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "role": "assistant",
        "content": answer.get("answer") or "",
        "cited_records": answer.get("cited_records") or [],
        "refused": bool(answer.get("refused")),
        "refusal_reason": answer.get("refusal_reason"),
        "agent_run_id": run_id,
        "created_at": iso(),
    }
    await db.briefing_threads.update_one(
        {"artifact_id": artifact_id},
        {"$push": {"messages": {"$each": [doctor_msg, assistant_msg]}}, "$set": {"updated_at": iso()}},
    )
    return await db.briefing_threads.find_one({"artifact_id": artifact_id}, {"_id": 0})


@api.get("/agents/runs")
async def list_agent_runs(limit: int = Query(50, le=200), skip: int = 0,
                          patient_user_id: Optional[str] = None, user=Depends(require_doctor)):
    query = {"invoked_by_user_id": user["user_id"]}
    if patient_user_id:
        await assert_doctor_can_access_patient(db, user, patient_user_id)
        query["patient_user_id"] = patient_user_id
    total = await db.agent_runs.count_documents(query)
    runs = await db.agent_runs.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).to_list(limit)
    return {"total": total, "limit": limit, "skip": skip, "runs": runs}


# ---------- Intake Agent: pre-visit questionnaire ----------
class IntakeResponseIn(BaseModel):
    question_id: str
    answer: Any


class IntakeResponsesIn(BaseModel):
    responses: List[IntakeResponseIn]


def _intake_expiry(encounter):
    """Defaults to the appointment time; a form is never born already expired."""
    scheduled = encounter.get("scheduled_at") or iso()
    floor = iso(now_utc() + timedelta(hours=24))
    return max(scheduled, floor)


async def _patient_encounter(encounter_id: str, user):
    enc = await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")
    if enc["patient_user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="This intake form belongs to another patient")
    return enc


@api.post("/agents/intake/{encounter_id}")
async def generate_intake_form(encounter_id: str, user=Depends(require_doctor)):
    enc = await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")
    await assert_doctor_can_access_patient(db, user, enc["patient_user_id"])

    existing = await db.intake_forms.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if existing and existing.get("responses"):
        raise HTTPException(status_code=409, detail="The patient has already started answering this form")

    try:
        content, run_id = await run_agent(
            db, INTAKE_AGENT,
            patient_user_id=enc["patient_user_id"],
            encounter_id=encounter_id,
            invoked_by=user["user_id"],
            profile_id=enc["profile_id"],
            encounter=enc,
        )
    except AgentRunFailed as exc:
        raise _agent_http_error(exc)

    form = {
        "intake_form_id": f"intake_{uuid.uuid4().hex[:12]}",
        "encounter_id": encounter_id,
        "patient_user_id": enc["patient_user_id"],
        "profile_id": enc["profile_id"],
        "questions": content["questions"],
        "responses": [],
        "status": "pending",
        "agent_run_id": run_id,
        "expires_at": _intake_expiry(enc),
        "created_at": iso(),
        "updated_at": iso(),
    }
    await db.intake_forms.replace_one({"encounter_id": encounter_id}, dict(form), upsert=True)
    await db.agent_runs.update_one(
        {"agent_run_id": run_id},
        {"$set": {"output_ref": {"collection": "intake_forms", "id": form["intake_form_id"]}}},
    )
    return form


@api.get("/intake/{encounter_id}")
async def get_my_intake(encounter_id: str, user=Depends(get_current_user)):
    enc = await _patient_encounter(encounter_id, user)
    form = await db.intake_forms.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if not form:
        raise HTTPException(status_code=404, detail="No intake form for this visit yet")
    return {**form, "scheduled_at": enc["scheduled_at"], "reason_for_visit": enc.get("reason_for_visit")}


@api.post("/intake/{encounter_id}/responses")
async def submit_intake_responses(encounter_id: str, body: IntakeResponsesIn, user=Depends(get_current_user)):
    enc = await _patient_encounter(encounter_id, user)
    form = await db.intake_forms.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if not form:
        raise HTTPException(status_code=404, detail="No intake form for this visit yet")
    if iso() > form["expires_at"]:
        raise HTTPException(status_code=409, detail="This questionnaire has closed. Please tell your doctor in person.")

    valid_ids = {q["question_id"] for q in form["questions"]}
    answers = {r["question_id"]: r for r in form.get("responses", [])}
    for item in body.responses:
        if item.question_id not in valid_ids:
            raise HTTPException(status_code=400, detail=f"Unknown question {item.question_id}")
        answers[item.question_id] = {
            "question_id": item.question_id, "answer": item.answer, "answered_at": iso(),
        }

    responses = [answers[q["question_id"]] for q in form["questions"] if q["question_id"] in answers]
    required = [q["question_id"] for q in form["questions"] if q.get("required")]
    complete = all(answers.get(q, {}).get("answer") not in (None, "", []) for q in required)
    status = "complete" if complete else ("partial" if responses else "pending")

    await db.intake_forms.update_one(
        {"encounter_id": encounter_id},
        {"$set": {"responses": responses, "status": status, "updated_at": iso()}},
    )

    if status == "complete" and form["status"] != "complete":
        await db.alerts.insert_one({
            "alert_id": f"alert_{uuid.uuid4().hex[:12]}",
            "user_id": enc["doctor_user_id"],
            "profile_id": enc["profile_id"],
            "type": "intake",
            "severity": "info",
            "message": f"{user.get('name')} completed pre-visit intake",
            "read": False,
            "created_at": iso(),
        })
    return await db.intake_forms.find_one({"encounter_id": encounter_id}, {"_id": 0})


@api.get("/doctor/intake/{encounter_id}")
async def doctor_get_intake(encounter_id: str, user=Depends(require_doctor)):
    enc = await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")
    await assert_doctor_can_access_patient(db, user, enc["patient_user_id"])
    form = await db.intake_forms.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if not form:
        return {"encounter_id": encounter_id, "status": "not_generated", "questions": [], "responses": []}
    return form


# ---------- Screening findings: structured, citable evidence from screening chats ----------
SCREENING_AGENT = ScreeningExtractionAgent()
SCREENING_STALE_DAYS = 90


async def extract_report_findings(report, invoked_by, encounter_id=None):
    """Structures one screening report. Never fails the caller — the report itself is already saved."""
    try:
        content, run_id = await run_agent(
            db, SCREENING_AGENT,
            patient_user_id=report["user_id"],
            encounter_id=encounter_id,
            invoked_by=invoked_by,
            report=report,
        )
    except AgentRunFailed:
        return None
    # Re-extraction keeps the id of a symptom already cited by an existing briefing.
    previous = {(f.get("symptom") or "").strip().lower(): f["finding_id"] for f in (report.get("findings") or [])}
    findings = content["findings"]
    for f in findings:
        stable = previous.get((f.get("symptom") or "").strip().lower())
        if stable:
            f["finding_id"] = stable
    await db.health_reports.update_one(
        {"report_id": report["report_id"]},
        {"$set": {"findings": content["findings"], "findings_agent_run_id": run_id,
                  "findings_extracted_at": iso()}},
    )
    await db.agent_runs.update_one(
        {"agent_run_id": run_id},
        {"$set": {"output_ref": {"collection": "health_reports", "id": report["report_id"]}}},
    )
    return content["findings"]

class ShareReport(BaseModel):
    encounter_id: Optional[str] = None


@api.put("/reports/{report_id}/share")
async def share_report_for_visit(report_id: str, body: ShareReport, user=Depends(get_current_user)):
    """A patient chooses which screening the doctor should read for a specific upcoming visit."""
    report = await db.health_reports.find_one({"report_id": report_id, "user_id": user["user_id"]}, {"_id": 0})
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if body.encounter_id:
        enc = await db.encounters.find_one(
            {"encounter_id": body.encounter_id, "patient_user_id": user["user_id"]}, {"_id": 0}
        )
        if not enc:
            raise HTTPException(status_code=404, detail="Visit not found")
    await db.health_reports.update_one(
        {"report_id": report_id}, {"$set": {"shared_encounter_id": body.encounter_id, "shared_at": iso()}}
    )
    return await db.health_reports.find_one({"report_id": report_id}, {"_id": 0})


@api.post("/doctor/reports/{report_id}/findings")
async def redo_report_findings(report_id: str, user=Depends(require_doctor)):
    report = await db.health_reports.find_one({"report_id": report_id}, {"_id": 0})
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    await assert_doctor_can_access_patient(db, user, report["user_id"])
    findings = await extract_report_findings(report, invoked_by=user["user_id"])
    if findings is None:
        raise HTTPException(status_code=502, detail="Could not structure this screening report")
    return await db.health_reports.find_one({"report_id": report_id}, {"_id": 0})


@api.get("/doctor/screening/{encounter_id}")
async def doctor_screening_view(encounter_id: str, user=Depends(require_doctor)):
    enc = await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")
    await assert_doctor_can_access_patient(db, user, enc["patient_user_id"])

    reports = await db.health_reports.find(
        {"user_id": enc["patient_user_id"]}, {"_id": 0}
    ).sort("generated_at", -1).to_list(10)
    timeline, _ = await agent_tools.get_symptom_timeline(db, enc["patient_user_id"], days=180)

    message_ids = [mid for r in reports for f in (r.get("findings") or []) for mid in f.get("source_message_ids", [])]
    messages = await db.chat_messages.find(
        {"message_id": {"$in": message_ids}}, {"_id": 0, "message_id": 1, "role": 1, "content": 1}
    ).to_list(500) if message_ids else []
    excerpts = {m["message_id"]: m for m in messages}

    out = []
    for r in reports:
        age_days = None
        try:
            age_days = (now_utc() - datetime.fromisoformat(r["generated_at"])).days
        except (ValueError, TypeError):
            pass
        out.append({
            "report_id": r["report_id"],
            "generated_at": r["generated_at"],
            "age_days": age_days,
            "stale": age_days is not None and age_days > SCREENING_STALE_DAYS,
            "shared_for_this_visit": r.get("shared_encounter_id") == encounter_id,
            "shared_at": r.get("shared_at"),
            "findings_extracted_at": r.get("findings_extracted_at"),
            "findings": r.get("findings") or [],
            "content": r.get("content"),
        })
    return {"encounter_id": encounter_id, "reports": out, "symptom_timeline": timeline["symptoms"],
            "excerpts": excerpts, "stale_after_days": SCREENING_STALE_DAYS}


@api.get("/doctor/dashboard")
async def doctor_dashboard(user=Depends(require_doctor)):
    """Everything a clinician needs on landing: today's list, what needs review, what's waiting on patients."""
    patient_query = {"sharing_enabled": True, "role": "patient"}
    if not user.get("is_admin"):
        patient_query["assigned_doctor_user_id"] = user["user_id"]
    patients = await db.users.find(patient_query, {"_id": 0, "user_id": 1, "name": 1}).to_list(300)
    patient_ids = [p["user_id"] for p in patients]
    names = {p["user_id"]: p["name"] for p in patients}

    encounters = await db.encounters.find(
        {"doctor_user_id": user["user_id"]}, {"_id": 0}
    ).sort("scheduled_at", 1).to_list(400)
    now = now_utc()
    today = now.strftime("%Y-%m-%d")
    week_end = iso(now + timedelta(days=7))

    enc_ids = [e["encounter_id"] for e in encounters]
    artifacts = await db.clinical_artifacts.find(
        {"encounter_id": {"$in": enc_ids}, "artifact_type": "previsit_brief"},
        {"_id": 0, "encounter_id": 1, "status": 1, "artifact_id": 1, "created_at": 1},
    ).sort("created_at", 1).to_list(400) if enc_ids else []
    briefings = {a["encounter_id"]: a for a in artifacts}
    forms = await db.intake_forms.find(
        {"encounter_id": {"$in": enc_ids}}, {"_id": 0, "encounter_id": 1, "status": 1}
    ).to_list(400) if enc_ids else []
    intakes = {f["encounter_id"]: f["status"] for f in forms}

    def row(e):
        brief = briefings.get(e["encounter_id"])
        return {
            "encounter_id": e["encounter_id"],
            "patient_user_id": e["patient_user_id"],
            "patient_name": names.get(e["patient_user_id"]),
            "scheduled_at": e["scheduled_at"],
            "reason_for_visit": e.get("reason_for_visit"),
            "status": e["status"],
            "briefing_status": brief["status"] if brief else None,
            "intake_status": intakes.get(e["encounter_id"]),
        }

    upcoming = [e for e in encounters
                if e["status"] in ("scheduled", "in_progress") and names.get(e["patient_user_id"])]
    todays = [row(e) for e in upcoming if (e["scheduled_at"] or "")[:10] == today]
    this_week = [row(e) for e in upcoming if today <= (e["scheduled_at"] or "")[:10] and e["scheduled_at"] <= week_end]
    needs_briefing = [r for r in this_week if r["briefing_status"] is None]
    awaiting_signature = [r for r in this_week if r["briefing_status"] in ("draft", "reviewed")]
    awaiting_intake = [r for r in this_week if r["intake_status"] in ("pending", "partial")]

    alerts = await db.alerts.find(
        {"user_id": {"$in": patient_ids + [user["user_id"]]}, "read": False}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    for a in alerts:
        # Alerts raised FOR the doctor (e.g. intake completed) name the patient via profile_id.
        a["patient_name"] = names.get(a.get("user_id")) or names.get(a.get("profile_id"))

    grouped = {}
    for a in alerts:
        key = (a.get("type") or "other", a.get("severity") or "info")
        g = grouped.setdefault(key, {"type": key[0], "severity": key[1], "count": 0,
                                     "latest_at": a["created_at"], "patients": [], "items": []})
        g["count"] += 1
        g["latest_at"] = max(g["latest_at"], a["created_at"])
        if a.get("patient_name") and a["patient_name"] not in g["patients"]:
            g["patients"].append(a["patient_name"])
        if len(g["items"]) < 5:
            g["items"].append({"alert_id": a["alert_id"], "message": a.get("message"),
                               "patient_name": a.get("patient_name"), "created_at": a["created_at"]})
    alert_groups = sorted(grouped.values(), key=lambda g: (g["severity"] != "critical", -g["count"]))
    runs = await db.agent_runs.find(
        {"invoked_by_user_id": user["user_id"]},
        {"_id": 0, "agent_run_id": 1, "agent_type": 1, "status": 1, "latency_ms": 1,
         "created_at": 1, "patient_user_id": 1, "encounter_id": 1},
    ).sort("created_at", -1).to_list(8)
    for r in runs:
        r["patient_name"] = names.get(r.get("patient_user_id"))

    return {
        "stats": {
            "patients": len(patients),
            "today": len(todays),
            "this_week": len(this_week),
            "needs_briefing": len(needs_briefing),
            "awaiting_signature": len(awaiting_signature),
            "awaiting_intake": len(awaiting_intake),
            "unread_alerts": len(alerts),
        },
        "todays_visits": todays,
        "upcoming_visits": this_week[:8],
        "needs_briefing": needs_briefing[:5],
        "awaiting_signature": awaiting_signature[:5],
        "awaiting_intake": awaiting_intake[:5],
        "alerts": alerts[:6],
        "alert_groups": alert_groups,
        "recent_runs": runs,
    }


# ---------- Clinical Scribe: consent, audio, SOAP notes ----------
SCRIBE_AGENT = ScribeAgent()
AUDIO_OBJECT_PREFIX = "consultation-audio"
AUDIO_RETENTION_DAYS = int(os.environ.get("AUDIO_RETENTION_DAYS", "30"))
_fernet = Fernet(os.environ["AUDIO_ENCRYPTION_KEY"].encode())
PATIENT_SUMMARY_AGENT = PatientSummaryAgent()
AUDIO_EXTENSIONS = {
    "audio/webm": "webm", "audio/mpeg": "mp3", "audio/mp3": "mp3", "audio/mp4": "mp4",
    "audio/m4a": "m4a", "audio/x-m4a": "m4a", "audio/wav": "wav", "audio/x-wav": "wav",
}


async def resolved_transcription_provider() -> str:
    row = await db.app_settings.find_one({"key": "transcription_provider"}, {"_id": 0})
    return (row or {}).get("value") or default_provider()


class TranscriptionProviderIn(BaseModel):
    provider: str


@api.get("/admin/transcription")
async def get_transcription_provider(user=Depends(require_admin)):
    return {"provider": await resolved_transcription_provider(), "env_default": default_provider()}


@api.put("/admin/transcription")
async def set_transcription_provider(body: TranscriptionProviderIn, user=Depends(require_admin)):
    provider = body.provider.strip().lower()
    if provider not in ("stub", "hosted"):
        raise HTTPException(status_code=400, detail="Provider must be 'stub' or 'hosted'")
    await db.app_settings.update_one(
        {"key": "transcription_provider"},
        {"$set": {"value": provider, "updated_at": iso(), "updated_by": user["user_id"]}},
        upsert=True,
    )
    return {"provider": provider, "env_default": default_provider()}


class ConsentIn(BaseModel):
    granted: bool


@api.post("/encounters/{encounter_id}/consent")
async def record_recording_consent(encounter_id: str, body: ConsentIn, user=Depends(get_current_user)):
    enc = await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")
    if user["user_id"] not in (enc["patient_user_id"], enc["doctor_user_id"]):
        raise HTTPException(status_code=403, detail="Not a participant in this encounter")
    consent = {"granted": body.granted, "granted_at": iso(), "granted_by": user["user_id"]}
    await db.encounters.update_one({"encounter_id": encounter_id},
                                   {"$set": {"recording_consent": consent, "updated_at": iso()}})
    return consent


async def _consented_encounter(encounter_id: str, doctor):
    enc = await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")
    await assert_doctor_can_access_patient(db, doctor, enc["patient_user_id"])
    if not (enc.get("recording_consent") or {}).get("granted"):
        raise HTTPException(status_code=403, detail="Recording consent has not been given for this encounter")
    return enc


@api.post("/encounters/{encounter_id}/audio/init")
async def init_audio_upload(encounter_id: str, mime_type: str = "audio/webm", user=Depends(require_doctor)):
    enc = await _consented_encounter(encounter_id, user)
    consent = enc["recording_consent"]
    audio = {
        "audio_id": f"aud_{uuid.uuid4().hex[:12]}",
        "encounter_id": encounter_id,
        "patient_user_id": enc["patient_user_id"],
        "storage_path": None,
        "duration_seconds": 0.0,
        "mime_type": mime_type,
        "size_bytes": 0,
        "consent_recorded_at": consent["granted_at"],
        "consent_by_user_id": consent["granted_by"],
        "transcription_status": "pending",
        "transcript": None,
        "retention_expires_at": iso(now_utc() + timedelta(days=AUDIO_RETENTION_DAYS)),
        "deleted_at": None,
        "created_at": iso(),
    }
    await db.consultation_audio.insert_one(dict(audio))
    return audio


LIVE_CHUNK_MAX_BYTES = 5 * 1024 * 1024


@api.post("/encounters/{encounter_id}/audio/live")
async def live_transcribe_chunk(encounter_id: str, offset_seconds: float = Form(0.0),
                                window_seconds: float = Form(10.0), chunk: UploadFile = File(...),
                                user=Depends(require_doctor)):
    """Transcribes one ~10s slice while recording so the clinician sees lines appear. Nothing is stored."""
    await _consented_encounter(encounter_id, user)
    data = await chunk.read(LIVE_CHUNK_MAX_BYTES + 1)
    if len(data) > LIVE_CHUNK_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Live audio slice is too large")
    if len(data) < 1024:
        return {"offset_seconds": offset_seconds, "segments": []}
    provider = await resolved_transcription_provider()
    suffix = AUDIO_EXTENSIONS.get((chunk.content_type or "").split(";")[0].strip(), "webm")
    scratch = Path(tempfile.mkstemp(suffix=f".{suffix}")[1])
    try:
        scratch.write_bytes(data)
        result = await get_transcriber(provider).transcribe(str(scratch), language_hint="ar-SA")
    except Exception as exc:
        logging.getLogger(__name__).exception("Live transcription failed for %s", encounter_id)
        raise HTTPException(status_code=502, detail=f"Live transcription failed: {type(exc).__name__}")
    finally:
        scratch.unlink(missing_ok=True)
    segments = result.get("segments") or []
    if provider == "stub":
        segments = [s for s in segments if offset_seconds <= s["start"] < offset_seconds + window_seconds]
    else:
        segments = [{**s, "start": round(s["start"] + offset_seconds, 2), "end": round(s["end"] + offset_seconds, 2)}
                    for s in segments]
    return {"offset_seconds": offset_seconds, "segments": segments}


@api.post("/audio/{audio_id}/chunk")
async def upload_audio_chunk(audio_id: str, index: int = Form(...), chunk: UploadFile = File(...),
                             user=Depends(require_doctor)):
    audio = await db.consultation_audio.find_one({"audio_id": audio_id}, {"_id": 0})
    if not audio:
        raise HTTPException(status_code=404, detail="Upload not found")
    await _consented_encounter(audio["encounter_id"], user)
    part = f"{STORAGE_APP}/{AUDIO_OBJECT_PREFIX}/{audio_id}/part-{index:04d}"
    data = await chunk.read()
    try:
        put_object(part, data, "application/octet-stream")
    except Exception:
        logging.getLogger(__name__).exception("Audio chunk upload failed for %s", audio_id)
        raise HTTPException(status_code=502, detail="Could not store that part of the recording")
    await db.consultation_audio.update_one({"audio_id": audio_id},
                                           {"$inc": {"size_bytes": len(data)},
                                            "$addToSet": {"chunk_paths": part}})
    return {"audio_id": audio_id, "index": index, "received_bytes": len(data)}


@api.post("/audio/{audio_id}/complete")
async def complete_audio_upload(audio_id: str, duration_seconds: float = Form(0.0), user=Depends(require_doctor)):
    audio = await db.consultation_audio.find_one({"audio_id": audio_id}, {"_id": 0})
    if not audio:
        raise HTTPException(status_code=404, detail="Upload not found")
    enc = await _consented_encounter(audio["encounter_id"], user)
    parts = sorted(audio.get("chunk_paths") or [])
    if not parts:
        raise HTTPException(status_code=400, detail="No audio was uploaded")

    raw = b"".join(get_object(path)[0] for path in parts)
    try:
        stored = put_object(f"{STORAGE_APP}/{AUDIO_OBJECT_PREFIX}/{audio_id}.enc",
                            _fernet.encrypt(raw), "application/octet-stream")
    except Exception:
        logging.getLogger(__name__).exception("Audio upload to object storage failed for %s", audio_id)
        raise HTTPException(status_code=502, detail="Could not store the recording. Try again.")
    await db.consultation_audio.update_one(
        {"audio_id": audio_id},
        {"$set": {"storage_path": stored["path"], "storage_backend": "object",
                  "duration_seconds": duration_seconds, "transcription_status": "processing"}},
    )

    suffix = AUDIO_EXTENSIONS.get(audio.get("mime_type"), "webm")
    scratch = Path(tempfile.mkstemp(suffix=f".{suffix}")[1])
    try:
        scratch.write_bytes(raw)
        provider = await resolved_transcription_provider()
        transcript = await get_transcriber(provider).transcribe(str(scratch), language_hint="ar-SA")
    except Exception as exc:
        await db.consultation_audio.update_one({"audio_id": audio_id},
                                               {"$set": {"transcription_status": "failed"}})
        logging.getLogger(__name__).exception("Transcription failed for %s", audio_id)
        raise HTTPException(status_code=502, detail=f"Transcription failed: {type(exc).__name__}")
    finally:
        scratch.unlink(missing_ok=True)

    await db.consultation_audio.update_one(
        {"audio_id": audio_id},
        {"$set": {"transcript": transcript, "transcription_status": "complete"}},
    )

    try:
        content, run_id = await run_agent(
            db, SCRIBE_AGENT,
            patient_user_id=enc["patient_user_id"],
            encounter_id=enc["encounter_id"],
            invoked_by=user["user_id"],
            profile_id=enc["profile_id"],
            transcript=transcript,
            audio_id=audio_id,
        )
    except AgentRunFailed as exc:
        raise _agent_http_error(exc)

    artifact = {
        "artifact_id": f"art_{uuid.uuid4().hex[:12]}",
        "artifact_type": "soap_note",
        "encounter_id": enc["encounter_id"],
        "patient_user_id": enc["patient_user_id"],
        "doctor_user_id": user["user_id"],
        "content": content,
        "edited_content": None,
        "audio_id": audio_id,
        "acknowledged_segments": [],
        "status": "draft",
        "signed_by": None,
        "signed_at": None,
        "agent_run_id": run_id,
        "created_at": iso(),
        "updated_at": iso(),
    }
    await db.clinical_artifacts.insert_one(dict(artifact))
    await db.agent_runs.update_one(
        {"agent_run_id": run_id},
        {"$set": {"output_ref": {"collection": "clinical_artifacts", "id": artifact["artifact_id"]}}},
    )
    return artifact


@api.get("/encounters/{encounter_id}/soap")
async def get_soap_note(encounter_id: str, user=Depends(require_doctor)):
    enc = await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")
    await assert_doctor_can_access_patient(db, user, enc["patient_user_id"])
    latest = await db.clinical_artifacts.find(
        {"encounter_id": encounter_id, "artifact_type": "soap_note"}, {"_id": 0}
    ).sort("created_at", -1).to_list(1)
    audio = await db.consultation_audio.find_one(
        {"encounter_id": encounter_id},
        {"_id": 0, "audio_id": 1, "transcription_status": 1, "duration_seconds": 1,
         "retention_expires_at": 1, "deleted_at": 1, "transcript": 1, "mime_type": 1},
    )
    summary = await db.clinical_artifacts.find(
        {"encounter_id": encounter_id, "artifact_type": "patient_summary"}, {"_id": 0}
    ).sort("created_at", -1).to_list(1)
    return {"encounter_id": encounter_id, "consent": enc.get("recording_consent"),
            "audio": audio, "note": latest[0] if latest else None,
            "patient_summary": summary[0] if summary else None,
            "transcript_segments": (audio or {}).get("transcript", {}).get("segments") if audio else None}


# ---------- Note to the patient: plain-language visit summary ----------
@api.post("/artifacts/{artifact_id}/patient-summary")
async def draft_patient_summary(artifact_id: str, user=Depends(require_doctor)):
    note = await _load_artifact_for_doctor(artifact_id, user)
    if note["artifact_type"] != "soap_note":
        raise HTTPException(status_code=400, detail="Patient summaries are drafted from a clinical note")
    if note["status"] != "signed":
        raise HTTPException(status_code=409, detail="Sign the clinical note before drafting the patient summary")
    existing = await db.clinical_artifacts.find_one(
        {"source_artifact_id": artifact_id, "artifact_type": "patient_summary", "status": "published"},
        {"_id": 0},
    )
    if existing:
        raise HTTPException(status_code=409, detail="A summary for this visit was already sent to the patient")

    enc = await db.encounters.find_one({"encounter_id": note["encounter_id"]}, {"_id": 0})
    try:
        content, run_id = await run_agent(
            db, PATIENT_SUMMARY_AGENT,
            patient_user_id=note["patient_user_id"],
            encounter_id=note["encounter_id"],
            invoked_by=user["user_id"],
            note=note.get("edited_content") or note["content"],
            source_artifact_id=artifact_id,
            reason_for_visit=(enc or {}).get("reason_for_visit"),
        )
    except AgentRunFailed as exc:
        raise _agent_http_error(exc)

    await db.clinical_artifacts.delete_many(
        {"source_artifact_id": artifact_id, "artifact_type": "patient_summary"})
    artifact = {
        "artifact_id": f"art_{uuid.uuid4().hex[:12]}",
        "artifact_type": "patient_summary",
        "source_artifact_id": artifact_id,
        "encounter_id": note["encounter_id"],
        "patient_user_id": note["patient_user_id"],
        "doctor_user_id": user["user_id"],
        "content": content,
        "edited_content": None,
        "status": "draft",
        "published_at": None,
        "signed_by": None,
        "signed_at": None,
        "agent_run_id": run_id,
        "created_at": iso(),
        "updated_at": iso(),
    }
    await db.clinical_artifacts.insert_one(dict(artifact))
    await db.agent_runs.update_one(
        {"agent_run_id": run_id},
        {"$set": {"output_ref": {"collection": "clinical_artifacts", "id": artifact["artifact_id"]}}},
    )
    return artifact


@api.post("/artifacts/{artifact_id}/publish")
async def publish_patient_summary(artifact_id: str, user=Depends(require_doctor)):
    artifact = await _load_artifact_for_doctor(artifact_id, user)
    if artifact["artifact_type"] != "patient_summary":
        raise HTTPException(status_code=400, detail="Only a patient summary can be sent to the patient")
    if artifact["status"] == "published":
        raise HTTPException(status_code=409, detail="This summary was already sent to the patient")
    enc = await db.encounters.find_one({"encounter_id": artifact["encounter_id"]}, {"_id": 0})
    await db.clinical_artifacts.update_one(
        {"artifact_id": artifact_id},
        {"$set": {"status": "published", "published_at": iso(), "published_by": user["user_id"],
                  "updated_at": iso()}},
    )
    await db.agent_runs.update_one(
        {"agent_run_id": artifact["agent_run_id"]},
        {"$set": {"human_action": "approved", "human_action_at": iso()}},
    )
    await db.alerts.insert_one({
        "alert_id": f"alert_{uuid.uuid4().hex[:12]}",
        "user_id": artifact["patient_user_id"],
        "profile_id": (enc or {}).get("profile_id") or artifact["patient_user_id"],
        "type": "visit_summary",
        "severity": "info",
        "message": f"{user.get('name')} sent you a summary of your visit",
        "read": False,
        "created_at": iso(),
    })
    return await db.clinical_artifacts.find_one({"artifact_id": artifact_id}, {"_id": 0})


@api.get("/patient/visit-summaries")
async def list_visit_summaries(user=Depends(get_current_user)):
    rows = await db.clinical_artifacts.find(
        {"patient_user_id": user["user_id"], "artifact_type": "patient_summary", "status": "published"},
        {"_id": 0},
    ).sort("published_at", -1).to_list(50)
    if not rows:
        return []
    encounters = {e["encounter_id"]: e for e in await db.encounters.find(
        {"encounter_id": {"$in": [r["encounter_id"] for r in rows]}},
        {"_id": 0, "encounter_id": 1, "reason_for_visit": 1, "scheduled_at": 1},
    ).to_list(50)}
    doctors = {d["user_id"]: d for d in await db.users.find(
        {"user_id": {"$in": list({r["doctor_user_id"] for r in rows})}},
        {"_id": 0, "user_id": 1, "name": 1, "specialty": 1},
    ).to_list(50)}
    for r in rows:
        enc = encounters.get(r["encounter_id"]) or {}
        doc = doctors.get(r["doctor_user_id"]) or {}
        r["reason_for_visit"] = enc.get("reason_for_visit")
        r["scheduled_at"] = enc.get("scheduled_at")
        r["doctor_name"] = doc.get("name")
        r["doctor_specialty"] = doc.get("specialty")
    return rows


@api.get("/audio/{audio_id}/stream")
async def stream_audio(audio_id: str, user=Depends(require_doctor)):
    audio = await db.consultation_audio.find_one({"audio_id": audio_id}, {"_id": 0})
    if not audio:
        raise HTTPException(status_code=404, detail="Recording not found")
    await _consented_encounter(audio["encounter_id"], user)
    if not audio.get("storage_path"):
        raise HTTPException(status_code=410, detail="This recording has passed its retention period")
    if audio.get("storage_backend") == "object":
        data = _fernet.decrypt(get_object(audio["storage_path"])[0])
    else:
        if not Path(audio["storage_path"]).exists():
            raise HTTPException(status_code=410, detail="This recording is no longer available")
        data = _fernet.decrypt(Path(audio["storage_path"]).read_bytes())
    return Response(content=data, media_type=audio.get("mime_type") or "audio/webm",
                    headers={"Cache-Control": "no-store"})


class AcknowledgeIn(BaseModel):
    index: int


@api.post("/artifacts/{artifact_id}/acknowledge")
async def acknowledge_low_confidence(artifact_id: str, body: AcknowledgeIn, user=Depends(require_doctor)):
    artifact = await _load_artifact_for_doctor(artifact_id, user)
    content = artifact.get("edited_content") or artifact["content"]
    segments = content.get("low_confidence_segments") or []
    if not 0 <= body.index < len(segments):
        raise HTTPException(status_code=400, detail="No such low-confidence segment")
    await db.clinical_artifacts.update_one(
        {"artifact_id": artifact_id},
        {"$addToSet": {"acknowledged_segments": body.index}, "$set": {"updated_at": iso()}},
    )
    return await db.clinical_artifacts.find_one({"artifact_id": artifact_id}, {"_id": 0})


async def purge_expired_audio():
    """Deletes audio bytes past retention; the metadata row survives with deleted_at set."""
    due = await db.consultation_audio.find(
        {"deleted_at": None, "retention_expires_at": {"$lte": iso()}}, {"_id": 0}
    ).to_list(500)
    purged = 0
    for audio in due:
        path = audio.get("storage_path")
        if path and audio.get("storage_backend") == "object":
            delete_object(path)
        elif path:
            Path(path).unlink(missing_ok=True)
        for part in audio.get("chunk_paths") or []:
            delete_object(part)
        await db.consultation_audio.update_one(
            {"audio_id": audio["audio_id"]},
            {"$set": {"storage_path": None, "transcript": None, "chunk_paths": [],
                      "deleted_at": iso()}},
        )
        purged += 1
    return {"purged": purged, "checked": len(due)}


@api.post("/admin/audio/purge")
async def purge_audio_now(user=Depends(require_admin)):
    return await purge_expired_audio()


@api.get("/")
async def root():
    return {"app": "Sihha AI", "status": "ok"}
# ---------- Phase 6: Pharmacy Marketplace ----------
# Sihha holds no stock, dispenses nothing and never verifies a prescription. Every order is
# fulfilled by a licensed partner. No LLM is involved in ordering, matching or compliance.
import requests
from pharmacy import compliance
from pharmacy import refill as refill_engine

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
STORAGE_APP = "sihha-ai"
_storage_key = None
RX_MIME = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp",
           "pdf": "application/pdf", "heic": "image/heic"}
PRESCRIPTION_VALID_DAYS = 180


def init_storage(force: bool = False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": os.environ["EMERGENT_LLM_KEY"]},
                         timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    for attempt in (0, 1):
        resp = requests.put(f"{STORAGE_URL}/objects/{path}",
                            headers={"X-Storage-Key": init_storage(force=attempt == 1),
                                     "Content-Type": content_type},
                            data=data, timeout=120)
        if resp.status_code == 404 and attempt == 0:
            continue
        resp.raise_for_status()
        return resp.json()


def get_object(path: str):
    for attempt in (0, 1):
        resp = requests.get(f"{STORAGE_URL}/objects/{path}",
                            headers={"X-Storage-Key": init_storage(force=attempt == 1)}, timeout=60)
        if resp.status_code == 404 and attempt == 0:
            continue
        resp.raise_for_status()
        return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


def delete_object(path: str) -> bool:
    """Best effort — retention must still mark the row purged even if the object is already gone."""
    try:
        resp = requests.delete(f"{STORAGE_URL}/objects/{path}",
                               headers={"X-Storage-Key": init_storage()}, timeout=60)
        return resp.status_code < 400
    except Exception:
        logging.getLogger(__name__).warning("Could not delete object %s", path)
        return False


PHARMACY_PUBLIC_FIELDS = ("pharmacy_id", "name_en", "name_ar", "sfda_license", "moh_license",
                          "cr_number", "fulfilment_mode", "handoff_url_template", "branches", "active")


def _is_sponsored(pharmacy: dict) -> bool:
    sponsorship = pharmacy.get("sponsorship") or {}
    if not sponsorship.get("tier"):
        return False
    until = sponsorship.get("active_until")
    return not until or until > iso()


def _directions_url(branch: dict) -> Optional[str]:
    if not branch or branch.get("lat") is None or branch.get("lng") is None:
        return None
    return f"https://www.google.com/maps/dir/?api=1&destination={branch['lat']},{branch['lng']}"


def _pharmacy_card(pharmacy: dict) -> dict:
    branches = pharmacy.get("branches") or []
    card = {k: pharmacy.get(k) for k in PHARMACY_PUBLIC_FIELDS}
    card["sponsored"] = _is_sponsored(pharmacy)
    card["sponsorship_tier"] = (pharmacy.get("sponsorship") or {}).get("tier")
    card["directions_url"] = _directions_url(branches[0] if branches else None)
    return card


def _rank_key(pharmacy: dict):
    sponsorship = pharmacy.get("sponsorship") or {}
    return (0 if _is_sponsored(pharmacy) else 1, sponsorship.get("rank") or 99)


def _handoff_url(pharmacy: dict, skus: List[str], branch_id: Optional[str] = None) -> Optional[str]:
    template = pharmacy.get("handoff_url_template")
    if not template:
        return None
    return (template.replace("{sku_list}", ",".join(skus))
            .replace("{branch_id}", branch_id or ((pharmacy.get("branches") or [{}])[0].get("branch_id") or "")))


async def _cart_doc(user, profile_id: Optional[str]):
    profile = profile_key(user, profile_id)
    cart = await db.carts.find_one({"profile_id": profile}, {"_id": 0})
    if not cart:
        cart = {
            "cart_id": f"cart_{uuid.uuid4().hex[:12]}",
            "user_id": user["user_id"],
            "profile_id": profile,
            "pharmacy_id": None,
            "items": [],
            "prescription_id": None,
            "created_at": iso(),
            "updated_at": iso(),
        }
        await db.carts.insert_one(dict(cart))
    return cart


async def _hydrate_cart(cart: dict) -> dict:
    pharmacy = await db.pharmacies.find_one({"pharmacy_id": cart["pharmacy_id"]}, {"_id": 0}) \
        if cart.get("pharmacy_id") else None
    items, entries = [], []
    for line in cart.get("items", []):
        item = await db.catalog_items.find_one({"item_id": line["item_id"]}, {"_id": 0})
        if not item:
            continue
        entries.append({"item": item, "qty": line["qty"]})
        items.append({**line, "requires_prescription": item.get("requires_prescription", False),
                      "days_supply": item.get("days_supply"),
                      "stock_status": item.get("stock_status"),
                      "violations": compliance.check_add_to_cart(item, pharmacy or {}, line["qty"])})
    prescription = await db.prescriptions.find_one({"prescription_id": cart["prescription_id"]}, {"_id": 0}) \
        if cart.get("prescription_id") else None
    subtotal = round(sum(l["qty"] * l["price_sar"] for l in cart.get("items", [])), 2)
    return {
        **cart,
        "items": items,
        "pharmacy": _pharmacy_card(pharmacy) if pharmacy else None,
        "prescription": prescription,
        "subtotal_sar": subtotal,
        "delivery_fee_sar": 0.0,
        "total_sar": subtotal,
        "violations": compliance.check_checkout(entries, pharmacy or {}, prescription) if entries else [],
    }


@api.get("/pharmacy/pharmacies")
async def list_pharmacies(city: Optional[str] = None, delivery_zone: Optional[str] = None,
                          user=Depends(get_current_user)):
    rows = await db.pharmacies.find({"active": True}, {"_id": 0}).to_list(100)
    out = []
    for pharmacy in rows:
        branches = pharmacy.get("branches") or []
        if city:
            branches = [b for b in branches if (b.get("city") or "").lower() == city.lower()]
        if delivery_zone:
            branches = [b for b in branches if delivery_zone in (b.get("delivery_zones") or [])]
        if (city or delivery_zone) and not branches:
            continue
        card = _pharmacy_card(pharmacy)
        card["branches"] = [{**b, "directions_url": _directions_url(b)} for b in branches]
        card["_rank"] = _rank_key(pharmacy)
        out.append(card)
    out.sort(key=lambda p: (p.pop("_rank"), p["name_en"] or ""))
    sponsored = [p["pharmacy_id"] for p in out if p["sponsored"]]
    if sponsored:
        await db.pharmacies.update_many({"pharmacy_id": {"$in": sponsored}}, {"$inc": {"stats.impressions": 1}})
    return out


@api.get("/pharmacy/catalog")
async def search_catalog(q: Optional[str] = None, category: Optional[str] = None,
                         pharmacy_id: Optional[str] = None, limit: int = Query(24, le=100),
                         skip: int = 0, user=Depends(get_current_user)):
    query = {"active": True}
    if category:
        query["category"] = category
    if pharmacy_id:
        query["pharmacy_id"] = pharmacy_id
    if q:
        needle = re.escape(q.strip())
        query["$or"] = [{"name_en": {"$regex": needle, "$options": "i"}},
                        {"name_ar": {"$regex": needle, "$options": "i"}},
                        {"generic_name": {"$regex": needle, "$options": "i"}}]
    rows = await db.catalog_items.find(query, {"_id": 0}).to_list(500)
    pharmacies = {p["pharmacy_id"]: p for p in await db.pharmacies.find({}, {"_id": 0}).to_list(100)}
    decorated = []
    for item in rows:
        pharmacy = pharmacies.get(item["pharmacy_id"]) or {}
        decorated.append({
            **item,
            "pharmacy": _pharmacy_card(pharmacy) if pharmacy else None,
            "orderable": compliance.is_orderable(item, pharmacy),
            "violations": compliance.check_catalog_item(item, pharmacy),
        })
    decorated.sort(key=lambda d: (0 if d["orderable"] else 1,
                                  _rank_key(pharmacies.get(d["pharmacy_id"]) or {}), d["price_sar"]))
    return {"total": len(decorated), "items": decorated[skip:skip + limit]}


@api.get("/pharmacy/catalog/{item_id}")
async def get_catalog_item(item_id: str, user=Depends(get_current_user)):
    item = await db.catalog_items.find_one({"item_id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Product not found")
    pharmacy = await db.pharmacies.find_one({"pharmacy_id": item["pharmacy_id"]}, {"_id": 0}) or {}
    return {**item, "pharmacy": _pharmacy_card(pharmacy) if pharmacy else None,
            "orderable": compliance.is_orderable(item, pharmacy),
            "violations": compliance.check_catalog_item(item, pharmacy)}


class CartItemIn(BaseModel):
    item_id: str
    qty: int = 1
    profile_id: Optional[str] = None


@api.get("/pharmacy/cart")
async def get_cart(profile_id: Optional[str] = None, user=Depends(get_current_user)):
    return await _hydrate_cart(await _cart_doc(user, profile_id))


@api.post("/pharmacy/cart/items")
async def add_cart_item(body: CartItemIn, user=Depends(get_current_user)):
    item = await db.catalog_items.find_one({"item_id": body.item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Product not found")
    pharmacy = await db.pharmacies.find_one({"pharmacy_id": item["pharmacy_id"]}, {"_id": 0}) or {}
    cart = await _cart_doc(user, body.profile_id)
    if cart.get("pharmacy_id") and cart["pharmacy_id"] != item["pharmacy_id"]:
        raise HTTPException(status_code=422, detail={"violations": [
            {"rule": "CART_SINGLE_PHARMACY", "item_id": body.item_id,
             "message": "A basket belongs to one partner pharmacy. Clear it before ordering from another."}]})
    already = next((l["qty"] for l in cart["items"] if l["item_id"] == body.item_id), 0)
    violations = compliance.check_add_to_cart(item, pharmacy, body.qty, qty_already_in_cart=already)
    if violations:
        raise HTTPException(status_code=422, detail={"violations": violations})
    lines = [l for l in cart["items"] if l["item_id"] != body.item_id]
    lines.append({"item_id": item["item_id"], "sku": item["sku"], "name_en": item["name_en"],
                  "name_ar": item["name_ar"], "qty": body.qty + already, "price_sar": item["price_sar"]})
    await db.carts.update_one({"cart_id": cart["cart_id"]},
                              {"$set": {"items": lines, "pharmacy_id": item["pharmacy_id"],
                                        "updated_at": iso()}})
    return await _hydrate_cart(await db.carts.find_one({"cart_id": cart["cart_id"]}, {"_id": 0}))


@api.delete("/pharmacy/cart/items/{item_id}")
async def remove_cart_item(item_id: str, profile_id: Optional[str] = None,
                           user=Depends(get_current_user)):
    cart = await _cart_doc(user, profile_id)
    lines = [l for l in cart["items"] if l["item_id"] != item_id]
    await db.carts.update_one({"cart_id": cart["cart_id"]},
                              {"$set": {"items": lines, "updated_at": iso(),
                                        "pharmacy_id": cart["pharmacy_id"] if lines else None}})
    return await _hydrate_cart(await db.carts.find_one({"cart_id": cart["cart_id"]}, {"_id": 0}))


@api.delete("/pharmacy/cart")
async def clear_cart(profile_id: Optional[str] = None, user=Depends(get_current_user)):
    cart = await _cart_doc(user, profile_id)
    await db.carts.update_one({"cart_id": cart["cart_id"]},
                              {"$set": {"items": [], "pharmacy_id": None, "prescription_id": None,
                                        "updated_at": iso()}})
    return await _hydrate_cart(await db.carts.find_one({"cart_id": cart["cart_id"]}, {"_id": 0}))


class CartPrescriptionIn(BaseModel):
    prescription_id: Optional[str] = None
    profile_id: Optional[str] = None


@api.post("/pharmacy/cart/prescription")
async def attach_cart_prescription(body: CartPrescriptionIn, user=Depends(get_current_user)):
    cart = await _cart_doc(user, body.profile_id)
    if body.prescription_id:
        rx = await db.prescriptions.find_one(
            {"prescription_id": body.prescription_id, "user_id": user["user_id"]}, {"_id": 0})
        if not rx:
            raise HTTPException(status_code=404, detail="Prescription not found")
    await db.carts.update_one({"cart_id": cart["cart_id"]},
                              {"$set": {"prescription_id": body.prescription_id, "updated_at": iso()}})
    return await _hydrate_cart(await db.carts.find_one({"cart_id": cart["cart_id"]}, {"_id": 0}))


@api.post("/pharmacy/prescriptions")
async def create_prescription(source: str = Form("upload"), encounter_id: Optional[str] = Form(None),
                              issued_date: Optional[str] = Form(None), profile_id: Optional[str] = Form(None),
                              file: Optional[UploadFile] = File(None), user=Depends(get_current_user)):
    if source not in ("upload", "encounter"):
        raise HTTPException(status_code=400, detail="source must be 'upload' or 'encounter'")
    storage_path = None
    content_type = None
    if source == "upload":
        if not file:
            raise HTTPException(status_code=400, detail="A prescription image or PDF is required")
        ext = (file.filename or "").rsplit(".", 1)[-1].lower()
        if ext not in RX_MIME:
            raise HTTPException(status_code=400, detail="Upload a JPG, PNG, WEBP, HEIC or PDF")
        data = await file.read()
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File is larger than 10 MB")
        content_type = RX_MIME[ext]
        try:
            result = put_object(f"{STORAGE_APP}/prescriptions/{user['user_id']}/{uuid.uuid4().hex}.{ext}",
                                data, content_type)
        except Exception:
            logging.getLogger(__name__).exception("Prescription upload failed")
            raise HTTPException(status_code=502, detail="Could not store the prescription. Try again.")
        storage_path = result["path"]
    else:
        enc = await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0}) if encounter_id else None
        if not enc or enc["patient_user_id"] != user["user_id"]:
            raise HTTPException(status_code=404, detail="Encounter not found")

    rx = {
        "prescription_id": f"rx_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "profile_id": profile_key(user, profile_id),
        "source": source,
        "encounter_id": encounter_id,
        "image_path": storage_path,
        "content_type": content_type,
        "issued_date": issued_date,
        "verification_status": "pending",
        "verified_by_pharmacy_id": None,
        "verified_at": None,
        "rejection_reason": None,
        "expires_at": iso(now_utc() + timedelta(days=PRESCRIPTION_VALID_DAYS)),
        "is_deleted": False,
        "created_at": iso(),
    }
    await db.prescriptions.insert_one(dict(rx))
    return rx


@api.get("/pharmacy/prescriptions")
async def list_prescriptions(profile_id: Optional[str] = None, user=Depends(get_current_user)):
    return await db.prescriptions.find(
        {"profile_id": profile_key(user, profile_id), "is_deleted": {"$ne": True},
         "status": {"$ne": "draft"}}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)


@api.get("/pharmacy/prescriptions/{prescription_id}/image")
async def get_prescription_image(prescription_id: str, user=Depends(get_current_user)):
    rx = await db.prescriptions.find_one(
        {"prescription_id": prescription_id, "user_id": user["user_id"]}, {"_id": 0})
    if not rx or not rx.get("image_path"):
        raise HTTPException(status_code=404, detail="Prescription image not found")
    data, content_type = get_object(rx["image_path"])
    return Response(content=data, media_type=rx.get("content_type") or content_type,
                    headers={"Cache-Control": "no-store"})


class CheckoutIn(BaseModel):
    profile_id: Optional[str] = None
    branch_id: Optional[str] = None
    note: Optional[str] = None


@api.post("/pharmacy/checkout")
async def checkout(body: CheckoutIn, user=Depends(get_current_user)):
    cart = await _cart_doc(user, body.profile_id)
    if not cart["items"]:
        raise HTTPException(status_code=422, detail={"violations": [
            {"rule": compliance.EMPTY_CART, "item_id": None, "message": "Your basket is empty."}]})
    pharmacy = await db.pharmacies.find_one({"pharmacy_id": cart["pharmacy_id"]}, {"_id": 0}) or {}
    entries = []
    for line in cart["items"]:
        item = await db.catalog_items.find_one({"item_id": line["item_id"]}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=422, detail={"violations": [
                {"rule": compliance.ITEM_UNAVAILABLE, "item_id": line["item_id"],
                 "message": f"{line['name_en']} is no longer listed."}]})
        entries.append({"item": item, "qty": line["qty"]})
    prescription = await db.prescriptions.find_one({"prescription_id": cart["prescription_id"]}, {"_id": 0}) \
        if cart.get("prescription_id") else None

    violations = compliance.check_checkout(entries, pharmacy, prescription)
    if violations:
        raise HTTPException(status_code=422, detail={"violations": violations})

    needs_pharmacist = any(e["item"].get("requires_prescription") for e in entries)
    mode = pharmacy.get("fulfilment_mode", "handoff")
    subtotal = round(sum(l["qty"] * l["price_sar"] for l in cart["items"]), 2)
    if mode == "handoff":
        status = "handed_off"
        note = "Basket handed off to the partner pharmacy. They dispense, verify and complete the sale."
    elif needs_pharmacist:
        status = "awaiting_pharmacist_verification"
        note = "Sent to the pharmacy. Their licensed pharmacist verifies the prescription before dispensing."
    else:
        status = "confirmed"
        note = "Sent to the pharmacy for preparation. Collect it at the branch."

    branch = next((b for b in (pharmacy.get("branches") or []) if b.get("branch_id") == body.branch_id),
                  (pharmacy.get("branches") or [{}])[0])
    order = {
        "order_id": f"ord_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "profile_id": cart["profile_id"],
        "pharmacy_id": pharmacy.get("pharmacy_id"),
        "pharmacy_snapshot": _pharmacy_card(pharmacy),
        "fulfilment_mode": mode,
        "items": [{"item_id": l["item_id"], "sku": l["sku"], "name_en": l["name_en"],
                   "name_ar": l["name_ar"], "qty": l["qty"], "price_sar": l["price_sar"]}
                  for l in cart["items"]],
        "prescription_id": cart.get("prescription_id"),
        "status": status,
        "status_history": [{"status": status, "at": iso(), "note": note}],
        "subtotal_sar": subtotal,
        "delivery_fee_sar": 0.0,
        "total_sar": subtotal,
        "delivery_address": None,
        "pickup_branch": {**branch, "directions_url": _directions_url(branch)} if branch else None,
        "handoff_url": _handoff_url(pharmacy, [l["sku"] for l in cart["items"]], body.branch_id)
        if mode == "handoff" else None,
        "note": body.note,
        "created_at": iso(),
        "updated_at": iso(),
    }
    await db.orders.insert_one(dict(order))
    await db.carts.update_one({"cart_id": cart["cart_id"]},
                              {"$set": {"items": [], "pharmacy_id": None, "prescription_id": None,
                                        "updated_at": iso()}})
    return order


@api.get("/pharmacy/orders")
async def list_orders(profile_id: Optional[str] = None, user=Depends(get_current_user)):
    return await db.orders.find({"profile_id": profile_key(user, profile_id)}, {"_id": 0}
                                ).sort("created_at", -1).to_list(50)


@api.get("/pharmacy/orders/{order_id}")
async def get_order(order_id: str, user=Depends(get_current_user)):
    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="This order belongs to another account")
    return order


CANCELLABLE = ("draft", "awaiting_pharmacist_verification", "confirmed")


@api.post("/pharmacy/orders/{order_id}/cancel")
async def cancel_order(order_id: str, user=Depends(get_current_user)):
    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="This order belongs to another account")
    if order["status"] not in CANCELLABLE:
        raise HTTPException(status_code=409,
                            detail=f"An order in '{order['status']}' can no longer be cancelled here")
    entry = {"status": "cancelled", "at": iso(), "note": "Cancelled by the patient"}
    await db.orders.update_one({"order_id": order_id},
                               {"$set": {"status": "cancelled", "updated_at": iso()},
                                "$push": {"status_history": entry}})
    return await db.orders.find_one({"order_id": order_id}, {"_id": 0})


@api.get("/pharmacy/refills")
async def get_refills(profile_id: Optional[str] = None, notify: bool = False,
                      user=Depends(get_current_user)):
    profile = profile_key(user, profile_id)
    refills = await refill_engine.compute_refills(db, profile)
    if notify:
        refills["alerts_raised"] = await refill_engine.raise_refill_alerts(
            db, user["user_id"], profile, refills)
    return refills



# ---------- Triage: how soon does this screening need a clinician? ----------
from agents.triage import TriageAgent
from triage import rules as triage_rules

TRIAGE_AGENT = TriageAgent()
CARE_GRANT_DAYS = 45


async def run_report_triage(report_id: str, invoked_by: str):
    """Never fails the caller — the screening report itself is already saved."""
    report = await db.health_reports.find_one({"report_id": report_id}, {"_id": 0})
    if not report:
        return None
    try:
        content, run_id = await run_agent(
            db, TRIAGE_AGENT,
            patient_user_id=report["user_id"],
            encounter_id=None,
            invoked_by=invoked_by,
            report=report,
            profile_id=report.get("profile_id") or report["user_id"],
        )
    except AgentRunFailed:
        return None
    await db.health_reports.update_one(
        {"report_id": report_id},
        {"$set": {"disposition": content, "disposition_agent_run_id": run_id, "disposition_at": iso()}},
    )
    await db.agent_runs.update_one(
        {"agent_run_id": run_id},
        {"$set": {"output_ref": {"collection": "health_reports", "id": report_id}}},
    )
    if content["level"] in ("emergency_now", "urgent_24h"):
        await db.alerts.insert_one({
            "alert_id": f"alert_{uuid.uuid4().hex[:12]}",
            "user_id": report["user_id"],
            "profile_id": report.get("profile_id") or report["user_id"],
            "type": "triage",
            "severity": "critical" if content["level"] == "emergency_now" else "warning",
            "message": content.get("headline") or triage_rules.TIMEFRAMES[content["level"]],
            "report_id": report_id,
            "read": False,
            "created_at": iso(),
        })
        doctor_id = (await db.users.find_one({"user_id": report["user_id"]},
                                             {"_id": 0, "assigned_doctor_user_id": 1}) or {}
                     ).get("assigned_doctor_user_id")
        patient_name = (await db.users.find_one({"user_id": report["user_id"]}, {"_id": 0, "name": 1}) or {}
                        ).get("name")
        if doctor_id:
            await db.alerts.insert_one({
                "alert_id": f"alert_{uuid.uuid4().hex[:12]}",
                "user_id": doctor_id,
                "profile_id": doctor_id,
                "type": "triage",
                "severity": "critical" if content["level"] == "emergency_now" else "warning",
                "message": f"{patient_name}: screening triaged as "
                           f"{triage_rules.TIMEFRAMES[content['level']].lower()}",
                "patient_user_id": report["user_id"],
                "report_id": report_id,
                "read": False,
                "created_at": iso(),
            })
    return content


@api.post("/reports/{report_id}/triage")
async def redo_report_triage(report_id: str, user=Depends(get_current_user)):
    report = await db.health_reports.find_one({"report_id": report_id, "user_id": user["user_id"]}, {"_id": 0})
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not report.get("findings"):
        await extract_report_findings(report, invoked_by=user["user_id"])
    content = await run_report_triage(report_id, invoked_by=user["user_id"])
    if content is None:
        raise HTTPException(status_code=502, detail="Could not triage this screening")
    return await db.health_reports.find_one({"report_id": report_id}, {"_id": 0})


# ---------- Booking: doctor availability and patient self-booking ----------
class AvailabilityBlock(BaseModel):
    weekday: int
    start: str
    end: str


class AvailabilityIn(BaseModel):
    slot_minutes: int = 30
    tz_offset_minutes: int = 180
    weekly: List[AvailabilityBlock] = []
    blocked_dates: List[str] = []


@api.get("/doctor/availability")
async def get_my_availability(user=Depends(require_doctor)):
    row = await db.doctor_availability.find_one({"doctor_user_id": user["user_id"]}, {"_id": 0})
    return row or {"doctor_user_id": user["user_id"], "slot_minutes": 30, "tz_offset_minutes": 180,
                   "weekly": [], "blocked_dates": []}


@api.put("/doctor/availability")
async def set_my_availability(body: AvailabilityIn, user=Depends(require_doctor)):
    for block in body.weekly:
        if not 0 <= block.weekday <= 6 or block.start >= block.end:
            raise HTTPException(status_code=400, detail="Each block needs a weekday 0-6 and start before end")
    if body.slot_minutes not in (15, 20, 30, 45, 60):
        raise HTTPException(status_code=400, detail="Slot length must be 15, 20, 30, 45 or 60 minutes")
    doc = {"doctor_user_id": user["user_id"], **body.model_dump(), "updated_at": iso()}
    await db.doctor_availability.update_one({"doctor_user_id": user["user_id"]}, {"$set": doc}, upsert=True)
    return await db.doctor_availability.find_one({"doctor_user_id": user["user_id"]}, {"_id": 0})


WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


async def _open_slots(doctor_user_id: str, days: int = 14):
    availability = await db.doctor_availability.find_one({"doctor_user_id": doctor_user_id}, {"_id": 0})
    if not availability or not availability.get("weekly"):
        return []
    slot_minutes = availability.get("slot_minutes") or 30
    offset = timedelta(minutes=availability.get("tz_offset_minutes", 180))
    blocked = set(availability.get("blocked_dates") or [])
    taken = {e["scheduled_at"][:16] for e in await db.encounters.find(
        {"doctor_user_id": doctor_user_id, "status": {"$in": ["scheduled", "in_progress"]}},
        {"_id": 0, "scheduled_at": 1}).to_list(1000) if e.get("scheduled_at")}

    now = now_utc()
    slots = []
    for offset_days in range(days):
        local_day = (now + offset).date() + timedelta(days=offset_days)
        date_str = local_day.isoformat()
        if date_str in blocked:
            continue
        for block in availability["weekly"]:
            if int(block["weekday"]) != local_day.weekday():
                continue
            cursor = datetime.fromisoformat(f"{date_str}T{block['start']}:00+00:00")
            block_end = datetime.fromisoformat(f"{date_str}T{block['end']}:00+00:00")
            while cursor + timedelta(minutes=slot_minutes) <= block_end:
                start_utc = cursor - offset
                if start_utc > now + timedelta(minutes=30) and iso(start_utc)[:16] not in taken:
                    slots.append({
                        "start": iso(start_utc),
                        "end": iso(start_utc + timedelta(minutes=slot_minutes)),
                        "date": date_str,
                        "local_time": cursor.strftime("%H:%M"),
                        "label": f"{WEEKDAY_NAMES[local_day.weekday()]} {local_day.strftime('%d %b')} · "
                                 f"{cursor.strftime('%H:%M')}",
                    })
                cursor += timedelta(minutes=slot_minutes)
    slots.sort(key=lambda s: s["start"])
    return slots


@api.get("/booking/doctors")
async def bookable_doctors(specialty: Optional[str] = None, city: Optional[str] = None,
                           account_id: Optional[str] = None, user=Depends(get_current_user)):
    """The patient's own doctor first, then anyone else who publishes slots."""
    query = {"role": "doctor", "email": {"$ne": ADMIN_EMAIL}}
    if account_id:
        query["account_id"] = account_id.upper()
    if specialty:
        query["specialty"] = {"$regex": re.escape(specialty), "$options": "i"}
    if city:
        query["city"] = {"$regex": re.escape(city), "$options": "i"}
    doctors = await db.users.find(query, {"_id": 0, "user_id": 1, "name": 1, "specialty": 1, "clinic": 1,
                                          "city": 1, "bio": 1, "clinic_phone": 1, "account_id": 1}).to_list(200)
    published = {a["doctor_user_id"] for a in await db.doctor_availability.find(
        {"weekly": {"$ne": []}}, {"_id": 0, "doctor_user_id": 1}).to_list(200)}
    mine = user.get("assigned_doctor_user_id")
    out = []
    for doctor in doctors:
        publishes = doctor["user_id"] in published
        if not publishes and doctor["user_id"] != mine:
            continue
        doctor["is_my_doctor"] = doctor["user_id"] == mine
        doctor["publishes_slots"] = publishes
        doctor["next_slots"] = (await _open_slots(doctor["user_id"], days=14))[:3] if publishes else []
        out.append(doctor)
    out.sort(key=lambda d: (not d["is_my_doctor"], not d["publishes_slots"], d["name"] or ""))
    return out


@api.get("/booking/slots")
async def open_slots(doctor_user_id: str, days: int = Query(14, le=60),
                     user=Depends(get_current_user)):
    doctor = await db.users.find_one({"user_id": doctor_user_id, "role": "doctor"}, USER_PROJECTION)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return {"doctor_user_id": doctor_user_id, "doctor_name": doctor.get("name"),
            "clinic_phone": doctor.get("clinic_phone"), "slots": await _open_slots(doctor_user_id, days)}


class BookingIn(BaseModel):
    doctor_user_id: str
    slot_start: str
    reason_for_visit: str = ""
    report_id: Optional[str] = None
    profile_id: Optional[str] = None
    share_record: bool = False


@api.post("/booking")
async def book_visit(body: BookingIn, user=Depends(get_current_user)):
    if user.get("role") == "doctor":
        raise HTTPException(status_code=403, detail="Clinicians create visits from their schedule")
    doctor = await db.users.find_one({"user_id": body.doctor_user_id, "role": "doctor"}, USER_PROJECTION)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    slots = await _open_slots(body.doctor_user_id, days=60)
    slot = next((s for s in slots if s["start"] == body.slot_start), None)
    if not slot:
        raise HTTPException(status_code=409, detail="That time is no longer available. Pick another slot.")

    triage_level = None
    report = None
    if body.report_id:
        report = await db.health_reports.find_one(
            {"report_id": body.report_id, "user_id": user["user_id"]}, {"_id": 0})
        if report:
            triage_level = (report.get("disposition") or {}).get("level")
    if triage_level == "emergency_now":
        raise HTTPException(status_code=409, detail=(
            f"This screening was triaged as needing emergency care now — an appointment is not safe. "
            f"Call {triage_rules.EMERGENCY_NUMBER} or go to the nearest emergency department."))

    encounter = {
        "encounter_id": f"enc_{uuid.uuid4().hex[:12]}",
        "patient_user_id": user["user_id"],
        "profile_id": profile_key(user, body.profile_id),
        "doctor_user_id": body.doctor_user_id,
        "scheduled_at": slot["start"],
        "slot_label": slot["label"],
        "started_at": None,
        "ended_at": None,
        "status": "scheduled",
        "reason_for_visit": body.reason_for_visit or (report or {}).get("disposition", {})
        .get("suggested_reason_for_visit", ""),
        "booked_by": "patient",
        "triage_level": triage_level,
        "screening_report_id": body.report_id,
        "record_shared": body.share_record or doctor["user_id"] == user.get("assigned_doctor_user_id"),
        "created_at": iso(),
        "updated_at": iso(),
    }
    await db.encounters.insert_one(dict(encounter))

    if body.share_record and doctor.get("account_id"):
        await _set_active_hospital(user, doctor["account_id"])
    if body.share_record and doctor["user_id"] != user.get("assigned_doctor_user_id"):
        await db.care_grants.insert_one({
            "grant_id": f"grant_{uuid.uuid4().hex[:12]}",
            "patient_user_id": user["user_id"],
            "doctor_user_id": doctor["user_id"],
            "encounter_id": encounter["encounter_id"],
            "reason": "Patient booked a visit with this clinician",
            "revoked": False,
            "expires_at": iso(now_utc() + timedelta(days=CARE_GRANT_DAYS)),
            "created_at": iso(),
        })
    if report and body.share_record:
        await db.health_reports.update_one(
            {"report_id": body.report_id},
            {"$set": {"shared_encounter_id": encounter["encounter_id"], "shared_at": iso()}})

    urgent = triage_level in ("emergency_now", "urgent_24h")
    await db.alerts.insert_one({
        "alert_id": f"alert_{uuid.uuid4().hex[:12]}",
        "user_id": doctor["user_id"],
        "profile_id": doctor["user_id"],
        "type": "appointment",
        "severity": "warning" if urgent else "info",
        "message": f"{user.get('name')} booked {slot['label']}"
                   + (f" — screening triaged as {triage_rules.TIMEFRAMES[triage_level].lower()}"
                      if urgent else ""),
        "patient_user_id": user["user_id"],
        "encounter_id": encounter["encounter_id"],
        "read": False,
        "created_at": iso(),
    })
    return {**encounter, "doctor_name": doctor.get("name"), "clinic": doctor.get("clinic"),
            "clinic_phone": doctor.get("clinic_phone")}


@api.post("/encounters/{encounter_id}/cancel")
async def cancel_visit(encounter_id: str, user=Depends(get_current_user)):
    enc = await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if not enc:
        raise HTTPException(status_code=404, detail="Visit not found")
    if user["user_id"] not in (enc["patient_user_id"], enc["doctor_user_id"]) and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="This visit belongs to someone else")
    if enc["status"] not in ("scheduled", "in_progress"):
        raise HTTPException(status_code=409, detail=f"A visit that is {enc['status']} cannot be cancelled")
    await db.encounters.update_one({"encounter_id": encounter_id},
                                   {"$set": {"status": "cancelled", "cancelled_by": user["user_id"],
                                             "updated_at": iso()}})
    other = enc["doctor_user_id"] if user["user_id"] == enc["patient_user_id"] else enc["patient_user_id"]
    await db.alerts.insert_one({
        "alert_id": f"alert_{uuid.uuid4().hex[:12]}",
        "user_id": other, "profile_id": other, "type": "appointment", "severity": "info",
        "message": f"{user.get('name')} cancelled the visit on "
                   f"{(enc.get('slot_label') or enc['scheduled_at'][:16])}",
        "encounter_id": encounter_id, "read": False, "created_at": iso(),
    })
    return await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0})


class RescheduleIn(BaseModel):
    slot_start: str


@api.post("/encounters/{encounter_id}/reschedule")
async def reschedule_visit(encounter_id: str, body: RescheduleIn, user=Depends(get_current_user)):
    """Moves a booked visit to another open time with the same clinician — no cancel-and-rebook."""
    enc = await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if not enc:
        raise HTTPException(status_code=404, detail="Visit not found")
    if user["user_id"] not in (enc["patient_user_id"], enc["doctor_user_id"]) and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="This visit belongs to someone else")
    if enc["status"] != "scheduled":
        raise HTTPException(status_code=409, detail=f"A visit that is {enc['status']} cannot be moved")
    slot = next((s for s in await _open_slots(enc["doctor_user_id"], days=60)
                 if s["start"] == body.slot_start), None)
    if not slot:
        raise HTTPException(status_code=409, detail="That time is no longer available. Pick another slot.")
    previous = enc.get("slot_label") or enc["scheduled_at"][:16]
    await db.encounters.update_one(
        {"encounter_id": encounter_id},
        {"$set": {"scheduled_at": slot["start"], "slot_label": slot["label"], "updated_at": iso(),
                  "rescheduled_by": user["user_id"], "rescheduled_at": iso()},
         "$push": {"reschedule_history": {"from": previous, "to": slot["label"], "at": iso(),
                                          "by": user["user_id"]}}})
    other = enc["doctor_user_id"] if user["user_id"] == enc["patient_user_id"] else enc["patient_user_id"]
    await db.alerts.insert_one({
        "alert_id": f"alert_{uuid.uuid4().hex[:12]}",
        "user_id": other, "profile_id": other, "type": "appointment", "severity": "info",
        "message": f"{user.get('name')} moved the visit from {previous} to {slot['label']}",
        "encounter_id": encounter_id, "read": False, "created_at": iso(),
    })
    return await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0})


@api.get("/my-visits")
async def my_visits(user=Depends(get_current_user)):
    """Upcoming and recent visits for the signed-in patient, with the clinician's details."""
    rows = await db.encounters.find({"patient_user_id": user["user_id"]}, {"_id": 0}
                                    ).sort("scheduled_at", -1).to_list(50)
    doctors = {d["user_id"]: d for d in await db.users.find(
        {"user_id": {"$in": list({r["doctor_user_id"] for r in rows})}},
        {"_id": 0, "user_id": 1, "name": 1, "specialty": 1, "clinic": 1, "city": 1, "clinic_phone": 1},
    ).to_list(100)} if rows else {}
    for row in rows:
        row["doctor"] = doctors.get(row["doctor_user_id"])
    upcoming = [r for r in rows if r["status"] in ("scheduled", "in_progress")
                and r["scheduled_at"] >= iso()]
    upcoming.sort(key=lambda r: r["scheduled_at"])
    return {"upcoming": upcoming, "past": [r for r in rows if r not in upcoming][:10]}
# ---------- Doctor-written prescriptions ----------




class RxItemIn(BaseModel):
    drug_name: str
    generic_name: str = ""
    form: str = ""
    strength: str = ""
    dose: str = ""
    frequency: str = ""
    duration_days: Optional[int] = None
    quantity: Optional[int] = None
    refills: int = 0
    instructions: str = ""


class PrescriptionIn(BaseModel):
    items: List[RxItemIn] = []
    diagnosis: str = ""
    notes: str = ""


async def _annotate_rx_items(items: List[dict]) -> List[dict]:
    """Flags controlled medicines so they can never be routed to an online basket."""
    catalog = await db.catalog_items.find({"active": True}, {"_id": 0}).to_list(1000)
    out = []
    for item in items:
        matches = refill_engine.find_matches(item.get("drug_name") or item.get("generic_name"),
                                            item.get("strength"), catalog, include_controlled=True)
        controlled = any(m[1].get("is_controlled") for m in matches)
        out.append({**item, "is_controlled": controlled, "dispense_in_clinic": controlled,
                    "catalog_match_count": len([m for m in matches if not m[1].get("is_controlled")])})
    return out


async def _load_rx_for_doctor(prescription_id: str, doctor):
    rx = await db.prescriptions.find_one({"prescription_id": prescription_id}, {"_id": 0})
    if not rx:
        raise HTTPException(status_code=404, detail="Prescription not found")
    if rx.get("issued_by_doctor_user_id") != doctor["user_id"] and not doctor.get("is_admin"):
        raise HTTPException(status_code=403, detail="This prescription was written by another clinician")
    return rx


@api.post("/encounters/{encounter_id}/prescription")
async def create_encounter_prescription(encounter_id: str, body: PrescriptionIn,
                                       user=Depends(require_doctor)):
    enc = await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if not enc or enc["doctor_user_id"] != user["user_id"]:
        raise HTTPException(status_code=404, detail="Encounter not found")
    await assert_doctor_can_access_patient(db, user, enc["patient_user_id"])
    if not body.items:
        raise HTTPException(status_code=400, detail="A prescription needs at least one medicine")
    existing = await db.prescriptions.find_one(
        {"encounter_id": encounter_id, "source": "encounter", "status": "draft"}, {"_id": 0})
    items = await _annotate_rx_items([i.model_dump() for i in body.items])
    if existing:
        await db.prescriptions.update_one(
            {"prescription_id": existing["prescription_id"]},
            {"$set": {"items": items, "diagnosis": body.diagnosis, "notes": body.notes, "updated_at": iso()}})
        return await db.prescriptions.find_one({"prescription_id": existing["prescription_id"]}, {"_id": 0})

    rx = {
        "prescription_id": f"rx_{uuid.uuid4().hex[:12]}",
        "user_id": enc["patient_user_id"],
        "profile_id": enc.get("profile_id") or enc["patient_user_id"],
        "source": "encounter",
        "encounter_id": encounter_id,
        "issued_by_doctor_user_id": user["user_id"],
        "issued_by_name": user.get("name"),
        "issued_by_clinic": user.get("clinic"),
        "items": items,
        "diagnosis": body.diagnosis,
        "notes": body.notes,
        "status": "draft",
        "image_path": None,
        "issued_date": None,
        "verification_status": "pending",
        "verified_by_pharmacy_id": None,
        "verified_at": None,
        "rejection_reason": None,
        "transmitted_to_pharmacy_id": None,
        "transmitted_at": None,
        "expires_at": iso(now_utc() + timedelta(days=PRESCRIPTION_VALID_DAYS)),
        "is_deleted": False,
        "created_at": iso(),
        "updated_at": iso(),
    }
    await db.prescriptions.insert_one(dict(rx))
    return rx


@api.patch("/prescriptions/{prescription_id}")
async def update_prescription(prescription_id: str, body: PrescriptionIn, user=Depends(require_doctor)):
    rx = await _load_rx_for_doctor(prescription_id, user)
    if rx["status"] != "draft":
        raise HTTPException(status_code=409, detail="A signed prescription cannot be edited")
    items = await _annotate_rx_items([i.model_dump() for i in body.items])
    await db.prescriptions.update_one(
        {"prescription_id": prescription_id},
        {"$set": {"items": items, "diagnosis": body.diagnosis, "notes": body.notes, "updated_at": iso()}})
    return await db.prescriptions.find_one({"prescription_id": prescription_id}, {"_id": 0})


@api.post("/prescriptions/{prescription_id}/sign")
async def sign_prescription(prescription_id: str, user=Depends(require_doctor)):
    rx = await _load_rx_for_doctor(prescription_id, user)
    if rx["status"] == "signed":
        raise HTTPException(status_code=409, detail="This prescription is already signed")
    if not rx.get("items"):
        raise HTTPException(status_code=400, detail="A prescription needs at least one medicine")
    await db.prescriptions.update_one(
        {"prescription_id": prescription_id},
        {"$set": {"status": "signed", "signed_at": iso(), "issued_date": iso(), "updated_at": iso()}})
    await db.alerts.insert_one({
        "alert_id": f"alert_{uuid.uuid4().hex[:12]}",
        "user_id": rx["user_id"], "profile_id": rx["profile_id"], "type": "prescription", "severity": "info",
        "message": f"{user.get('name')} sent you a prescription for {len(rx['items'])} medicine(s)",
        "prescription_id": prescription_id, "read": False, "created_at": iso(),
    })
    return await db.prescriptions.find_one({"prescription_id": prescription_id}, {"_id": 0})


class TransmitIn(BaseModel):
    pharmacy_id: str


@api.post("/prescriptions/{prescription_id}/transmit")
async def transmit_prescription(prescription_id: str, body: TransmitIn, user=Depends(require_doctor)):
    """Sends a signed prescription to a partner pharmacy. Their pharmacist still verifies before dispensing."""
    rx = await _load_rx_for_doctor(prescription_id, user)
    if rx["status"] != "signed":
        raise HTTPException(status_code=409, detail="Sign the prescription before sending it to a pharmacy")
    pharmacy = await db.pharmacies.find_one({"pharmacy_id": body.pharmacy_id, "active": True}, {"_id": 0})
    if not pharmacy:
        raise HTTPException(status_code=404, detail="Partner pharmacy not found")
    violations = compliance.check_pharmacy(pharmacy)
    if violations:
        raise HTTPException(status_code=422, detail={"violations": violations})

    catalog = await db.catalog_items.find(
        {"pharmacy_id": body.pharmacy_id, "active": True}, {"_id": 0}).to_list(1000)
    lines, unmatched = [], []
    for item in rx["items"]:
        if item.get("is_controlled"):
            unmatched.append({"drug_name": item["drug_name"],
                              "reason": "Controlled medicine — dispensed in clinic, never sent online"})
            continue
        matches = refill_engine.find_matches(item.get("drug_name") or item.get("generic_name"),
                                            item.get("strength"), catalog)
        if not matches:
            unmatched.append({"drug_name": item["drug_name"],
                              "reason": "This pharmacy does not list that medicine"})
            continue
        product = matches[0][1]
        lines.append({"item_id": product["item_id"], "sku": product["sku"], "name_en": product["name_en"],
                      "name_ar": product["name_ar"], "qty": 1, "price_sar": product["price_sar"]})

    order = None
    if lines and pharmacy.get("fulfilment_mode") == "in_app":
        subtotal = round(sum(l["price_sar"] for l in lines), 2)
        order = {
            "order_id": f"ord_{uuid.uuid4().hex[:12]}",
            "user_id": rx["user_id"], "profile_id": rx["profile_id"], "pharmacy_id": body.pharmacy_id,
            "pharmacy_snapshot": _pharmacy_card(pharmacy), "fulfilment_mode": "in_app",
            "items": lines, "prescription_id": prescription_id,
            "status": "awaiting_pharmacist_verification",
            "status_history": [{"status": "awaiting_pharmacist_verification", "at": iso(),
                                "note": f"Prescription sent by {user.get('name')}. The pharmacy's licensed "
                                        f"pharmacist verifies it before dispensing."}],
            "subtotal_sar": subtotal, "delivery_fee_sar": 0.0, "total_sar": subtotal,
            "delivery_address": None,
            "pickup_branch": (pharmacy.get("branches") or [{}])[0],
            "handoff_url": None, "note": None, "created_at": iso(), "updated_at": iso(),
        }
        await db.orders.insert_one(dict(order))

    await db.prescriptions.update_one(
        {"prescription_id": prescription_id},
        {"$set": {"transmitted_to_pharmacy_id": body.pharmacy_id, "transmitted_at": iso(),
                  "transmitted_pharmacy_name": pharmacy["name_en"],
                  "transmission_unmatched": unmatched, "updated_at": iso()}})
    await db.alerts.insert_one({
        "alert_id": f"alert_{uuid.uuid4().hex[:12]}",
        "user_id": rx["user_id"], "profile_id": rx["profile_id"], "type": "prescription", "severity": "info",
        "message": f"Your prescription was sent to {pharmacy['name_en']}",
        "prescription_id": prescription_id, "read": False, "created_at": iso(),
    })
    return {"prescription": await db.prescriptions.find_one({"prescription_id": prescription_id}, {"_id": 0}),
            "order": order, "unmatched": unmatched,
            "pharmacy": _pharmacy_card(pharmacy)}


@api.get("/prescriptions")
async def list_my_prescriptions(profile_id: Optional[str] = None, encounter_id: Optional[str] = None,
                                user=Depends(get_current_user)):
    if user.get("role") == "doctor" and encounter_id:
        enc = await db.encounters.find_one({"encounter_id": encounter_id}, {"_id": 0})
        if not enc or enc["doctor_user_id"] != user["user_id"]:
            raise HTTPException(status_code=404, detail="Encounter not found")
        return await db.prescriptions.find({"encounter_id": encounter_id}, {"_id": 0}
                                           ).sort("created_at", -1).to_list(20)
    return await db.prescriptions.find(
        {"profile_id": profile_key(user, profile_id), "source": "encounter", "status": "signed"}, {"_id": 0}
    ).sort("signed_at", -1).to_list(50)


@api.get("/prescriptions/{prescription_id}")
async def get_prescription(prescription_id: str, user=Depends(get_current_user)):
    rx = await db.prescriptions.find_one({"prescription_id": prescription_id}, {"_id": 0})
    if not rx:
        raise HTTPException(status_code=404, detail="Prescription not found")
    is_owner = rx["user_id"] == user["user_id"]
    is_author = rx.get("issued_by_doctor_user_id") == user["user_id"]
    if not (is_owner or is_author or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="This prescription belongs to another patient")
    if is_owner and rx["status"] == "draft":
        raise HTTPException(status_code=404, detail="Prescription not found")
    return rx


@api.get("/prescriptions/{prescription_id}/basket-options")
async def prescription_basket_options(prescription_id: str, user=Depends(get_current_user)):
    """What each prescribed medicine maps to in the catalog. The patient confirms every match."""
    rx = await db.prescriptions.find_one(
        {"prescription_id": prescription_id, "user_id": user["user_id"], "status": "signed"}, {"_id": 0})
    if not rx:
        raise HTTPException(status_code=404, detail="Prescription not found")
    catalog = await db.catalog_items.find({"active": True}, {"_id": 0}).to_list(1000)
    pharmacies = {p["pharmacy_id"]: p for p in await db.pharmacies.find({"active": True}, {"_id": 0}
                                                                       ).to_list(100)}
    proposals = []
    for item in rx["items"]:
        if item.get("is_controlled"):
            proposals.append({"drug_name": item["drug_name"], "strength": item.get("strength"),
                              "orderable": False, "offers": [],
                              "reason": "Controlled medicine — collect it at the clinic with the paper "
                                        "prescription. It can never be ordered online."})
            continue
        matches = [m[1] for m in refill_engine.find_matches(
            item.get("drug_name") or item.get("generic_name"), item.get("strength"), catalog)
            if m[0] >= 0.85 and m[1]["pharmacy_id"] in pharmacies]
        offers = [{"item": product, "pharmacy": _pharmacy_card(pharmacies[product["pharmacy_id"]]),
                   "sponsored": _is_sponsored(pharmacies[product["pharmacy_id"]])} for product in matches]
        offers.sort(key=lambda o: (_rank_key(pharmacies[o["item"]["pharmacy_id"]]), o["item"]["price_sar"]))
        proposals.append({"drug_name": item["drug_name"], "strength": item.get("strength"),
                          "orderable": bool(offers), "offers": offers,
                          "requires_user_confirmation": True,
                          "reason": None if offers else
                          "No partner pharmacy lists this medicine — search the pharmacy page instead."})
    return {"prescription_id": prescription_id, "proposals": proposals}


# ---------- Super admin: accounts, feature flags, white-label (staging) ----------
APP_ENV = os.environ["APP_ENV"].strip().lower()
IS_STAGING = APP_ENV == "staging"

FEATURE_FLAGS = [
    {"key": "health_chat", "label": "AI health chat & screening", "description": "Patients chat with the AI and get a screening report.", "default": True},
    {"key": "pill_id", "label": "Pill identification", "description": "Photograph a pill to identify it.", "default": True},
    {"key": "booking", "label": "Visit booking", "description": "Patients book published doctor slots.", "default": True},
    {"key": "prescriptions", "label": "Prescriptions", "description": "Doctors write and send prescriptions.", "default": True},
    {"key": "visit_summaries", "label": "Patient visit summaries", "description": "Doctor-reviewed plain-language visit notes.", "default": True},
    {"key": "pharmacy_marketplace", "label": "Pharmacy marketplace", "description": "Partner pharmacy discovery and refills.", "default": True},
    {"key": "live_transcript", "label": "Live Arabic transcript", "description": "Transcript lines appear while the doctor records.", "default": True},
    {"key": "white_label", "label": "White-label branding", "description": "Hospital logo, name, colours and web address. Staging only.", "default": False, "staging_only": True},
]
FLAG_KEYS = {f["key"] for f in FEATURE_FLAGS}
ACCOUNT_TYPES = ("hospital", "clinic", "pharmacy_group")
ACCOUNT_STATUSES = ("trial", "subscribed", "suspended")
ACCOUNT_ROLES = ("member", "account_admin")
HEX_COLOR = r"^#[0-9A-Fa-f]{6}$"
DOMAIN_RE = r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
ACCOUNT_PROJECTION = {"_id": 0}
IMPORT_COLUMNS = ["name", "email", "phone", "date_of_birth", "gender", "conditions", "allergies",
                  "medications", "last_visit", "notes"]
IMPORT_MAX_BYTES = 2 * 1024 * 1024
IMPORT_MAX_ROWS = 2000


def require_staging():
    if not IS_STAGING:
        raise HTTPException(status_code=403, detail="White-label setup is only available in the staging environment")


async def global_flags() -> dict:
    stored = {f["key"]: f["enabled"] for f in await db.feature_flags.find({}, {"_id": 0}).to_list(100)}
    return {f["key"]: stored.get(f["key"], f["default"]) for f in FEATURE_FLAGS}


async def effective_flags(account: Optional[dict]) -> dict:
    flags = await global_flags()
    if account:
        flags.update({k: v for k, v in (account.get("features") or {}).items() if k in FLAG_KEYS})
    if not IS_STAGING:
        flags["white_label"] = False
    return flags


async def get_account_or_404(account_id: str) -> dict:
    account = await db.accounts.find_one({"account_id": account_id.upper()}, ACCOUNT_PROJECTION)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


async def _active_tenant(account_id: str) -> Optional[dict]:
    if not IS_STAGING:
        return None
    account = await db.accounts.find_one({"account_id": account_id.upper(), "status": {"$ne": "suspended"}},
                                         ACCOUNT_PROJECTION)
    if account and (await effective_flags(account))["white_label"]:
        return account
    return None


async def new_account_id() -> str:
    while True:
        candidate = f"ACC-{secrets.token_hex(3).upper()}"
        if not await db.accounts.find_one({"account_id": candidate}, {"_id": 1}):
            return candidate


async def account_counts(account_ids: list) -> dict:
    rows = await db.users.aggregate([
        {"$match": {"account_id": {"$in": account_ids}}},
        {"$group": {"_id": {"a": "$account_id", "r": "$role"}, "n": {"$sum": 1}}},
    ]).to_list(1000)
    counts = {a: {"staff": 0, "customers": 0} for a in account_ids}
    for r in rows:
        counts[r["_id"]["a"]]["customers" if r["_id"]["r"] == "patient" else "staff"] += r["n"]
    return counts


def account_card(account: dict, counts: dict) -> dict:
    branding = account.get("branding") or {}
    return {**account, "staff_count": counts.get("staff", 0), "customer_count": counts.get("customers", 0),
            "user_count": counts.get("staff", 0) + counts.get("customers", 0),
            "logo_url": f"/api/tenant/{account['account_id']}/logo" if branding.get("logo_path") else None}


class AccountIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    type: str = Field(default="hospital", pattern="^(hospital|clinic|pharmacy_group)$")
    status: str = Field(default="trial", pattern="^(trial|subscribed|suspended)$")
    city: Optional[str] = Field(default=None, max_length=80)
    contact_email: Optional[str] = Field(default=None, max_length=254)


class AccountPatch(BaseModel):
    listed_in_app: Optional[bool] = None
    about: Optional[str] = Field(default=None, max_length=600)
    specialties: Optional[List[str]] = Field(default=None, max_length=20)
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    type: Optional[str] = Field(default=None, pattern="^(hospital|clinic|pharmacy_group)$")
    status: Optional[str] = Field(default=None, pattern="^(trial|subscribed|suspended)$")
    city: Optional[str] = Field(default=None, max_length=80)
    contact_email: Optional[str] = Field(default=None, max_length=254)
    features: Optional[dict] = None


class BrandingPatch(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=80)
    primary_color: Optional[str] = Field(default=None, pattern=HEX_COLOR)
    accent_color: Optional[str] = Field(default=None, pattern=HEX_COLOR)
    default_language: Optional[str] = Field(default=None, pattern="^(ar|en)$")
    custom_domain: Optional[str] = Field(default=None, max_length=253)


class AccountUserIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(default="patient", pattern="^(patient|doctor)$")
    account_role: str = Field(default="member", pattern="^(member|account_admin)$")


class AccountUserPatch(BaseModel):
    role: Optional[str] = Field(default=None, pattern="^(patient|doctor)$")
    account_role: Optional[str] = Field(default=None, pattern="^(member|account_admin)$")


class FlagPatch(BaseModel):
    enabled: bool


@api.get("/env")
async def environment():
    return {"env": APP_ENV, "is_staging": IS_STAGING}


@api.get("/flags")
async def my_flags(user=Depends(get_current_user)):
    account = await db.accounts.find_one({"account_id": user.get("account_id")}, ACCOUNT_PROJECTION) \
        if user.get("account_id") else None
    return await effective_flags(account)


@api.get("/tenant")
async def resolve_tenant(host: Optional[str] = None, account: Optional[str] = None):
    """Public branding lookup for white-label sites (staging only): by custom web address or account ID."""
    found = None
    if IS_STAGING and host:
        row = await db.accounts.find_one({"custom_domain": host.strip().lower()}, {"_id": 0, "account_id": 1})
        found = await _active_tenant(row["account_id"]) if row else None
    if IS_STAGING and not found and account:
        found = await _active_tenant(account)
    if not found:
        return {"tenant": None}
    branding = found.get("branding") or {}
    return {"tenant": {
        "account_id": found["account_id"],
        "name": branding.get("display_name") or found["name"],
        "primary_color": branding.get("primary_color"),
        "accent_color": branding.get("accent_color"),
        "default_language": found.get("default_language") or "en",
        "logo_url": f"/api/tenant/{found['account_id']}/logo" if branding.get("logo_path") else None,
        "features": await effective_flags(found),
    }}


@api.get("/tenant/{account_id}/logo")
async def tenant_logo(account_id: str):
    account = await get_account_or_404(account_id)
    path = (account.get("branding") or {}).get("logo_path")
    if not path:
        raise HTTPException(status_code=404, detail="No logo")
    data, content_type = await asyncio.to_thread(get_object, path)
    return Response(content=data, media_type=content_type, headers={"Cache-Control": "public, max-age=300"})


@api.get("/admin/accounts")
async def list_accounts(q: Optional[str] = None, type: Optional[str] = None, status: Optional[str] = None,
                        page: int = 1, limit: int = 25, admin=Depends(require_admin)):
    query = {}
    if q and q.strip():
        pattern = re.escape(q.strip())
        query["$or"] = [{"name": {"$regex": pattern, "$options": "i"}},
                        {"account_id": {"$regex": pattern, "$options": "i"}},
                        {"custom_domain": {"$regex": pattern, "$options": "i"}},
                        {"city": {"$regex": pattern, "$options": "i"}}]
    if type in ACCOUNT_TYPES:
        query["type"] = type
    if status in ACCOUNT_STATUSES:
        query["status"] = status
    limit = max(1, min(limit, 100))
    total = await db.accounts.count_documents(query)
    rows = await db.accounts.find(query, ACCOUNT_PROJECTION).sort("name", 1) \
        .skip((max(page, 1) - 1) * limit).limit(limit).to_list(limit)
    counts = await account_counts([a["account_id"] for a in rows])
    return {"total": total, "page": max(page, 1), "limit": limit,
            "items": [account_card(a, counts[a["account_id"]]) for a in rows]}


@api.get("/admin/accounts/export")
async def export_accounts(admin=Depends(require_admin)):
    rows = await db.accounts.find({}, ACCOUNT_PROJECTION).sort("name", 1).to_list(10000)
    counts = await account_counts([a["account_id"] for a in rows])
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["account_id", "name", "type", "status", "city", "staff", "customers", "custom_domain", "created_at"])
    for a in rows:
        c = counts[a["account_id"]]
        writer.writerow([a["account_id"], a["name"], a["type"], a["status"], a.get("city") or "", c["staff"],
                         c["customers"], a.get("custom_domain") or "", a["created_at"]])
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=sihha-accounts.csv"})


@api.post("/admin/accounts")
async def create_account(body: AccountIn, admin=Depends(require_admin)):
    account = {"account_id": await new_account_id(), "name": body.name.strip(), "type": body.type,
               "status": body.status, "city": body.city, "contact_email": body.contact_email,
               "branding": {}, "default_language": "ar", "custom_domain": None, "domain_verified": False,
               "features": {}, "created_by": admin["user_id"], "created_at": iso()}
    await db.accounts.insert_one(account)
    return account_card(await get_account_or_404(account["account_id"]), {})


@api.get("/admin/accounts/{account_id}")
async def get_account(account_id: str, admin=Depends(require_admin)):
    account = await get_account_or_404(account_id)
    counts = await account_counts([account["account_id"]])
    return {**account_card(account, counts[account["account_id"]]), "effective_flags": await effective_flags(account)}


@api.patch("/admin/accounts/{account_id}")
async def update_account(account_id: str, body: AccountPatch, admin=Depends(require_admin)):
    account = await get_account_or_404(account_id)
    update = body.model_dump(exclude_none=True)
    if "features" in update:
        update["features"] = {k: bool(v) for k, v in update["features"].items() if k in FLAG_KEYS}
    if update:
        update["updated_at"] = iso()
        await db.accounts.update_one({"account_id": account["account_id"]}, {"$set": update})
        _flag_cache.pop(account["account_id"], None)
    return await get_account(account["account_id"], admin)


@api.patch("/admin/accounts/{account_id}/branding")
async def update_branding(account_id: str, body: BrandingPatch, admin=Depends(require_admin)):
    require_staging()
    account = await get_account_or_404(account_id)
    data = body.model_dump(exclude_unset=True)
    update = {f"branding.{k}": v for k, v in data.items() if k in ("display_name", "primary_color", "accent_color")}
    if "default_language" in data and data["default_language"]:
        update.update(default_language=data["default_language"], language_confirmed=True)
    if "custom_domain" in data:
        domain = (data["custom_domain"] or "").strip().lower() or None
        if domain and not re.match(DOMAIN_RE, domain):
            raise HTTPException(status_code=422, detail="Enter a web address like care.yourhospital.sa")
        if domain and await db.accounts.find_one({"custom_domain": domain, "account_id": {"$ne": account["account_id"]}}):
            raise HTTPException(status_code=409, detail="That web address is already used by another account")
        if domain != account.get("custom_domain"):
            update.update(custom_domain=domain, domain_verified=False)
    if update:
        update["updated_at"] = iso()
        await db.accounts.update_one({"account_id": account["account_id"]}, {"$set": update})
    return await get_account(account["account_id"], admin)


@api.post("/admin/accounts/{account_id}/logo")
async def upload_account_logo(account_id: str, file: UploadFile = File(...), admin=Depends(require_admin)):
    require_staging()
    account = await get_account_or_404(account_id)
    if file.content_type not in ("image/png", "image/jpeg", "image/webp", "image/svg+xml"):
        raise HTTPException(status_code=415, detail="Upload a PNG, JPG, WEBP or SVG logo")
    data = await file.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Logo must be under 2 MB")
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/svg+xml": "svg"}[file.content_type]
    result = await asyncio.to_thread(put_object, f"{STORAGE_APP}/branding/{account['account_id']}/{uuid.uuid4().hex}.{ext}",
                                     data, file.content_type)
    await db.accounts.update_one({"account_id": account["account_id"]},
                                 {"$set": {"branding.logo_path": result["path"], "updated_at": iso()}})
    return await get_account(account["account_id"], admin)


@api.post("/admin/accounts/{account_id}/domain/verify")
async def verify_account_domain(account_id: str, request: Request, admin=Depends(require_admin)):
    require_staging()
    account = await get_account_or_404(account_id)
    domain = account.get("custom_domain")
    if not domain:
        raise HTTPException(status_code=400, detail="Add a web address first")
    app_host = urlparse(_app_origin(request)).hostname

    def addresses(host):
        try:
            return {a[4][0] for a in socket.getaddrinfo(host, 443)}
        except OSError:
            return set()
    domain_ips, app_ips = await asyncio.to_thread(addresses, domain), await asyncio.to_thread(addresses, app_host)
    verified = bool(domain_ips & app_ips)
    await db.accounts.update_one({"account_id": account["account_id"]}, {"$set": {"domain_verified": verified}})
    return {"verified": verified, "domain": domain, "points_to": app_host, "resolves": bool(domain_ips)}


async def _account_users(account_id: str, kind: Optional[str], q: Optional[str], limit: int) -> dict:
    query = {"account_id": account_id}
    if kind == "staff":
        query["role"] = {"$ne": "patient"}
    elif kind == "customers":
        query["role"] = "patient"
    if q and q.strip():
        pattern = re.escape(q.strip())
        query["$or"] = [{"name": {"$regex": pattern, "$options": "i"}}, {"email": {"$regex": pattern, "$options": "i"}}]
    total = await db.users.count_documents(query)
    users = await db.users.find(query, {"_id": 0, "user_id": 1, "name": 1, "email": 1, "role": 1, "account_role": 1,
                                        "created_at": 1, "imported": 1, "invited_at": 1, "password_hash": 1}) \
        .sort("name", 1).limit(max(1, min(limit, 200))).to_list(200)
    records = {r["user_id"]: r for r in await db.imported_records.find(
        {"account_id": account_id, "user_id": {"$in": [u["user_id"] for u in users]}}, {"_id": 0}).to_list(200)}
    items = []
    for u in users:
        has_password = bool(u.pop("password_hash", None))
        items.append({**u, "account_role": u.get("account_role") or "member",
                      "status": "active" if has_password else "invited",
                      "history": records.get(u["user_id"])})
    return {"total": total, "items": items}


async def _account_overview(account: dict) -> dict:
    aid = account["account_id"]
    counts = (await account_counts([aid]))[aid]
    staff_ids = [u["user_id"] for u in await db.users.find(
        {"account_id": aid, "role": {"$ne": "patient"}}, {"_id": 0, "user_id": 1}).to_list(5000)]
    customer_ids = [u["user_id"] for u in await db.users.find(
        {"account_id": aid, "role": "patient"}, {"_id": 0, "user_id": 1}).to_list(50000)]
    since = iso(now_utc() - timedelta(days=30))
    branding = account.get("branding") or {}
    (imported, doctor_count, admin_count, new_customers, visits, visits_30d, prescriptions, screenings,
     recent_staff, recent_customers) = await asyncio.gather(
        db.imported_records.count_documents({"account_id": aid}),
        db.users.count_documents({"account_id": aid, "role": "doctor"}),
        db.users.count_documents({"account_id": aid, "account_role": "account_admin"}),
        db.users.count_documents({"account_id": aid, "role": "patient", "created_at": {"$gte": since}}),
        db.encounters.count_documents({"doctor_user_id": {"$in": staff_ids}}),
        db.encounters.count_documents({"doctor_user_id": {"$in": staff_ids}, "created_at": {"$gte": since}}),
        db.prescriptions.count_documents({"profile_id": {"$in": customer_ids}}),
        db.health_reports.count_documents({"user_id": {"$in": customer_ids}}),
        _account_users(aid, "staff", None, 5),
        db.users.find({"account_id": aid, "role": "patient"}, {"_id": 0, "user_id": 1, "name": 1, "email": 1, "created_at": 1})
        .sort("created_at", -1).limit(5).to_list(5),
    )
    checklist = [
        {"key": "created", "label": "Account created with a unique ID", "done": True},
        {"key": "branding", "label": "Brand name and colours set", "done": bool(branding.get("display_name") and branding.get("primary_color"))},
        {"key": "logo", "label": "Logo uploaded", "done": bool(branding.get("logo_path"))},
        {"key": "language", "label": "Default language confirmed", "done": bool(account.get("language_confirmed"))},
        {"key": "features", "label": "Features chosen for this hospital", "done": bool(account.get("features"))},
        {"key": "staff", "label": "First staff member invited", "done": counts["staff"] > 0},
        {"key": "import", "label": "Existing patient data imported (optional)", "done": imported > 0, "optional": True},
        {"key": "domain", "label": "Own web address connected", "done": bool(account.get("domain_verified"))},
    ]
    return {
        "account": account_card(account, counts),
        "staff_count": counts["staff"], "customer_count": counts["customers"],
        "doctor_count": doctor_count, "account_admin_count": admin_count,
        "new_customers_30d": new_customers, "imported_records": imported,
        "visits": visits, "visits_30d": visits_30d, "prescriptions": prescriptions, "screenings": screenings,
        "recent_staff": recent_staff["items"], "recent_customers": recent_customers,
        "checklist": checklist,
        "checklist_done": sum(1 for c in checklist if c["done"]),
    }


@api.get("/admin/accounts/{account_id}/overview")
async def admin_account_overview(account_id: str, admin=Depends(require_admin)):
    return await _account_overview(await get_account_or_404(account_id))


@api.get("/admin/accounts/{account_id}/users")
async def admin_account_users(account_id: str, kind: Optional[str] = None, q: Optional[str] = None,
                              limit: int = 100, admin=Depends(require_admin)):
    account = await get_account_or_404(account_id)
    return await _account_users(account["account_id"], kind, q, limit)


@api.post("/admin/accounts/{account_id}/users")
async def invite_account_user(account_id: str, body: AccountUserIn, request: Request, admin=Depends(require_admin)):
    account = await get_account_or_404(account_id)
    email = body.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=422, detail="Enter a valid email address")
    existing = await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1, "account_id": 1, "role": 1})
    if existing and existing.get("account_id") and existing["account_id"] != account["account_id"]:
        raise HTTPException(status_code=409, detail=f"This person already belongs to account {existing['account_id']}")
    if existing and existing.get("role") != body.role:
        raise HTTPException(status_code=409, detail=(
            "This person already has a patient account. Approve clinician access in Doctor assignments first."
            if body.role == "doctor" else "This person is a staff member — add them from the Staff tab."))
    fields = {"account_id": account["account_id"], "role": body.role, "account_role": body.account_role}
    if existing:
        await db.users.update_one({"user_id": existing["user_id"]},
                                  {"$set": {"account_id": account["account_id"], "account_role": body.account_role}})
        return {"user_id": existing["user_id"], "invited": False, "linked": True}
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    await db.users.insert_one({"user_id": user_id, "email": email, "name": body.name.strip(), "picture": None,
                               "clinician_requested": False, "sharing_enabled": True, "assigned_doctor_user_id": None,
                               "onboarding_completed": False, "invited_at": iso(), "invited_by": admin["user_id"],
                               "created_at": iso(), **fields})
    token = await _issue_password_token(user_id, email, 7 * 24 * 60)
    subject, html = account_invite_email(body.name.strip(), (account.get("branding") or {}).get("display_name") or account["name"],
                                         f"{_app_origin(request)}/auth/reset?token={token}")
    _send_in_background(user_id, email, subject, html)
    return {"user_id": user_id, "invited": True, "linked": False}


@api.patch("/admin/accounts/{account_id}/users/{user_id}")
async def update_account_user(account_id: str, user_id: str, body: AccountUserPatch, admin=Depends(require_admin)):
    account = await get_account_or_404(account_id)
    update = body.model_dump(exclude_none=True)
    result = await db.users.update_one({"user_id": user_id, "account_id": account["account_id"]}, {"$set": update}) \
        if update else None
    if result is not None and result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found in this account")
    return {"ok": True}


@api.delete("/admin/accounts/{account_id}/users/{user_id}")
async def remove_account_user(account_id: str, user_id: str, admin=Depends(require_admin)):
    account = await get_account_or_404(account_id)
    result = await db.users.update_one({"user_id": user_id, "account_id": account["account_id"]},
                                       {"$set": {"account_id": None, "account_role": None}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found in this account")
    return {"ok": True}


def _split_list(value: str) -> list:
    return [v.strip() for v in re.split(r"[;|]", value or "") if v.strip()][:50]


@api.post("/admin/accounts/{account_id}/import")
async def import_customers(account_id: str, file: UploadFile = File(...), admin=Depends(require_admin)):
    """CSV import of a hospital's existing patients and their history. Imported patients get no password until invited."""
    require_staging()
    account = await get_account_or_404(account_id)
    raw = await file.read(IMPORT_MAX_BYTES + 1)
    if len(raw) > IMPORT_MAX_BYTES:
        raise HTTPException(status_code=413, detail="CSV must be under 2 MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="Save the file as UTF-8 CSV and try again")
    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    if "name" not in headers or "email" not in headers:
        raise HTTPException(status_code=422, detail="The CSV needs at least 'name' and 'email' columns")
    created = linked = 0
    errors = []
    for index, row in enumerate(reader, start=2):
        if index - 1 > IMPORT_MAX_ROWS:
            errors.append({"row": index, "reason": f"Stopped after {IMPORT_MAX_ROWS} rows"})
            break
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        name, email = row.get("name", ""), row.get("email", "").lower()
        if not name or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            errors.append({"row": index, "reason": "Missing name or valid email"})
            continue
        existing = await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1, "account_id": 1, "role": 1})
        if existing and existing.get("account_id") not in (None, account["account_id"]):
            errors.append({"row": index, "reason": f"{email} belongs to another account"})
            continue
        if existing and existing.get("role") != "patient":
            errors.append({"row": index, "reason": f"{email} is a staff account"})
            continue
        if existing:
            user_id = existing["user_id"]
            await db.users.update_one({"user_id": user_id}, {"$set": {"account_id": account["account_id"]}})
            linked += 1
        else:
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            await db.users.insert_one({"user_id": user_id, "email": email, "name": name, "picture": None,
                                       "role": "patient", "account_id": account["account_id"], "account_role": "member",
                                       "clinician_requested": False, "sharing_enabled": True,
                                       "assigned_doctor_user_id": None, "onboarding_completed": False,
                                       "imported": True, "created_at": iso()})
            created += 1
        await db.imported_records.update_one(
            {"account_id": account["account_id"], "user_id": user_id},
            {"$set": {"phone": row.get("phone") or None, "date_of_birth": row.get("date_of_birth") or None,
                      "gender": row.get("gender") or None, "conditions": _split_list(row.get("conditions")),
                      "allergies": _split_list(row.get("allergies")), "medications": _split_list(row.get("medications")),
                      "last_visit": row.get("last_visit") or None, "notes": (row.get("notes") or "")[:2000] or None,
                      "imported_at": iso(), "imported_by": admin["user_id"]},
             "$setOnInsert": {"record_id": f"imp_{uuid.uuid4().hex[:12]}"}},
            upsert=True)
    return {"created": created, "linked": linked, "errors": errors[:100], "error_count": len(errors)}


@api.get("/admin/search")
async def admin_quick_search(q: str, admin=Depends(require_admin)):
    pattern = re.escape(q.strip())
    if not pattern:
        return {"accounts": [], "users": []}
    accounts = await db.accounts.find({"$or": [{"name": {"$regex": pattern, "$options": "i"}},
                                               {"account_id": {"$regex": pattern, "$options": "i"}},
                                               {"custom_domain": {"$regex": pattern, "$options": "i"}}]},
                                      {"_id": 0, "account_id": 1, "name": 1, "type": 1, "status": 1}).limit(8).to_list(8)
    users = await db.users.find({"$or": [{"name": {"$regex": pattern, "$options": "i"}},
                                         {"email": {"$regex": pattern, "$options": "i"}}]},
                                {"_id": 0, "user_id": 1, "name": 1, "email": 1, "role": 1, "account_id": 1}).limit(8).to_list(8)
    return {"accounts": accounts, "users": users}


@api.get("/admin/flags")
async def admin_flags(admin=Depends(require_admin)):
    current = await global_flags()
    overrides = await db.accounts.find({"features": {"$ne": {}}}, {"_id": 0, "account_id": 1, "name": 1, "features": 1}).to_list(1000)
    return {"is_staging": IS_STAGING, "flags": [
        {**f, "enabled": current[f["key"]] and (IS_STAGING or not f.get("staging_only")),
         "overrides": [{"account_id": a["account_id"], "name": a["name"], "enabled": a["features"][f["key"]]}
                       for a in overrides if f["key"] in (a.get("features") or {})]}
        for f in FEATURE_FLAGS]}


@api.put("/admin/flags/{key}")
async def set_flag(key: str, body: FlagPatch, admin=Depends(require_admin)):
    if key not in FLAG_KEYS:
        raise HTTPException(status_code=404, detail="Unknown feature")
    await db.feature_flags.update_one({"key": key}, {"$set": {"key": key, "enabled": body.enabled,
                                                              "updated_by": admin["user_id"], "updated_at": iso()}},
                                      upsert=True)
    _flag_cache.clear()
    return await admin_flags(admin)


async def require_account_admin(user=Depends(get_current_user)):
    if user.get("account_role") != "account_admin" or not user.get("account_id"):
        raise HTTPException(status_code=403, detail="Hospital admin access required")
    return user


@api.get("/account/overview")
async def my_account_overview(user=Depends(require_account_admin)):
    return await _account_overview(await get_account_or_404(user["account_id"]))


@api.get("/account/users")
async def my_account_users(kind: Optional[str] = None, q: Optional[str] = None, user=Depends(require_account_admin)):
    return await _account_users(user["account_id"], kind, q, 200)


class DemoRequestIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    organization: str = Field(min_length=2, max_length=160)
    role: Optional[str] = Field(default=None, max_length=80)
    message: Optional[str] = Field(default=None, max_length=1000)


@api.post("/demo-requests")
async def create_demo_request(body: DemoRequestIn, request: Request):
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", body.email.strip()):
        raise HTTPException(status_code=422, detail="Enter a valid work email")
    ip = client_ip(request)
    if await db.demo_requests.count_documents({"ip": ip, "created_at": {"$gte": iso(now_utc() - timedelta(hours=1))}}) >= 5:
        raise HTTPException(status_code=429, detail="Thanks — we already have your request.")
    await db.demo_requests.insert_one({"request_id": f"demo_{uuid.uuid4().hex[:12]}", **body.model_dump(),
                                       "email": body.email.strip().lower(), "ip": ip, "status": "new", "notes": "",
                                       "created_at": iso()})
    settings = await db.app_settings.find_one({"key": "demo_alert_email"}, {"_id": 0})
    if settings and settings.get("value"):
        subject, html = demo_alert_email(body.model_dump(), f"{_app_origin(request)}/admin/demo-requests")
        _send_in_background("demo_alert", settings["value"], subject, html)
    return {"ok": True}


DEMO_STATUSES = ("new", "contacted", "demo_booked", "won", "lost")


class DemoRequestPatch(BaseModel):
    status: Optional[str] = Field(default=None, pattern="^(new|contacted|demo_booked|won|lost)$")
    notes: Optional[str] = Field(default=None, max_length=4000)


class AlertEmailIn(BaseModel):
    email: Optional[str] = Field(default=None, max_length=254)


@api.patch("/admin/demo-requests/{request_id}")
async def update_demo_request(request_id: str, body: DemoRequestPatch, admin=Depends(require_admin)):
    update = body.model_dump(exclude_none=True)
    result = await db.demo_requests.update_one({"request_id": request_id},
                                               {"$set": {**update, "updated_at": iso(), "updated_by": admin["user_id"]}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Request not found")
    return await db.demo_requests.find_one({"request_id": request_id}, {"_id": 0, "ip": 0})


@api.get("/admin/settings/demo-alert")
async def get_demo_alert(admin=Depends(require_admin)):
    row = await db.app_settings.find_one({"key": "demo_alert_email"}, {"_id": 0})
    return {"email": (row or {}).get("value")}


@api.put("/admin/settings/demo-alert")
async def set_demo_alert(body: AlertEmailIn, admin=Depends(require_admin)):
    email = (body.email or "").strip().lower() or None
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=422, detail="Enter a valid email address")
    await db.app_settings.update_one({"key": "demo_alert_email"}, {"$set": {"key": "demo_alert_email", "value": email}}, upsert=True)
    return {"email": email}


def _report_period(month: Optional[str]):
    if month:
        if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", month):
            raise HTTPException(status_code=422, detail="Use a month like 2026-05")
        start = datetime(int(month[:4]), int(month[5:]), 1, tzinfo=timezone.utc)
    else:
        first = now_utc().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start = (first - timedelta(days=1)).replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)
    return start, end


async def _usage_report(account: dict, month: Optional[str]) -> dict:
    start, end = _report_period(month)
    window = {"$gte": iso(start), "$lt": iso(end)}
    aid = account["account_id"]
    staff = await db.users.find({"account_id": aid, "role": {"$ne": "patient"}}, {"_id": 0, "user_id": 1, "name": 1}).to_list(5000)
    customer_ids = [u["user_id"] for u in await db.users.find({"account_id": aid, "role": "patient"}, {"_id": 0, "user_id": 1}).to_list(50000)]
    staff_ids = [s["user_id"] for s in staff]
    visits, new_customers, screenings, prescriptions, visits_by_doc, rx_by_doc = await asyncio.gather(
        db.encounters.count_documents({"doctor_user_id": {"$in": staff_ids}, "created_at": window}),
        db.users.count_documents({"account_id": aid, "role": "patient", "created_at": window}),
        db.health_reports.count_documents({"user_id": {"$in": customer_ids}, "generated_at": window}),
        db.prescriptions.count_documents({"issued_by_doctor_user_id": {"$in": staff_ids}, "created_at": window}),
        db.encounters.aggregate([{"$match": {"doctor_user_id": {"$in": staff_ids}, "created_at": window}},
                                 {"$group": {"_id": "$doctor_user_id", "n": {"$sum": 1}}}]).to_list(5000),
        db.prescriptions.aggregate([{"$match": {"issued_by_doctor_user_id": {"$in": staff_ids}, "created_at": window}},
                                    {"$group": {"_id": "$issued_by_doctor_user_id", "n": {"$sum": 1}}}]).to_list(5000),
    )
    v = {r["_id"]: r["n"] for r in visits_by_doc}
    p = {r["_id"]: r["n"] for r in rx_by_doc}
    flags = await effective_flags(account)
    labels = {f["key"]: f["label"] for f in FEATURE_FLAGS}
    return {
        "account_id": aid, "account_name": (account.get("branding") or {}).get("display_name") or account["name"],
        "primary_color": (account.get("branding") or {}).get("primary_color"),
        "period_label": start.strftime("%B %Y"), "month": start.strftime("%Y-%m"),
        "generated_at": now_utc().strftime("%d %b %Y %H:%M UTC"),
        "kpis": [
            {"label": "Visits", "value": visits, "sub": "consultations this month"},
            {"label": "New customers", "value": new_customers, "sub": f"{len(customer_ids)} in total"},
            {"label": "AI screenings", "value": screenings},
            {"label": "Prescriptions", "value": prescriptions},
            {"label": "Staff", "value": len(staff)},
            {"label": "Modules on", "value": sum(1 for k in flags if flags[k] and k != "white_label")},
        ],
        "tables": [
            ("Activity by doctor", ["Doctor", "Visits", "Prescriptions"],
             sorted([[s["name"], v.get(s["user_id"], 0), p.get(s["user_id"], 0)] for s in staff], key=lambda r: -r[1])),
            ("Modules", ["Module", "Status"], [[labels[k], "On" if flags[k] else "Off"] for k in labels if k != "white_label"]),
        ],
    }


def _pdf_response(report: dict) -> Response:
    pdf = render_usage_report(report)
    filename = f"{report['account_id']}-usage-{report['month']}.pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@api.get("/admin/accounts/{account_id}/report")
async def admin_usage_report(account_id: str, month: Optional[str] = None, admin=Depends(require_admin)):
    return _pdf_response(await _usage_report(await get_account_or_404(account_id), month))


@api.get("/account/report")
async def my_usage_report(month: Optional[str] = None, user=Depends(require_account_admin)):
    return _pdf_response(await _usage_report(await get_account_or_404(user["account_id"]), month))


def _verify_cron(request: Request):
    header = request.headers.get("authorization", "")
    token = header[7:] if header.startswith("Bearer ") else ""
    if not token or not secrets.compare_digest(token, os.environ["WEBHOOK_CRON_SECRET"]):
        raise HTTPException(status_code=401, detail="Unauthorized")


async def _claim_cron_run(request: Request, name: str) -> bool:
    raw = await request.body()
    try:
        body = json.loads(raw) if raw.strip() else {}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid body")
    run_id = request.headers.get("x-webhook-id") or (body or {}).get("run_id") or f"{name}:{uuid.uuid4().hex}"
    result = await db.cron_runs.update_one({"run_id": run_id}, {"$setOnInsert": {"run_id": run_id, "name": name, "at": iso()}}, upsert=True)
    return result.upserted_id is not None


def _in_background(coro):
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def send_monthly_reports():
    origin = next(o for o in CORS_ORIGINS if o.startswith("https://"))
    month = _report_period(None)[0].strftime("%Y-%m")
    period = _report_period(None)[0].strftime("%B %Y")
    for account in await db.accounts.find({"status": {"$ne": "suspended"}, "last_report_sent": {"$ne": month}},
                                          ACCOUNT_PROJECTION).to_list(10000):
        name = (account.get("branding") or {}).get("display_name") or account["name"]
        admins = await db.users.find({"account_id": account["account_id"], "account_role": "account_admin",
                                      "password_hash": {"$exists": True}}, {"_id": 0, "user_id": 1, "name": 1, "email": 1}).to_list(50)
        sent = 0
        for a in admins:
            subject, html = usage_report_email(a["name"], name, period, f"{origin}/my-hospital?report={month}")
            sent += await _deliver_reset_email(a["user_id"], a["email"], subject, html, kind="usage report")
        if sent:
            await db.accounts.update_one({"account_id": account["account_id"]}, {"$set": {"last_report_sent": month}})


@api.post("/cron/monthly-reports")
async def cron_monthly_reports(request: Request):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    _verify_cron(request)
    if await _claim_cron_run(request, "monthly-reports"):
        _in_background(send_monthly_reports())
    return {"accepted": True}


@api.post("/cron/audio-purge")
async def cron_audio_purge(request: Request):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    _verify_cron(request)
    if await _claim_cron_run(request, "audio-purge"):
        _in_background(purge_expired_audio())
    return {"accepted": True}


@api.get("/admin/demo-requests")
async def list_demo_requests(admin=Depends(require_admin)):
    return await db.demo_requests.find({}, {"_id": 0, "ip": 0}).sort("created_at", -1).to_list(200)


DEMO_ACCOUNTS = [
    {"name": "Al Noor Specialist Hospital", "type": "hospital", "status": "subscribed", "city": "Riyadh",
     "branding": {"display_name": "Al Noor Care", "primary_color": "#0F4C5C", "accent_color": "#E3B23C"},
     "members": [("dr.layla@sihha.ai", "account_admin"), ("omar.patient@sihha.ai", "member"), ("noura.patient@sihha.ai", "member")]},
    {"name": "Jeddah Family Clinics", "type": "clinic", "status": "trial", "city": "Jeddah", "branding": {}, "members": []},
    {"name": "Eastern Health Group", "type": "hospital", "status": "subscribed", "city": "Dammam", "branding": {}, "members": []},
]


async def seed_demo_accounts():
    """Staging-only sample hospital accounts so the super admin console has something to show."""
    if await db.accounts.count_documents({}) > 0:
        return
    for demo in DEMO_ACCOUNTS:
        account_id = await new_account_id()
        await db.accounts.insert_one({"account_id": account_id, "name": demo["name"], "type": demo["type"],
                                      "status": demo["status"], "city": demo["city"], "contact_email": None,
                                      "branding": demo["branding"], "default_language": "ar", "custom_domain": None,
                                      "domain_verified": False, "features": {"white_label": True} if demo["branding"] else {},
                                      "sample": True, "created_by": "seed", "created_at": iso()})
        for email, account_role in demo["members"]:
            await db.users.update_one({"email": email, "account_id": {"$in": [None]}},
                                      {"$set": {"account_id": account_id, "account_role": account_role}})


# ---------- Standalone patients: hospital finder ----------
LISTABLE_TYPES = ("hospital", "clinic")


class HospitalChoice(BaseModel):
    account_id: Optional[str] = Field(default=None, max_length=20)


class ListingPatch(BaseModel):
    listed_in_app: Optional[bool] = None
    city: Optional[str] = Field(default=None, max_length=80)
    about: Optional[str] = Field(default=None, max_length=600)
    specialties: Optional[List[str]] = Field(default=None, max_length=20)


def _hospital_card(account: dict, doctors: List[dict], published: set) -> dict:
    branding = account.get("branding") or {}
    return {
        "account_id": account["account_id"],
        "name": branding.get("display_name") or account["name"],
        "legal_name": account["name"],
        "type": account.get("type"),
        "city": account.get("city"),
        "about": account.get("about") or "",
        "specialties": account.get("specialties") or sorted({d["specialty"] for d in doctors if d.get("specialty")}),
        "doctor_count": len(doctors),
        "bookable_doctor_count": sum(1 for d in doctors if d["user_id"] in published),
        "primary_color": branding.get("primary_color"),
        "logo_url": f"/api/tenant/{account['account_id']}/logo" if branding.get("logo_path") else None,
    }


async def _hospital_cards(query: dict) -> List[dict]:
    accounts = await db.accounts.find(query, ACCOUNT_PROJECTION).to_list(500)
    ids = [a["account_id"] for a in accounts]
    doctors = await db.users.find({"role": "doctor", "account_id": {"$in": ids}, "email": {"$ne": ADMIN_EMAIL}},
                                  {"_id": 0, "user_id": 1, "account_id": 1, "specialty": 1}).to_list(5000)
    published = {a["doctor_user_id"] for a in await db.doctor_availability.find(
        {"weekly": {"$ne": []}}, {"_id": 0, "doctor_user_id": 1}).to_list(5000)}
    return [_hospital_card(a, [d for d in doctors if d["account_id"] == a["account_id"]], published) for a in accounts]


@api.get("/care/hospitals")
async def list_hospitals(q: Optional[str] = None, city: Optional[str] = None, specialty: Optional[str] = None,
                         user=Depends(get_current_user)):
    query = {"listed_in_app": True, "status": {"$ne": "suspended"}, "type": {"$in": list(LISTABLE_TYPES)}}
    if city:
        query["city"] = {"$regex": re.escape(city), "$options": "i"}
    cards = await _hospital_cards(query)
    if q:
        needle = q.lower()
        cards = [c for c in cards if needle in c["name"].lower() or needle in c["legal_name"].lower()]
    if specialty:
        needle = specialty.lower()
        cards = [c for c in cards if any(needle in s.lower() for s in c["specialties"])]
    mine = user.get("account_id")
    for c in cards:
        c["is_my_hospital"] = c["account_id"] == mine
    cards.sort(key=lambda c: (not c["is_my_hospital"], -c["bookable_doctor_count"], c["name"]))
    return cards


async def _set_active_hospital(user: dict, account_id: Optional[str]):
    """One active hospital at a time: doctors from any other hospital lose access."""
    update = {"account_id": account_id, "hospital_linked_at": iso()}
    if user.get("account_id") != account_id:
        update["account_role"] = "member" if account_id else None
    if user.get("assigned_doctor_user_id"):
        doctor = await db.users.find_one({"user_id": user["assigned_doctor_user_id"]}, {"_id": 0, "account_id": 1})
        if (doctor or {}).get("account_id") and doctor["account_id"] != account_id:
            update.update(assigned_doctor_user_id=None, assigned_by="patient", assigned_at=iso())
    others = [d["user_id"] for d in await db.users.find(
        {"role": "doctor", "account_id": {"$nin": [None, account_id]}}, {"_id": 0, "user_id": 1}).to_list(5000)]
    if others:
        await db.care_grants.update_many(
            {"patient_user_id": user["user_id"], "doctor_user_id": {"$in": others}, "revoked": False},
            {"$set": {"revoked": True, "revoked_at": iso(), "revoked_reason": "Patient changed hospital"}})
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": update})
    user.update(update)


@api.get("/profile/hospital")
async def my_hospital_link(user=Depends(get_current_user)):
    hospital = None
    if user.get("account_id"):
        cards = await _hospital_cards({"account_id": user["account_id"]})
        hospital = cards[0] if cards else None
    doctor = await db.users.find_one({"user_id": user.get("assigned_doctor_user_id") or "-"},
                                     {"_id": 0, "user_id": 1, "name": 1, "specialty": 1, "account_id": 1})
    return {"hospital": hospital, "doctor": doctor, "linked_at": user.get("hospital_linked_at")}


@api.put("/profile/hospital")
async def choose_hospital(body: HospitalChoice, user=Depends(get_current_user)):
    if user.get("role") != "patient":
        raise HTTPException(status_code=403, detail="Only patients choose a hospital")
    account_id = body.account_id.upper() if body.account_id else None
    if account_id:
        account = await db.accounts.find_one({"account_id": account_id, "listed_in_app": True,
                                              "status": {"$ne": "suspended"}}, {"_id": 0, "account_id": 1})
        if not account:
            raise HTTPException(status_code=404, detail="That hospital is not taking patients through the app")
    await _set_active_hospital(user, account_id)
    return await my_hospital_link(user)


@api.patch("/account/listing")
async def update_my_listing(body: ListingPatch, user=Depends(require_account_admin)):
    update = body.model_dump(exclude_none=True)
    if update:
        update["updated_at"] = iso()
        await db.accounts.update_one({"account_id": user["account_id"]}, {"$set": update})
    return await get_account_or_404(user["account_id"])


# ---------- Pharmacy portal ----------
SPONSOR_DAYS = 30
SPONSOR_TIERS = {
    "bronze": {"label": "Bronze", "price_sar": 500.0, "rank": 3,
               "perks": ["Sponsored badge on your listing", "Shown above unsponsored pharmacies"]},
    "silver": {"label": "Silver", "price_sar": 1200.0, "rank": 2,
               "perks": ["Everything in Bronze", "Placed above Bronze sponsors", "Suggested on refill reminders"]},
    "gold": {"label": "Gold", "price_sar": 2500.0, "rank": 1,
             "perks": ["Everything in Silver", "Top placement in the marketplace", "Featured first on refills"]},
}
PORTAL_TRANSITIONS = {
    "handed_off": ("confirmed", "rejected"),
    "awaiting_pharmacist_verification": ("confirmed", "rejected"),
    "confirmed": ("ready_for_pickup", "out_for_delivery", "rejected"),
    "ready_for_pickup": ("completed",),
    "out_for_delivery": ("completed",),
}
ORDER_NOTICES = {
    "confirmed": ("Your pharmacy order was accepted", "The pharmacist accepted your order and is preparing it."),
    "rejected": ("Your pharmacy order was not accepted", "The pharmacy could not fill this order."),
    "ready_for_pickup": ("Your order is ready for pickup", "Your order is ready at the branch."),
    "out_for_delivery": ("Your order is on its way", "Your order has left the pharmacy."),
    "completed": ("Your order is complete", "The pharmacy marked your order as handed over."),
}


class PharmacyApplyIn(BaseModel):
    pharmacy_name: str = Field(min_length=2, max_length=120)
    city: str = Field(min_length=2, max_length=80)
    sfda_license: str = Field(min_length=3, max_length=60)
    phone: str = Field(default="", max_length=30)
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=6, max_length=128)


class PharmacyStaffIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)


class ReasonIn(BaseModel):
    reason: str = Field(default="", max_length=500)


class OrderStatusIn(BaseModel):
    status: str = Field(pattern="^(confirmed|rejected|ready_for_pickup|out_for_delivery|completed)$")
    note: str = Field(default="", max_length=500)


class OrderMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class SponsorRequestIn(BaseModel):
    tier: str = Field(pattern="^(bronze|silver|gold)$")


class MarkPaidIn(BaseModel):
    reference: str = Field(default="", max_length=120)


def _valid_email(email: str) -> str:
    email = email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=422, detail="Enter a valid email address")
    return email


async def require_pharmacist(user=Depends(get_current_user)):
    if user.get("role") != "pharmacist":
        raise HTTPException(status_code=403, detail="Pharmacy access required")
    if not user.get("pharmacy_id"):
        raise HTTPException(status_code=403, detail="Your pharmacy is waiting for approval")
    return user


async def _portal_order(order_id: str, user: dict) -> dict:
    order = await db.orders.find_one({"order_id": order_id, "pharmacy_id": user["pharmacy_id"]}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@api.post("/pharmacy-portal/apply")
async def apply_as_pharmacy(body: PharmacyApplyIn, request: Request):
    email = _valid_email(body.email)
    ip_key = f"pharmacy-apply:{client_ip(request)}"
    row = await db.login_attempts.find_one({"identifier": ip_key}, {"_id": 0})
    if row and row.get("window_start", "") >= iso(now_utc() - timedelta(hours=1)) and row.get("count", 0) >= 5:
        raise HTTPException(status_code=429, detail="Too many applications from this network. Try again later.")
    if row and row.get("window_start", "") >= iso(now_utc() - timedelta(hours=1)):
        await db.login_attempts.update_one({"identifier": ip_key}, {"$inc": {"count": 1}})
    else:
        await db.login_attempts.update_one({"identifier": ip_key}, {"$set": {"window_start": iso(), "count": 1}},
                                           upsert=True)
    if await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1}):
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    await db.users.insert_one({
        "user_id": user_id, "email": email, "name": body.name.strip(), "password_hash": hash_password(body.password),
        "picture": None, "role": "pharmacist", "pharmacy_id": None, "pharmacy_role": "owner",
        "clinician_requested": False, "sharing_enabled": False, "assigned_doctor_user_id": None,
        "onboarding_completed": True, "account_id": None, "created_at": iso(),
    })
    application = {
        "application_id": f"papp_{uuid.uuid4().hex[:12]}", "user_id": user_id, "email": email,
        "contact_name": body.name.strip(), "pharmacy_name": body.pharmacy_name.strip(), "city": body.city.strip(),
        "sfda_license": body.sfda_license.strip(), "phone": body.phone.strip(), "status": "pending",
        "created_at": iso(),
    }
    await db.pharmacy_applications.insert_one(dict(application))
    return {"application_id": application["application_id"], "status": "pending"}


@api.get("/pharmacy-portal/me")
async def pharmacy_portal_me(user=Depends(get_current_user)):
    if user.get("role") != "pharmacist":
        raise HTTPException(status_code=403, detail="Pharmacy access required")
    if not user.get("pharmacy_id"):
        application = await db.pharmacy_applications.find_one({"user_id": user["user_id"]}, {"_id": 0},
                                                              sort=[("created_at", -1)])
        return {"status": (application or {}).get("status", "pending"), "application": application, "pharmacy": None}
    pharmacy = await db.pharmacies.find_one({"pharmacy_id": user["pharmacy_id"]}, {"_id": 0})
    counts = {s["_id"]: s["n"] for s in await db.orders.aggregate([
        {"$match": {"pharmacy_id": user["pharmacy_id"]}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}
    ]).to_list(50)}
    return {"status": "approved", "pharmacy": {**_pharmacy_card(pharmacy or {}), "stats": (pharmacy or {}).get("stats")},
            "pharmacy_role": user.get("pharmacy_role"), "order_counts": counts}


@api.get("/pharmacy-portal/orders")
async def pharmacy_portal_orders(view: str = Query("open", pattern="^(open|done|all)$"),
                                 user=Depends(require_pharmacist)):
    query = {"pharmacy_id": user["pharmacy_id"]}
    if view == "open":
        query["status"] = {"$in": list(PORTAL_TRANSITIONS)}
    elif view == "done":
        query["status"] = {"$nin": list(PORTAL_TRANSITIONS)}
    orders = await db.orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    patients = {u["user_id"]: u for u in await db.users.find(
        {"user_id": {"$in": list({o["user_id"] for o in orders})}}, {"_id": 0, "user_id": 1, "name": 1}).to_list(500)}
    rx_ids = [o["prescription_id"] for o in orders if o.get("prescription_id")]
    prescriptions = {p["prescription_id"]: p for p in await db.prescriptions.find(
        {"prescription_id": {"$in": rx_ids}}, {"_id": 0, "prescription_id": 1, "image_path": 1,
                                               "verification_status": 1, "source": 1}).to_list(500)}
    unread = {m["_id"]: m["n"] for m in await db.order_messages.aggregate([
        {"$match": {"order_id": {"$in": [o["order_id"] for o in orders]}, "sender": "patient", "read_by_pharmacy": False}},
        {"$group": {"_id": "$order_id", "n": {"$sum": 1}}}]).to_list(500)}
    for o in orders:
        o["patient_name"] = (patients.get(o["user_id"]) or {}).get("name") or "Patient"
        rx = prescriptions.get(o.get("prescription_id")) or {}
        o["prescription"] = {"has_image": bool(rx.get("image_path")), "verification_status": rx.get("verification_status"),
                             "source": rx.get("source")} if rx else None
        o["allowed_next"] = list(PORTAL_TRANSITIONS.get(o["status"], ()))
        o["unread_messages"] = unread.get(o["order_id"], 0)
    return orders


@api.post("/pharmacy-portal/orders/{order_id}/status")
async def pharmacy_set_order_status(order_id: str, body: OrderStatusIn, request: Request,
                                    user=Depends(require_pharmacist)):
    order = await _portal_order(order_id, user)
    if body.status not in PORTAL_TRANSITIONS.get(order["status"], ()):
        raise HTTPException(status_code=409, detail=f"An order that is '{order['status']}' cannot move to '{body.status}'")
    if body.status == "rejected" and not body.note.strip():
        raise HTTPException(status_code=422, detail="Tell the patient why the order can't be filled")
    headline, text = ORDER_NOTICES[body.status]
    note = body.note.strip() or text
    entry = {"status": body.status, "at": iso(), "note": note, "by": user["name"]}
    await db.orders.update_one({"order_id": order_id}, {"$set": {"status": body.status, "updated_at": iso()},
                                                        "$push": {"status_history": entry}})
    pharmacy_name = (order.get("pharmacy_snapshot") or {}).get("name_en") or "Your pharmacy"
    await db.alerts.insert_one({
        "alert_id": f"alert_{uuid.uuid4().hex[:12]}", "user_id": order["user_id"], "profile_id": order["profile_id"],
        "type": "pharmacy", "severity": "warning" if body.status == "rejected" else "info",
        "message": f"{pharmacy_name}: {headline.lower()}", "order_id": order_id, "read": False, "created_at": iso(),
    })
    patient = await db.users.find_one({"user_id": order["user_id"]}, {"_id": 0, "email": 1, "name": 1})
    if patient and patient.get("email"):
        subject, html = notice_email(patient.get("name") or "there", headline, f"{pharmacy_name}: {note}",
                                     f"{_app_origin(request)}/pharmacy/orders", "View my order")
        _send_in_background(order["user_id"], patient["email"], subject, html)
    return await db.orders.find_one({"order_id": order_id}, {"_id": 0})


async def _order_thread(order_id: str, reader: str):
    field = "read_by_pharmacy" if reader == "pharmacy" else "read_by_patient"
    await db.order_messages.update_many({"order_id": order_id, field: False}, {"$set": {field: True}})
    return await db.order_messages.find({"order_id": order_id}, {"_id": 0}).sort("created_at", 1).to_list(500)


async def _post_order_message(order: dict, sender: str, name: str, text: str) -> dict:
    message = {"message_id": f"omsg_{uuid.uuid4().hex[:12]}", "order_id": order["order_id"], "sender": sender,
               "sender_name": name, "text": text.strip(), "read_by_pharmacy": sender == "pharmacy",
               "read_by_patient": sender == "patient", "created_at": iso()}
    await db.order_messages.insert_one(dict(message))
    if sender == "pharmacy":
        await db.alerts.insert_one({
            "alert_id": f"alert_{uuid.uuid4().hex[:12]}", "user_id": order["user_id"], "profile_id": order["profile_id"],
            "type": "pharmacy", "severity": "info",
            "message": f"{(order.get('pharmacy_snapshot') or {}).get('name_en') or 'Your pharmacy'} sent you a message about your order",
            "order_id": order["order_id"], "read": False, "created_at": iso(),
        })
    message.pop("_id", None)
    return message


@api.get("/pharmacy-portal/orders/{order_id}/messages")
async def pharmacy_order_messages(order_id: str, user=Depends(require_pharmacist)):
    await _portal_order(order_id, user)
    return await _order_thread(order_id, "pharmacy")


@api.post("/pharmacy-portal/orders/{order_id}/messages")
async def pharmacy_send_message(order_id: str, body: OrderMessageIn, user=Depends(require_pharmacist)):
    order = await _portal_order(order_id, user)
    return await _post_order_message(order, "pharmacy", user["name"], body.text)


@api.get("/pharmacy-portal/orders/{order_id}/prescription-image")
async def pharmacy_prescription_image(order_id: str, user=Depends(require_pharmacist)):
    order = await _portal_order(order_id, user)
    rx = await db.prescriptions.find_one({"prescription_id": order.get("prescription_id") or "-"}, {"_id": 0})
    if not rx or not rx.get("image_path"):
        raise HTTPException(status_code=404, detail="This order has no prescription image")
    data, content_type = get_object(rx["image_path"])
    return Response(content=data, media_type=rx.get("content_type") or content_type, headers={"Cache-Control": "no-store"})


@api.get("/pharmacy/orders/{order_id}/messages")
async def patient_order_messages(order_id: str, user=Depends(get_current_user)):
    await get_order(order_id, user)
    return await _order_thread(order_id, "patient")


@api.post("/pharmacy/orders/{order_id}/messages")
async def patient_send_message(order_id: str, body: OrderMessageIn, user=Depends(get_current_user)):
    order = await get_order(order_id, user)
    if not order.get("pharmacy_id"):
        raise HTTPException(status_code=409, detail="This order has no pharmacy to message")
    return await _post_order_message(order, "patient", user["name"], body.text)


@api.get("/pharmacy-portal/sponsorship")
async def pharmacy_sponsorship(user=Depends(require_pharmacist)):
    pharmacy = await db.pharmacies.find_one({"pharmacy_id": user["pharmacy_id"]}, {"_id": 0}) or {}
    sponsorship = pharmacy.get("sponsorship") or {}
    requests = await db.sponsorship_requests.find({"pharmacy_id": user["pharmacy_id"]}, {"_id": 0}
                                                  ).sort("created_at", -1).to_list(50)
    since = iso(now_utc() - timedelta(days=30))
    orders_30d = await db.orders.count_documents({"pharmacy_id": user["pharmacy_id"], "created_at": {"$gte": since}})
    return {"tiers": [{"key": k, **v, "days": SPONSOR_DAYS} for k, v in SPONSOR_TIERS.items()],
            "current": {"tier": sponsorship.get("tier"), "active_until": sponsorship.get("active_until"),
                        "active": _is_sponsored(pharmacy)},
            "requests": requests, "payment_provider_connected": False,
            "stats": {"impressions": (pharmacy.get("stats") or {}).get("impressions", 0), "orders_30d": orders_30d}}


@api.post("/pharmacy-portal/sponsorship/requests")
async def request_sponsorship(body: SponsorRequestIn, user=Depends(require_pharmacist)):
    if await db.sponsorship_requests.find_one({"pharmacy_id": user["pharmacy_id"], "status": "awaiting_payment"}):
        raise HTTPException(status_code=409, detail="You already have a sponsorship waiting for payment")
    tier = SPONSOR_TIERS[body.tier]
    pharmacy = await db.pharmacies.find_one({"pharmacy_id": user["pharmacy_id"]}, {"_id": 0, "name_en": 1})
    request_doc = {
        "request_id": f"spr_{uuid.uuid4().hex[:10]}", "reference": f"SP-{uuid.uuid4().hex[:6].upper()}",
        "pharmacy_id": user["pharmacy_id"], "pharmacy_name": (pharmacy or {}).get("name_en"), "tier": body.tier,
        "tier_label": tier["label"], "amount_sar": tier["price_sar"], "days": SPONSOR_DAYS,
        "status": "awaiting_payment", "payment_provider": None, "requested_by": user["user_id"],
        "requested_by_name": user["name"], "created_at": iso(),
    }
    await db.sponsorship_requests.insert_one(dict(request_doc))
    return request_doc


@api.post("/pharmacy-portal/sponsorship/requests/{request_id}/cancel")
async def cancel_sponsorship_request(request_id: str, user=Depends(require_pharmacist)):
    result = await db.sponsorship_requests.update_one(
        {"request_id": request_id, "pharmacy_id": user["pharmacy_id"], "status": "awaiting_payment"},
        {"$set": {"status": "cancelled", "closed_at": iso()}})
    if not result.matched_count:
        raise HTTPException(status_code=409, detail="Only a request waiting for payment can be cancelled")
    return {"ok": True}


@api.get("/admin/pharmacies")
async def admin_pharmacies(admin=Depends(require_admin)):
    pharmacies = await db.pharmacies.find({}, {"_id": 0}).sort("name_en", 1).to_list(500)
    staff = await db.users.find({"role": "pharmacist", "pharmacy_id": {"$ne": None}},
                                {"_id": 0, "user_id": 1, "name": 1, "email": 1, "pharmacy_id": 1, "pharmacy_role": 1,
                                 "password_hash": 1}).to_list(5000)
    out = []
    for p in pharmacies:
        card = _pharmacy_card(p)
        card["sponsorship"] = p.get("sponsorship") or {}
        card["staff"] = [{"user_id": s["user_id"], "name": s["name"], "email": s["email"],
                          "pharmacy_role": s.get("pharmacy_role"),
                          "status": "active" if s.get("password_hash") else "invited"}
                         for s in staff if s["pharmacy_id"] == p["pharmacy_id"]]
        out.append(card)
    return out


@api.post("/admin/pharmacies/{pharmacy_id}/staff")
async def invite_pharmacy_staff(pharmacy_id: str, body: PharmacyStaffIn, request: Request, admin=Depends(require_admin)):
    pharmacy = await db.pharmacies.find_one({"pharmacy_id": pharmacy_id}, {"_id": 0})
    if not pharmacy:
        raise HTTPException(status_code=404, detail="Pharmacy not found")
    email = _valid_email(body.email)
    existing = await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1, "role": 1, "pharmacy_id": 1})
    if existing:
        if existing.get("role") != "pharmacist" or existing.get("pharmacy_id") not in (None, pharmacy_id):
            raise HTTPException(status_code=409, detail="This email already belongs to another account")
        await db.users.update_one({"user_id": existing["user_id"]}, {"$set": {"pharmacy_id": pharmacy_id}})
        return {"user_id": existing["user_id"], "invited": False, "linked": True}
    has_staff = await db.users.count_documents({"role": "pharmacist", "pharmacy_id": pharmacy_id})
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    await db.users.insert_one({
        "user_id": user_id, "email": email, "name": body.name.strip(), "picture": None, "role": "pharmacist",
        "pharmacy_id": pharmacy_id, "pharmacy_role": "staff" if has_staff else "owner", "clinician_requested": False,
        "sharing_enabled": False, "assigned_doctor_user_id": None, "onboarding_completed": True, "account_id": None,
        "invited_at": iso(), "invited_by": admin["user_id"], "created_at": iso(),
    })
    token = await _issue_password_token(user_id, email, 7 * 24 * 60)
    subject, html = account_invite_email(body.name.strip(), pharmacy.get("name_en") or "your pharmacy",
                                         f"{_app_origin(request)}/auth/reset?token={token}&next=pharmacy")
    _send_in_background(user_id, email, subject, html)
    return {"user_id": user_id, "invited": True, "linked": False}


@api.delete("/admin/pharmacies/{pharmacy_id}/staff/{user_id}")
async def remove_pharmacy_staff(pharmacy_id: str, user_id: str, admin=Depends(require_admin)):
    result = await db.users.update_one({"user_id": user_id, "role": "pharmacist", "pharmacy_id": pharmacy_id},
                                       {"$set": {"pharmacy_id": None, "pharmacy_removed_at": iso()}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return {"ok": True}


@api.get("/admin/pharmacy-applications")
async def admin_pharmacy_applications(status: str = Query("pending", pattern="^(pending|approved|rejected|all)$"),
                                      admin=Depends(require_admin)):
    query = {} if status == "all" else {"status": status}
    return await db.pharmacy_applications.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)


async def _open_application(application_id: str) -> dict:
    application = await db.pharmacy_applications.find_one({"application_id": application_id, "status": "pending"},
                                                           {"_id": 0})
    if not application:
        raise HTTPException(status_code=409, detail="This application was already handled")
    return application


@api.post("/admin/pharmacy-applications/{application_id}/approve")
async def approve_pharmacy(application_id: str, request: Request, admin=Depends(require_admin)):
    application = await _open_application(application_id)
    pharmacy_id = f"ph_{uuid.uuid4().hex[:10]}"
    await db.pharmacies.insert_one({
        "pharmacy_id": pharmacy_id, "name_en": application["pharmacy_name"], "name_ar": application["pharmacy_name"],
        "sfda_license": application["sfda_license"], "moh_license": None, "cr_number": None,
        "fulfilment_mode": "in_app", "handoff_url_template": None,
        "sponsorship": {"tier": None, "rank": None, "active_until": None},
        "branches": [{"branch_id": f"br_{uuid.uuid4().hex[:8]}", "city": application["city"], "lat": None, "lng": None,
                      "delivery_zones": [], "hours": "", "phone": application.get("phone")}],
        "active": True, "source": "portal_application", "created_at": iso(),
    })
    await db.users.update_one({"user_id": application["user_id"]},
                              {"$set": {"pharmacy_id": pharmacy_id, "pharmacy_role": "owner"}})
    await db.pharmacy_applications.update_one({"application_id": application_id},
                                              {"$set": {"status": "approved", "pharmacy_id": pharmacy_id,
                                                        "decided_by": admin["user_id"], "decided_at": iso()}})
    subject, html = notice_email(application["contact_name"], "Your pharmacy is approved",
                                 f"{application['pharmacy_name']} is now live on the marketplace. Sign in to manage orders.",
                                 f"{_app_origin(request)}/auth/pharmacy", "Open the pharmacy portal")
    _send_in_background(application["user_id"], application["email"], subject, html)
    return {"application_id": application_id, "status": "approved", "pharmacy_id": pharmacy_id}


@api.post("/admin/pharmacy-applications/{application_id}/reject")
async def reject_pharmacy(application_id: str, body: ReasonIn, admin=Depends(require_admin)):
    await _open_application(application_id)
    await db.pharmacy_applications.update_one({"application_id": application_id},
                                              {"$set": {"status": "rejected", "reason": body.reason.strip(),
                                                        "decided_by": admin["user_id"], "decided_at": iso()}})
    return {"application_id": application_id, "status": "rejected"}


@api.get("/admin/sponsorship-requests")
async def admin_sponsorship_requests(status: str = Query("awaiting_payment", pattern="^(awaiting_payment|paid|declined|cancelled|all)$"),
                                     admin=Depends(require_admin)):
    query = {} if status == "all" else {"status": status}
    return await db.sponsorship_requests.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)


@api.post("/admin/sponsorship-requests/{request_id}/mark-paid")
async def mark_sponsorship_paid(request_id: str, body: MarkPaidIn, admin=Depends(require_admin)):
    req = await db.sponsorship_requests.find_one({"request_id": request_id, "status": "awaiting_payment"}, {"_id": 0})
    if not req:
        raise HTTPException(status_code=409, detail="This request is not waiting for payment")
    pharmacy = await db.pharmacies.find_one({"pharmacy_id": req["pharmacy_id"]}, {"_id": 0}) or {}
    current = pharmacy.get("sponsorship") or {}
    start = now_utc()
    if _is_sponsored(pharmacy) and current.get("tier") == req["tier"] and current.get("active_until"):
        start = max(start, datetime.fromisoformat(current["active_until"]))
    active_until = iso(start + timedelta(days=req["days"]))
    await db.pharmacies.update_one({"pharmacy_id": req["pharmacy_id"]}, {"$set": {"sponsorship": {
        "tier": req["tier"], "rank": SPONSOR_TIERS[req["tier"]]["rank"], "active_until": active_until,
        "started_at": iso(), "request_id": request_id}}})
    await db.sponsorship_requests.update_one({"request_id": request_id}, {"$set": {
        "status": "paid", "payment_provider": "manual", "payment_reference": body.reference.strip(),
        "active_until": active_until, "confirmed_by": admin["user_id"], "closed_at": iso()}})
    return await db.sponsorship_requests.find_one({"request_id": request_id}, {"_id": 0})


@api.post("/admin/sponsorship-requests/{request_id}/decline")
async def decline_sponsorship(request_id: str, body: ReasonIn, admin=Depends(require_admin)):
    result = await db.sponsorship_requests.update_one(
        {"request_id": request_id, "status": "awaiting_payment"},
        {"$set": {"status": "declined", "reason": body.reason.strip(), "closed_at": iso()}})
    if not result.matched_count:
        raise HTTPException(status_code=409, detail="This request is not waiting for payment")
    return {"ok": True}



app.include_router(api)

FEATURE_ROUTES = [
    (re.compile(r"^/api/chat(/|$)"), "health_chat"),
    (re.compile(r"^/api/pills(/|$)"), "pill_id"),
    (re.compile(r"^/api/booking(/|$)"), "booking"),
    (re.compile(r"^/api/(prescriptions(/|$)|encounters/[^/]+/prescription$)"), "prescriptions"),
    (re.compile(r"^/api/(patient/visit-summaries|artifacts/[^/]+/patient-summary)"), "visit_summaries"),
    (re.compile(r"^/api/pharmacy(/|$)"), "pharmacy_marketplace"),
    (re.compile(r"^/api/encounters/[^/]+/audio/live$"), "live_transcript"),
]
_flag_cache: dict = {}


async def _flags_for_account(account_id: Optional[str]) -> dict:
    cached = _flag_cache.get(account_id)
    if cached and cached[0] > now_utc():
        return cached[1]
    account = await db.accounts.find_one({"account_id": account_id}, ACCOUNT_PROJECTION) if account_id else None
    flags = await effective_flags(account)
    _flag_cache[account_id] = (now_utc() + timedelta(seconds=15), flags)
    return flags


@app.middleware("http")
async def enforce_feature_flags(request: Request, call_next):
    """Switched-off features return 403 for the signed-in user's account; unauthenticated calls fall through to auth."""
    key = next((k for pattern, k in FEATURE_ROUTES if pattern.match(request.url.path)), None)
    token = request.cookies.get("access_token") or request.headers.get("Authorization", "").removeprefix("Bearer ")
    if key and token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.PyJWTError:
            payload = None
        if payload and payload.get("type") == "access":
            try:
                user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0, "account_id": 1})
                flags = await _flags_for_account((user or {}).get("account_id"))
            except DB_DOWN_ERRORS:
                return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable",
                                                              "code": "service_unavailable"})
            if not flags.get(key, True):
                return JSONResponse(status_code=403, content={"detail": "This feature is turned off for your organisation",
                                                              "code": "feature_disabled"})
    return await call_next(request)

CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
if "*" in CORS_ORIGINS:
    raise RuntimeError(
        "CORS_ORIGINS must not contain '*' while credentials are enabled — list explicit origins."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
