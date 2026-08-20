"""Seeds two synthetic screening reports for omar.patient so triage can be exercised without paying for a chat."""
import asyncio, os, uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient


def iso():
    return datetime.now(timezone.utc).isoformat()


def finding(symptom, words, severity="moderate"):
    return {"finding_id": f"find_{uuid.uuid4().hex[:10]}", "symptom": symptom, "patient_words": words,
            "severity": severity, "onset": "2 days ago", "duration": "2 days", "source_message_ids": []}


REPORTS = [
    ("RED", "Screening summary: patient reports chest pain radiating to the left arm since this morning, "
            "with sweating and shortness of breath.",
     [finding("Chest pain", "I have chest pain that goes into my left arm", "severe"),
      finding("Shortness of breath", "I feel short of breath when I walk")]),
    ("MILD", "Screening summary: patient reports a small itchy rash on the forearm for three days, no fever, "
             "no spreading, sleeping and eating normally.",
     [finding("Itchy rash", "a small itchy rash on my arm", "mild")]),
]


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    user = await db.users.find_one({"email": "omar.patient@sihha.ai"}, {"_id": 0, "user_id": 1})
    await db.health_reports.delete_many({"user_id": user["user_id"], "seeded_probe": True})
    for tag, content, findings in REPORTS:
        report = {
            "report_id": f"report_{uuid.uuid4().hex[:12]}",
            "chat_session_id": f"chat_{uuid.uuid4().hex[:12]}",
            "user_id": user["user_id"], "profile_id": user["user_id"],
            "content": content, "findings": findings, "findings_extracted_at": iso(),
            "generated_at": iso(), "seeded_probe": True,
        }
        await db.health_reports.insert_one(report)
        print(tag, report["report_id"])


asyncio.run(main())
