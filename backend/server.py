import os
import json
import uuid
import logging
import re
import random
import base64
import asyncio
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from cryptography.fernet import Fernet
from typing import Optional, List, Any

from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent, TextDelta, StreamDone
from gradio_client import Client as GradioClient, handle_file

from agents import tools as agent_tools
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

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
LLM_KEY = os.environ["EMERGENT_LLM_KEY"]

app = FastAPI(title="Sihha AI")
api = APIRouter(prefix="/api")

# Original system prompt from the user's TestSihha project (healthAI.ts)
SCREENING_SYSTEM_PROMPT = (
    "This GPT is designed to provide accurate and detailed information regarding various medical conditions. "
    "It should ask the patient to further explain what are they feeling exactly to give proper answers before "
    "jumping into conclusions basically it should do basic health screening or symptom checking as well as give "
    "proper diagnostics like a professional doctor would and assess the user's symptoms to give a proper health "
    "screening report to be used by the healthcare professional as they will be relying on it (all questions must "
    "be asked one by one give room for the patient to answer the questions one by one). The questions should be "
    "one by one giving the patient room to answer all questions properly (all questions must be asked one by one). "
    "It should always reference reputable sources and maintain a formal, professional tone. In situations where "
    "there is insufficient information to provide a detailed response, it should ask for clarification and suggest "
    "consulting a healthcare professional as well as suggesting what the user should do depending on their situation "
    "and also ask the user if they need the health screening medical report after the health screening is over. "
    "It should also utilize the dataset provided. Generate a report after the symptom check is done but ask the "
    "user if they need it first."
)

REPORT_PROMPT = """Generate a comprehensive medical screening report based on this conversation. Include:

1. CHIEF COMPLAINT
   - Main symptoms
   - Onset and duration
   - Severity and characteristics

2. HISTORY OF PRESENT ILLNESS
   - Progression of symptoms
   - Associated symptoms
   - Aggravating/relieving factors
   - Impact on daily activities

3. ASSESSMENT SUMMARY
   - Key findings from the conversation
   - Areas requiring attention

4. RECOMMENDATIONS
   - Suggested next steps
   - Lifestyle modifications if applicable
   - Warning signs to watch for

5. IMPORTANT NOTES
   - This is not a diagnosis
   - Advise consulting a healthcare provider
   - Note any concerning symptoms that require immediate attention

Base this report on the following conversation:
"""

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
    payload = {"sub": user_id, "email": email, "type": "access",
               "exp": datetime.now(timezone.utc) + timedelta(minutes=15)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "type": "refresh",
               "exp": datetime.now(timezone.utc) + timedelta(days=7)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


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
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return with_capabilities(user)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1)
    email: str
    password: str = Field(min_length=6)
    requested_role: Optional[str] = None


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
        "created_at": iso(),
    })
    set_auth_cookies(response, create_access_token(user_id, email), create_refresh_token(user_id))
    return with_capabilities(await db.users.find_one({"user_id": user_id}, USER_PROJECTION))


@api.post("/auth/login")
async def login(body: LoginRequest, request: Request, response: Response):
    email = body.email.strip().lower()
    identifier = f"{request.client.host}:{email}"
    attempt = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0})
    if attempt and attempt.get("locked_until"):
        locked_until = datetime.fromisoformat(attempt["locked_until"])
        if locked_until > now_utc():
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash") or not verify_password(body.password, user["password_hash"]):
        count = (attempt.get("count", 0) + 1) if attempt else 1
        update = {"identifier": identifier, "count": count, "updated_at": iso()}
        if count >= 5:
            update["locked_until"] = iso(now_utc() + timedelta(minutes=15))
            update["count"] = 0
        await db.login_attempts.update_one({"identifier": identifier}, {"$set": update}, upsert=True)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    await db.login_attempts.delete_one({"identifier": identifier})
    set_auth_cookies(response, create_access_token(user["user_id"], email), create_refresh_token(user["user_id"]))
    return with_capabilities(await db.users.find_one({"user_id": user["user_id"]}, USER_PROJECTION))


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
    if not user:
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


@app.on_event("startup")
async def seed_and_index():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.encounters.create_index([("doctor_user_id", 1), ("scheduled_at", -1)])
    await db.encounters.create_index([("patient_user_id", 1), ("scheduled_at", -1)])
    await db.agent_runs.create_index([("patient_user_id", 1), ("created_at", -1)])
    await db.clinical_artifacts.create_index("encounter_id")
    await db.briefing_threads.create_index("artifact_id", unique=True)
    await db.intake_forms.create_index("encounter_id", unique=True)
    await db.intake_forms.create_index([("patient_user_id", 1), ("status", 1)])
    await db.consultation_audio.create_index("encounter_id")
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
    greeting = "Hello! I'm here to help assess your health concerns. Could you please tell me what brings you in today?"
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
    system = SCREENING_SYSTEM_PROMPT
    if session["profile_id"] == user["user_id"]:
        system += health_profile_context(user)
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
        api_key=LLM_KEY, session_id=f"report_{sid}",
        system_message="You are a medical report writer. Output plain text sections, no markdown symbols like ** or #.",
    ).with_model("openai", "gpt-5.5")
    result = await chat.send_message(UserMessage(text=REPORT_PROMPT + convo))
    report = {
        "report_id": f"report_{uuid.uuid4().hex[:12]}",
        "chat_session_id": sid,
        "user_id": user["user_id"],
        "profile_id": session["profile_id"],
        "content": result,
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
AUDIO_DIR = Path(os.environ.get("AUDIO_STORAGE_DIR", "/app/backend/uploads/audio"))
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
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


@api.post("/audio/{audio_id}/chunk")
async def upload_audio_chunk(audio_id: str, index: int = Form(...), chunk: UploadFile = File(...),
                             user=Depends(require_doctor)):
    audio = await db.consultation_audio.find_one({"audio_id": audio_id}, {"_id": 0})
    if not audio:
        raise HTTPException(status_code=404, detail="Upload not found")
    await _consented_encounter(audio["encounter_id"], user)
    part = AUDIO_DIR / f"{audio_id}.part"
    data = await chunk.read()
    with open(part, "ab") as fh:
        fh.write(data)
    os.chmod(part, 0o600)
    await db.consultation_audio.update_one({"audio_id": audio_id},
                                           {"$inc": {"size_bytes": len(data)}})
    return {"audio_id": audio_id, "index": index, "received_bytes": len(data)}


@api.post("/audio/{audio_id}/complete")
async def complete_audio_upload(audio_id: str, duration_seconds: float = Form(0.0), user=Depends(require_doctor)):
    audio = await db.consultation_audio.find_one({"audio_id": audio_id}, {"_id": 0})
    if not audio:
        raise HTTPException(status_code=404, detail="Upload not found")
    enc = await _consented_encounter(audio["encounter_id"], user)
    part = AUDIO_DIR / f"{audio_id}.part"
    if not part.exists():
        raise HTTPException(status_code=400, detail="No audio was uploaded")

    encrypted = AUDIO_DIR / f"{audio_id}.enc"
    encrypted.write_bytes(_fernet.encrypt(part.read_bytes()))
    os.chmod(encrypted, 0o600)
    part.unlink()
    await db.consultation_audio.update_one(
        {"audio_id": audio_id},
        {"$set": {"storage_path": str(encrypted), "duration_seconds": duration_seconds,
                  "transcription_status": "processing"}},
    )

    plain = AUDIO_DIR / f"{audio_id}.{AUDIO_EXTENSIONS.get(audio.get('mime_type'), 'webm')}"
    try:
        plain.write_bytes(_fernet.decrypt(encrypted.read_bytes()))
        provider = await resolved_transcription_provider()
        transcript = await get_transcriber(provider).transcribe(str(plain), language_hint="ar-SA")
    except Exception as exc:
        await db.consultation_audio.update_one({"audio_id": audio_id},
                                               {"$set": {"transcription_status": "failed"}})
        logging.getLogger(__name__).exception("Transcription failed for %s", audio_id)
        raise HTTPException(status_code=502, detail=f"Transcription failed: {type(exc).__name__}")
    finally:
        plain.unlink(missing_ok=True)

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
    if not audio.get("storage_path") or not Path(audio["storage_path"]).exists():
        raise HTTPException(status_code=410, detail="This recording has passed its retention period")
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
        if path:
            Path(path).unlink(missing_ok=True)
        await db.consultation_audio.update_one(
            {"audio_id": audio["audio_id"]},
            {"$set": {"storage_path": None, "transcript": None, "deleted_at": iso()}},
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
        out.append(card)
    out.sort(key=lambda p: (0 if p["sponsored"] else 1, p["name_en"]))
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
                           user=Depends(get_current_user)):
    """The patient's own doctor first, then anyone else who publishes slots."""
    query = {"role": "doctor", "email": {"$ne": ADMIN_EMAIL}}
    if specialty:
        query["specialty"] = {"$regex": re.escape(specialty), "$options": "i"}
    if city:
        query["city"] = {"$regex": re.escape(city), "$options": "i"}
    doctors = await db.users.find(query, {"_id": 0, "user_id": 1, "name": 1, "specialty": 1, "clinic": 1,
                                          "city": 1, "bio": 1, "clinic_phone": 1}).to_list(200)
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
        "created_at": iso(),
        "updated_at": iso(),
    }
    await db.encounters.insert_one(dict(encounter))

    if doctor["user_id"] != user.get("assigned_doctor_user_id"):
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
    if report:
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
async def create_prescription(encounter_id: str, body: PrescriptionIn, user=Depends(require_doctor)):
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





app.include_router(api)

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
