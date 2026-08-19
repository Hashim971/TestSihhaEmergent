"""One-off backfill: give every existing sharing patient an assigned doctor.

Existing patients go to the seeded doctor (dr.layla@sihha.ai) so her panel is not empty; the admin
account sees every patient regardless of assignment and can reassign from /admin/assignments.

Run once:  cd /app/backend && python migrations/assign_existing_patients.py
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).parent.parent / ".env")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

DEFAULT_DOCTOR_EMAIL = os.environ.get("DEFAULT_ASSIGNED_DOCTOR_EMAIL", "dr.layla@sihha.ai")
doctor = db.users.find_one({"email": DEFAULT_DOCTOR_EMAIL, "role": "doctor"}, {"_id": 0, "user_id": 1, "name": 1})
if not doctor:
    raise SystemExit(f"doctor {DEFAULT_ASSIGNED_DOCTOR_EMAIL} not found")

res = db.users.update_many(
    {"role": "patient", "assigned_doctor_user_id": {"$in": [None, ""]}},
    {"$set": {"assigned_doctor_user_id": doctor["user_id"], "assigned_by": "migration"}},
)
missing = db.users.update_many(
    {"role": "patient", "assigned_doctor_user_id": {"$exists": False}},
    {"$set": {"assigned_doctor_user_id": doctor["user_id"], "assigned_by": "migration"}},
)
print(f"assigned to {doctor['name']}: {res.modified_count + missing.modified_count}")
print("unassigned patients left:",
      db.users.count_documents({"role": "patient", "assigned_doctor_user_id": {"$in": [None, ""]}}))
