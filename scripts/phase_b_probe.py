import asyncio, os, secrets, hashlib, subprocess, requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient
from emergentintegrations.llm.openai import OpenAITextToSpeech

API = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0] + "/api"
EMAIL = "delivered+sihha-reset@resend.dev"


async def db_token():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    user = await db.users.find_one({"email": EMAIL}, {"_id": 0, "user_id": 1})
    sent = await db.password_reset_tokens.count_documents({"email": EMAIL})
    raw = secrets.token_urlsafe(32)
    await db.password_reset_tokens.insert_one({
        "token_hash": hashlib.sha256(raw.encode()).hexdigest(), "user_id": user["user_id"], "email": EMAIL,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=60), "used_at": None,
        "created_at": datetime.now(timezone.utc).isoformat()})
    return raw, sent


def reset_flow():
    s = requests.Session()
    r = s.post(f"{API}/auth/register", json={"name": "Reset Tester", "email": EMAIL, "password": "OldPass1"})
    print("register", r.status_code)
    r = requests.post(f"{API}/auth/forgot-password", json={"email": EMAIL})
    print("forgot (real email send)", r.status_code, r.json())
    raw, sent = asyncio.run(db_token())
    print("tokens stored for user", sent)
    r = requests.post(f"{API}/auth/reset-password", json={"token": raw, "password": "NewPass1"})
    print("reset", r.status_code, r.json())
    r = requests.post(f"{API}/auth/reset-password", json={"token": raw, "password": "Another1"})
    print("reuse same token ->", r.status_code)
    print("login old pw ->", requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": "OldPass1"}).status_code)
    print("login new pw ->", requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": "NewPass1"}).status_code)


async def tts():
    t = OpenAITextToSpeech(api_key=os.environ["EMERGENT_LLM_KEY"])
    return await t.generate_speech(text="عندي ألم في الصدر منذ يومين ويزيد مع المشي.", model="tts-1", voice="alloy",
                                   response_format="mp3")


def live_flow():
    open("/tmp/live.mp3", "wb").write(asyncio.run(tts()))
    d = requests.Session()
    d.post(f"{API}/auth/login", json={"email": "dr.layla@sihha.ai", "password": "Doctor@123"})
    enc = d.get(f"{API}/encounters").json()[0]["encounter_id"]
    d.post(f"{API}/encounters/{enc}/consent", json={"granted": True})
    r = d.post(f"{API}/encounters/{enc}/audio/live", data={"offset_seconds": 20, "window_seconds": 10},
               files={"chunk": ("live.mp3", open("/tmp/live.mp3", "rb"), "audio/mpeg")})
    print("live", r.status_code, r.text[:400])
    p = requests.Session()
    p.post(f"{API}/auth/login", json={"email": "omar.patient@sihha.ai", "password": "Patient@123"})
    r = p.post(f"{API}/encounters/{enc}/audio/live", data={"offset_seconds": 0},
               files={"chunk": ("live.mp3", open("/tmp/live.mp3", "rb"), "audio/mpeg")})
    print("live as patient ->", r.status_code)


live_flow()
