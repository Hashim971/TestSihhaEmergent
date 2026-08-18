"""Phase 1 seed data: 1 doctor, 3 sharing patients with 90 days of vitals + dose logs, 5 encounters.

Run:  cd /app/backend && python seed_phase1.py
Recent-window vitals come from the existing POST /api/vitals/simulate endpoint; the earlier part of
the 90-day window is backfilled with the same distributions so trends are visible to the agents.
"""
import os
import random
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

BASE = os.environ.get("SEED_BASE_URL") or next(
    (l.split("=", 1)[1].strip() for l in (ROOT.parent / "frontend" / ".env").read_text().splitlines()
     if l.startswith("REACT_APP_BACKEND_URL")), None
)
API = f"{BASE.rstrip('/')}/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

DOCTOR = {"name": "Dr. Layla Haddad", "email": "dr.layla@sihha.ai", "password": "Doctor@123"}
PATIENTS = [
    {"name": "Omar Farouk", "email": "omar.patient@sihha.ai", "password": "Patient@123",
     "profile": "hypertensive", "reason": "Blood pressure review"},
    {"name": "Noura Aziz", "email": "noura.patient@sihha.ai", "password": "Patient@123",
     "profile": "diabetic", "reason": "Diabetes follow-up and fatigue"},
    {"name": "Sami Rahman", "email": "sami.patient@sihha.ai", "password": "Patient@123",
     "profile": "stable", "reason": "Annual check-up"},
]
MEDS = {
    "hypertensive": [("Lisinopril", "10 mg", ["08:00"]), ("Aspirin", "81 mg", ["08:00"])],
    "diabetic": [("Metformin", "500 mg", ["08:00", "20:00"]), ("Empagliflozin", "10 mg", ["08:00"])],
    "stable": [("Levothyroxine", "50 mcg", ["07:00"])],
}
ADHERENCE = {"hypertensive": 0.92, "diabetic": 0.62, "stable": 0.97}


def iso(dt):
    return dt.isoformat()


def session_for(person, register=True):
    s = requests.Session()
    if register:
        s.post(f"{API}/auth/register", json={"name": person["name"], "email": person["email"],
                                             "password": person["password"]}, timeout=30)
    r = s.post(f"{API}/auth/login", json={"email": person["email"], "password": person["password"]}, timeout=30)
    r.raise_for_status()
    return s, r.json()


def backfill_vitals(profile_id, user_id, kind):
    """Days 8-90 of the window, mirroring the distributions used by /api/vitals/simulate."""
    now = datetime.now(timezone.utc)
    docs = []
    for day in range(90, 7, -1):
        drift = (90 - day) / 83
        for hour in (8, 19):
            ts = (now - timedelta(days=day)).replace(hour=hour, minute=random.randint(0, 59))
            base = {
                "heart_rate": round(random.gauss(74, 8)),
                "systolic": round(random.gauss(118, 8)),
                "diastolic": round(random.gauss(76, 6)),
                "glucose": round(random.gauss(100, 14)),
                "spo2": round(min(100, random.gauss(97.5, 1.2)), 1),
                "temperature": round(random.gauss(36.7, 0.3), 1),
            }
            if kind == "hypertensive":
                base["systolic"] = round(random.gauss(128 + 14 * drift, 7))
                base["diastolic"] = round(random.gauss(82 + 7 * drift, 5))
            if kind == "diabetic":
                base["glucose"] = round(random.gauss(135 + 30 * drift, 20))
            docs.append({
                "vital_id": f"vital_{uuid.uuid4().hex[:12]}",
                "user_id": user_id, "profile_id": profile_id, **base, "weight": None,
                "source": "wearable_sim", "recorded_at": iso(ts), "created_at": iso(now),
            })
    db.vitals.insert_many(docs)
    return len(docs)


def seed_medications(session, kind):
    med_ids = []
    for name, dosage, times in MEDS[kind]:
        r = session.post(f"{API}/medications", json={"name": name, "dosage": dosage, "times": times,
                                                     "instructions": "With food", "profile_id": "self"}, timeout=30)
        r.raise_for_status()
        med_ids.append((r.json()["medication_id"], times))
    return med_ids


def seed_dose_logs(session, med_ids, kind):
    rate = ADHERENCE[kind]
    now = datetime.now(timezone.utc)
    logged = 0
    for med_id, times in med_ids:
        for day in range(90):
            date = (now - timedelta(days=day)).strftime("%Y-%m-%d")
            for t in times:
                status = "taken" if random.random() < rate else "missed"
                session.post(f"{API}/medications/{med_id}/dose",
                             json={"time": t, "status": status, "date": date}, timeout=30)
                logged += 1
    return logged


def main():
    print(f"Seeding against {API}")
    doctor_session, doctor = session_for(DOCTOR)
    db.users.update_one({"user_id": doctor["user_id"]},
                        {"$set": {"role": "doctor", "onboarding_completed": True}})
    doctor_session.post(f"{API}/auth/login", json={"email": DOCTOR["email"], "password": DOCTOR["password"]})
    print(f"  doctor {doctor['user_id']}")

    encounters = 0
    for i, person in enumerate(PATIENTS):
        s, u = session_for(person)
        s.post(f"{API}/auth/sharing", json={"enabled": True}, timeout=30)
        s.put(f"{API}/profile/health", json={
            "height": 170 + i * 4, "weight": 72 + i * 6, "date_of_birth": f"19{60 + i * 7}-04-1{i}",
            "chronic_conditions": person["profile"] != "stable",
            "chronic_conditions_details": {"hypertensive": "Hypertension since 2019",
                                           "diabetic": "Type 2 diabetes since 2016",
                                           "stable": ""}[person["profile"]],
            "allergies": i == 1, "allergies_details": "Penicillin" if i == 1 else "",
            "current_medications": True,
            "current_medications_details": ", ".join(m[0] for m in MEDS[person["profile"]]),
            "smoker": i == 0, "physical_activity": i != 1,
        }, timeout=30)

        sim = s.post(f"{API}/vitals/simulate", json={"profile_id": "self"}, timeout=60).json()
        back = backfill_vitals(u["user_id"], u["user_id"], person["profile"])
        meds = seed_medications(s, person["profile"])
        doses = seed_dose_logs(s, meds, person["profile"])
        print(f"  patient {u['user_id']} ({person['profile']}): {sim['inserted'] + back} vitals, "
              f"{len(meds)} meds, {doses} dose logs")

        for offset in (1, 6) if i == 0 else (2,) if i == 1 else (3, 9):
            when = datetime.now(timezone.utc) + timedelta(days=offset)
            r = doctor_session.post(f"{API}/encounters", json={
                "patient_user_id": u["user_id"],
                "scheduled_at": iso(when.replace(hour=9 + offset % 6, minute=0, second=0, microsecond=0)),
                "reason_for_visit": person["reason"],
            }, timeout=30)
            r.raise_for_status()
            encounters += 1

    print(f"  {encounters} encounters created")
    print("Done.")


if __name__ == "__main__":
    if not BASE:
        sys.exit("REACT_APP_BACKEND_URL not found")
    main()
