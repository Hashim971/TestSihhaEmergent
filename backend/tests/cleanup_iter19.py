# Cleanup of iteration 19 UI test data (TEST_ pharmacy, users, orders, encounters, probe report). Idempotent.
import os
from pymongo import MongoClient
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
SOLO = db.users.find_one({"email": "solo.patient@sihha.ai"})["user_id"]
test_ph = [p["pharmacy_id"] for p in db.pharmacies.find({"name_en": {"$regex": "^TEST_"}}, {"pharmacy_id": 1})]
test_users = [u["user_id"] for u in db.users.find({"$or": [{"email": {"$regex": "^test_(ui_)?(pharm|staff)"}},
                                                             {"pharmacy_id": {"$in": test_ph}}]}, {"user_id": 1})]
print("pharmacies", db.pharmacies.delete_many({"pharmacy_id": {"$in": test_ph}}).deleted_count)
print("catalog", db.catalog_items.delete_many({"pharmacy_id": {"$in": test_ph}}).deleted_count)
print("spr", db.sponsorship_requests.delete_many({"pharmacy_id": {"$in": test_ph}}).deleted_count)
print("apps", db.pharmacy_applications.delete_many({"pharmacy_name": {"$regex": "^TEST_"}}).deleted_count)
print("users", db.users.delete_many({"user_id": {"$in": test_users}}).deleted_count)
db.password_reset_tokens.delete_many({"user_id": {"$in": test_users}})
orders = [o["order_id"] for o in db.orders.find({"user_id": SOLO}, {"order_id": 1})]
db.order_messages.delete_many({"order_id": {"$in": orders}})
db.alerts.delete_many({"order_id": {"$in": orders}})
print("orders", db.orders.delete_many({"order_id": {"$in": orders}}).deleted_count)
encs = [e["encounter_id"] for e in db.encounters.find({"$or": [{"patient_user_id": SOLO},
        {"reason_for_visit": {"$regex": "^TEST_"}}]}, {"encounter_id": 1})]
db.care_grants.delete_many({"$or": [{"encounter_id": {"$in": encs}}, {"patient_user_id": SOLO}]})
db.alerts.delete_many({"encounter_id": {"$in": encs}})
print("encounters", db.encounters.delete_many({"encounter_id": {"$in": encs}}).deleted_count)
rep = db.health_reports.find_one({"report_id": "report_4114e629ecc7"})
if rep:
    db.chat_messages.delete_many({"chat_session_id": rep["chat_session_id"]})
    db.chat_sessions.delete_many({"chat_session_id": rep["chat_session_id"]})
    db.health_reports.delete_one({"report_id": "report_4114e629ecc7"})
db.carts.delete_many({"user_id": SOLO})
db.alerts.delete_many({"user_id": SOLO})
db.users.update_one({"user_id": SOLO}, {"$set": {"account_id": None, "account_role": None, "assigned_doctor_user_id": None}})
acc = db.accounts.find_one({"account_id": "ACC-12AFFE"})
db.accounts.update_one({"account_id": "ACC-12AFFE"}, {"$set": {"about": (acc.get("about") or "").strip()}})
db.accounts.update_one({"account_id": "ACC-A84A0F"}, {"$set": {"listed_in_app": False}})
db.login_attempts.delete_many({"identifier": {"$regex": "^pharmacy-apply:"}})
print("omar:", db.users.find_one({"email": "omar.patient@sihha.ai"}, {"_id": 0, "account_id": 1, "assigned_doctor_user_id": 1}))
print("solo:", db.users.find_one({"user_id": SOLO}, {"_id": 0, "account_id": 1, "assigned_doctor_user_id": 1}))
