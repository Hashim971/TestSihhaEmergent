# Cleanup for iteration 15 QA data (QA-prefixed accounts, qa.* users, demo requests, spoofcheck lockouts)
from pymongo import MongoClient
from dotenv import dotenv_values

env = dotenv_values('/app/backend/.env')
db = MongoClient(env["MONGO_URL"])[env["DB_NAME"]]
qa_accounts = [a["account_id"] for a in db.accounts.find({"name": {"$regex": "^QA "}}, {"account_id": 1})]
print("QA accounts:", qa_accounts)
print("users removed:", db.users.delete_many({"$or": [
    {"account_id": {"$in": qa_accounts}},
    {"email": {"$regex": r"^(qa\.|delivered\+qa)"}}]}).deleted_count)
print("imported removed:", db.imported_records.delete_many({"account_id": {"$in": qa_accounts}}).deleted_count)
print("accounts removed:", db.accounts.delete_many({"account_id": {"$in": qa_accounts}}).deleted_count)
print("demo removed:", db.demo_requests.delete_many({"email": {"$regex": "^qa\\."}}).deleted_count)
print("lockouts removed:", db.login_attempts.delete_many({"identifier": {"$regex": "spoofcheck-"}}).deleted_count)
print("flags:", {f["key"]: f["enabled"] for f in db.feature_flags.find({}, {"_id": 0})})
print("accounts left:", [(a["account_id"], a["name"], a.get("features"), a.get("custom_domain")) for a in db.accounts.find({}, {"_id": 0})])
print("real-user lockouts:", list(db.login_attempts.find({"identifier": {"$regex": "sihha.ai"}}, {"_id": 0})))
