"""Seed for the hospital finder and pharmacy portal. Idempotent.

Run: cd /app/backend && set -a && . ./.env && set +a && python seed_marketplace_portal.py
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone

import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient

PHARMACIST = ("pharmacist@aldawaa.sihha.ai", "Pharma@123", "Huda Al Dawaa")
SOLO_PATIENT = ("solo.patient@sihha.ai", "Patient@123", "Faisal Standalone")
LISTINGS = {
    "Al Noor Specialist Hospital": {"about": "Multi-specialty hospital with same-week cardiology and internal medicine visits.",
                                    "specialties": ["Internal Medicine", "Cardiology", "Endocrinology"]},
    "Jeddah Family Clinics": {"about": "Family medicine clinics across Jeddah for adults and children.",
                              "specialties": ["Family Medicine", "Pediatrics"]},
}


def iso():
    return datetime.now(timezone.utc).isoformat()


def pw(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    for name, listing in LISTINGS.items():
        r = await db.accounts.update_one({"name": name}, {"$set": {"listed_in_app": True, **listing}})
        print(name, "listed" if r.matched_count else "NOT FOUND")

    pharmacy = await db.pharmacies.find_one({"name_en": "Al Dawaa Pharmacy"}, {"_id": 0, "pharmacy_id": 1})
    email, password, name = PHARMACIST
    await db.users.update_one({"email": email}, {"$set": {
        "name": name, "password_hash": pw(password), "role": "pharmacist",
        "pharmacy_id": pharmacy["pharmacy_id"] if pharmacy else None, "pharmacy_role": "owner",
        "onboarding_completed": True, "sharing_enabled": False, "account_id": None},
        "$setOnInsert": {"user_id": f"user_{uuid.uuid4().hex[:12]}", "created_at": iso(), "picture": None,
                         "clinician_requested": False, "assigned_doctor_user_id": None}}, upsert=True)
    print("pharmacist ->", pharmacy)

    email, password, name = SOLO_PATIENT
    await db.users.update_one({"email": email}, {"$set": {
        "name": name, "password_hash": pw(password), "role": "patient", "onboarding_completed": True,
        "sharing_enabled": True, "account_id": None, "assigned_doctor_user_id": None},
        "$setOnInsert": {"user_id": f"user_{uuid.uuid4().hex[:12]}", "created_at": iso(), "picture": None,
                         "clinician_requested": False}}, upsert=True)
    print("solo patient ready")

    jeddah = await db.accounts.find_one({"name": "Jeddah Family Clinics"}, {"_id": 0, "account_id": 1})
    await db.users.update_one({"email": "dr.khalid@sihha.ai"}, {"$set": {
        "name": "Dr. Khalid Al Harbi", "password_hash": pw("Doctor@123"), "role": "doctor",
        "specialty": "Family Medicine", "clinic": "Jeddah Family Clinics — Al Rawdah", "city": "Jeddah",
        "account_id": jeddah["account_id"] if jeddah else None, "account_role": "member", "onboarding_completed": True},
        "$setOnInsert": {"user_id": f"user_{uuid.uuid4().hex[:12]}", "created_at": iso(), "picture": None,
                         "clinician_requested": False, "sharing_enabled": False, "assigned_doctor_user_id": None}},
        upsert=True)
    khalid = await db.users.find_one({"email": "dr.khalid@sihha.ai"}, {"_id": 0, "user_id": 1})
    await db.doctor_availability.update_one({"doctor_user_id": khalid["user_id"]}, {"$set": {
        "doctor_user_id": khalid["user_id"], "slot_minutes": 30, "tz_offset_minutes": 180, "blocked_dates": [],
        "weekly": [{"weekday": d, "start": "09:00", "end": "13:00"} for d in (6, 0, 1, 2, 3)], "updated_at": iso()}},
        upsert=True)
    print("dr.khalid ready at", jeddah)


asyncio.run(main())
