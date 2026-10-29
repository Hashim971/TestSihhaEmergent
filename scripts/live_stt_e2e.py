import asyncio, os, requests
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from emergentintegrations.llm.openai import OpenAITextToSpeech

API = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0] + "/api"
TEXT = "مرحبا يا دكتور، عندي صداع من ثلاثة أيام وضغطي مرتفع. أنا آخذ كونكور خمسة ملغ مرة يومياً."


async def make_audio():
    tts = OpenAITextToSpeech(api_key=os.environ["EMERGENT_LLM_KEY"])
    audio = await tts.generate_speech(text=TEXT, model="tts-1", voice="alloy", response_format="mp3")
    return audio


def main():
    audio = asyncio.run(make_audio())
    print("audio bytes", len(audio))
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "admin@sihha.ai", "password": "Admin@123"})
    print("admin login", r.status_code)
    print("provider", s.get(f"{API}/admin/transcription").json())
    d = requests.Session()
    r = d.post(f"{API}/auth/login", json={"email": "dr.layla@sihha.ai", "password": "Doctor@123"})
    print("doctor login", r.status_code)
    encs = d.get(f"{API}/encounters").json()
    encs = encs if isinstance(encs, list) else encs.get("encounters", encs.get("items", []))
    enc = encs[0]["encounter_id"]
    print("encounter", enc)
    print("consent", d.post(f"{API}/encounters/{enc}/consent", json={"granted": True}).status_code)
    a = d.post(f"{API}/encounters/{enc}/audio/init", params={"mime_type": "audio/mpeg"}).json()
    aid = a["audio_id"]
    half = len(audio) // 2
    for i, part in enumerate([audio[:half], audio[half:]]):
        r = d.post(f"{API}/audio/{aid}/chunk", data={"index": i}, files={"chunk": ("c", part)})
        print("chunk", i, r.status_code)
    r = d.post(f"{API}/audio/{aid}/complete", data={"duration_seconds": 8})
    print("complete", r.status_code, r.text[:300])
    st = d.get(f"{API}/encounters/{enc}/audio").json() if r.ok else None
    print("audio status", str(st)[:600])


main()
