# Iteration 22 UI seed/cleanup: TEST_ dependent for omar with 2 high systolic readings; `cleanup` removes everything.
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
    deps = [d["dependent_id"] for d in DB.dependents.find({"user_id": OMAR, "name": {"$regex": "^TEST_"}})]
    sids = [s["chat_session_id"] for s in DB.chat_sessions.find({"profile_id": {"$in": deps}})]
    DB.chat_messages.delete_many({"chat_session_id": {"$in": sids}})
    for col in ("vitals", "alerts", "vital_limits", "vital_trend_notices", "medications", "dose_logs", "chat_sessions",
                "chat_messages", "carts"):
        DB[col].delete_many({"profile_id": {"$in": deps}})
    DB.dependents.delete_many({"dependent_id": {"$in": deps}})
    DB.vital_limits.delete_many({"profile_id": OMAR})
    DB.vital_trend_notices.delete_many({"profile_id": OMAR})
    print("cleaned", deps)
else:
    s = requests.Session()
    s.post(f"{API}/auth/login", json={"email": "omar.patient@sihha.ai", "password": "Patient@123"})
    dep = s.post(f"{API}/dependents", json={"name": "TEST_ Lina", "relation": "child"}).json()["dependent_id"]
    for v in (150, 156):
        s.post(f"{API}/vitals", json={"profile_id": dep, "systolic": v, "source": "TEST_ui"})
    print(dep)
