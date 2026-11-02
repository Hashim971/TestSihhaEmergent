# Iteration 21 UI seed/cleanup: completed Al Noor visit for omar (rating dialog), `cleanup` arg removes everything.
import sys
import requests
from pymongo import MongoClient

def _env(path, key):
    for line in open(path):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')

API = _env("/app/frontend/.env", "REACT_APP_BACKEND_URL").rstrip("/") + "/api"
DB = MongoClient(_env("/app/backend/.env", "MONGO_URL"))[_env("/app/backend/.env", "DB_NAME")]
OMAR = "user_020593feb10e"

if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
    ids = [e["encounter_id"] for e in DB.encounters.find({"reason_for_visit": "TEST_ ui visit"})]
    DB.hospital_ratings.delete_many({"encounter_id": {"$in": ids}})
    DB.alerts.delete_many({"encounter_id": {"$in": ids}})
    DB.encounters.delete_many({"encounter_id": {"$in": ids}})
    DB.vitals.delete_many({"source": "TEST_ui"})
    DB.alerts.delete_many({"type": "vital_trend", "user_id": OMAR})
    DB.alerts.delete_many({"user_id": OMAR, "type": "vital", "created_at": {"$gte": "2026-11-02"}})
    DB.vital_trend_notices.delete_many({"profile_id": OMAR})
    DB.vital_limits.delete_many({"profile_id": OMAR})
    DB.catalog_items.delete_many({"sku": {"$regex": "^TEST_"}})
    print("cleaned", ids)
else:
    s = requests.Session()
    s.post(f"{API}/auth/login", json={"email": "dr.layla@sihha.ai", "password": "Doctor@123"})
    r = s.post(f"{API}/encounters", json={"patient_user_id": OMAR, "reason_for_visit": "TEST_ ui visit"})
    eid = r.json()["encounter_id"]
    print(s.patch(f"{API}/encounters/{eid}", json={"status": "completed"}).status_code, eid)
