"""One-off backfill: doctor sharing is on by default, so existing patients opt in retroactively.

Run once:  cd /app/backend && python migrations/enable_sharing_default.py
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).parent.parent / ".env")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

res = db.users.update_many(
    {"role": "patient", "sharing_enabled": {"$ne": True}}, {"$set": {"sharing_enabled": True}}
)
print(f"patients switched to sharing: {res.modified_count}")
print(f"patients now sharing: {db.users.count_documents({'role': 'patient', 'sharing_enabled': True})}")
