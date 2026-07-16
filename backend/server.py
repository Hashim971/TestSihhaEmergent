import os
import json
import uuid
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import Optional, List

from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent, TextDelta, StreamDone

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


# ---------- Auth ----------
async def get_current_user(request: Request):
    token = request.cookies.get("session_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now_utc():
        raise HTTPException(status_code=401, detail="Session expired")
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


class SessionRequest(BaseModel):
    session_id: str


@api.post("/auth/session")
async def create_session(body: SessionRequest, response: Response):
    async with httpx.AsyncClient() as hc:
        r = await hc.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": body.session_id},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session id")
    data = r.json()
    existing = await db.users.find_one({"email": data["email"]}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": data.get("name"), "picture": data.get("picture")}},
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": data["email"],
            "name": data.get("name"),
            "picture": data.get("picture"),
            "role": "patient",
            "sharing_enabled": False,
            "created_at": iso(),
        })
    session_token = data["session_token"]
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": iso(now_utc() + timedelta(days=7)),
        "created_at": iso(),
    })
    response.set_cookie(
        key="session_token", value=session_token, httponly=True,
        secure=True, samesite="none", path="/", max_age=7 * 24 * 3600,
    )
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return user


@api.get("/auth/me")
async def auth_me(user=Depends(get_current_user)):
    return user


@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


class RoleUpdate(BaseModel):
    role: str


@api.post("/auth/role")
async def set_role(body: RoleUpdate, user=Depends(get_current_user)):
    if body.role not in ("patient", "doctor"):
        raise HTTPException(status_code=400, detail="Invalid role")
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"role": body.role}})
    return await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})


class SharingUpdate(BaseModel):
    enabled: bool


@api.post("/auth/sharing")
async def set_sharing(body: SharingUpdate, user=Depends(get_current_user)):
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"sharing_enabled": body.enabled}})
    return await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})


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
    system = SCREENING_SYSTEM_PROMPT + ("\n\nConversation so far:\n" + context if context else "")

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
    return report


@api.get("/reports")
async def list_reports(user=Depends(get_current_user)):
    return await db.health_reports.find({"user_id": user["user_id"]}, {"_id": 0}).sort("generated_at", -1).to_list(50)


# ---------- Pill Identification ----------
class PillIdentifyRequest(BaseModel):
    image_base64: str
    profile_id: Optional[str] = None


@api.post("/pills/identify")
async def identify_pill(body: PillIdentifyRequest, user=Depends(get_current_user)):
    chat = LlmChat(
        api_key=LLM_KEY, session_id=f"pill_{uuid.uuid4().hex[:8]}", system_message=PILL_ID_PROMPT
    ).with_model("openai", "gpt-5.5")
    img = ImageContent(image_base64=body.image_base64)
    result = await chat.send_message(UserMessage(
        text="Identify this medication and return the JSON.", file_contents=[img]
    ))
    text = result.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        parsed = json.loads(text.strip())
    except Exception:
        parsed = {"identified": False, "reason": "Could not parse AI response", "raw": result}
    record = {
        "pill_id": f"pill_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "profile_id": profile_key(user, body.profile_id),
        "result": parsed,
        "created_at": iso(),
    }
    await db.pill_history.insert_one(record)
    record.pop("_id", None)
    return record


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


@api.get("/doctor/patients")
async def doctor_patients(user=Depends(require_doctor)):
    patients = await db.users.find({"sharing_enabled": True, "role": "patient"}, {"_id": 0}).to_list(200)
    out = []
    for p in patients:
        alerts = await db.alerts.count_documents({"user_id": p["user_id"], "read": False})
        out.append({**p, "unread_alerts": alerts})
    return out


@api.get("/doctor/patients/{patient_id}/summary")
async def doctor_patient_summary(patient_id: str, user=Depends(require_doctor)):
    patient = await db.users.find_one({"user_id": patient_id, "sharing_enabled": True}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found or not sharing")
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


@api.get("/")
async def root():
    return {"app": "Sihha AI", "status": "ok"}


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
