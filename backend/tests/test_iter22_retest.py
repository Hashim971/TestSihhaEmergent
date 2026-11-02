# Iteration 22 retest: profile_key IDOR fix + dependent regression, partial vital limits, top_rated unrounded,
# CSV import 'active' column, no_data trends + Arabic copy, one-sided limit validation, reviews 404 for unlisted.
import io
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


def _env(path, key):
    for line in open(path):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


MONGO = MongoClient(_env("/app/backend/.env", "MONGO_URL"))[_env("/app/backend/.env", "DB_NAME")]
AL_NOOR, JEDDAH = "ACC-12AFFE", "ACC-2BC6ED"
LAYLA = "user_b1000ae5aad6"
AL_DAWAA = "pharm_744d6031f418"
CREATED = {"users": [], "deps": [], "ratings": [], "accounts_restore": {}}


def login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return s


def make_patient(tag):
    email = f"test_{tag}_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"name": f"TEST_ {tag} Patient", "email": email, "password": "Test@1234"})
    assert r.status_code == 200, r.text
    uid = MONGO.users.find_one({"email": email})["user_id"]
    CREATED["users"].append(uid)
    MONGO.users.update_one({"user_id": uid}, {"$set": {"assigned_doctor_user_id": LAYLA, "account_id": AL_NOOR,
                                                       "account_role": "member", "sharing_enabled": True}})
    return login(email, "Test@1234"), uid


@pytest.fixture(scope="module")
def a():
    return make_patient("a22")


@pytest.fixture(scope="module")
def b():
    return make_patient("b22")


@pytest.fixture(scope="module")
def layla():
    return login("dr.layla@sihha.ai", "Doctor@123")


@pytest.fixture(scope="module")
def pharm():
    return login("pharmacist@aldawaa.sihha.ai", "Pharma@123")


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    ids = CREATED["users"] + CREATED["deps"]
    sids = [s["chat_session_id"] for s in MONGO.chat_sessions.find({"user_id": {"$in": CREATED["users"]}})]
    MONGO.chat_messages.delete_many({"chat_session_id": {"$in": sids}})
    for col in ("vitals", "alerts", "vital_limits", "vital_trend_notices", "medications", "dose_logs",
                "chat_sessions", "carts", "orders"):
        MONGO[col].delete_many({"$or": [{"user_id": {"$in": ids}}, {"profile_id": {"$in": ids}}]})
    MONGO.dependents.delete_many({"user_id": {"$in": CREATED["users"]}})
    MONGO.hospital_ratings.delete_many({"rating_id": {"$in": CREATED["ratings"]}})
    MONGO.catalog_items.delete_many({"pharmacy_id": AL_DAWAA, "sku": {"$regex": "^TEST_"}})
    for acc, fields in CREATED["accounts_restore"].items():
        MONGO.accounts.update_one({"account_id": acc}, {"$set": fields})
    MONGO.users.delete_many({"user_id": {"$in": CREATED["users"]}})


# ---------- (1) IDOR fix ----------
class TestProfileIdor:
    @pytest.mark.parametrize("method,path,kind", [
        ("get", "/vitals", "q"), ("get", "/vitals/latest", "q"), ("get", "/vitals/trends", "q"),
        ("get", "/medications", "q"), ("get", "/medications/schedule/today", "q"),
        ("get", "/medications/adherence/stats", "q"), ("get", "/pharmacy/orders", "q"), ("get", "/pharmacy/cart", "q"),
        ("get", "/pharmacy/refills", "q"), ("get", "/pharmacy/prescriptions", "q"), ("get", "/prescriptions", "q"),
        ("post", "/vitals", "b"), ("post", "/vitals/simulate", "b"), ("post", "/chat/sessions", "b"),
        ("post", "/medications", "b"),
    ])
    def test_other_users_profile_404(self, a, b, method, path, kind):
        sa, uid_a = a
        sb, _ = b
        if kind == "q":
            r = getattr(sb, method)(f"{API}{path}", params={"profile_id": uid_a})
        else:
            body = {"profile_id": uid_a, "systolic": 150, "name": "TEST_ med", "dosage": "1", "times": ["08:00"],
                    "frequency": "daily"}
            r = getattr(sb, method)(f"{API}{path}", json=body)
        assert r.status_code == 404, f"{method} {path}: {r.status_code} {r.text[:200]}"
        assert r.json().get("detail") == "Profile not found"

    def test_no_write_into_other(self, a):
        _, uid_a = a
        assert MONGO.vitals.count_documents({"profile_id": uid_a}) == 0

    def test_self_and_own_id(self, a):
        sa, uid_a = a
        assert sa.post(f"{API}/vitals", json={"profile_id": "self", "systolic": 120}).status_code == 200
        r = sa.get(f"{API}/vitals", params={"profile_id": uid_a})
        assert r.status_code == 200 and len(r.json()) == 1
        assert sa.get(f"{API}/vitals").json()[0]["systolic"] == 120

    def test_dependent_regression(self, a, b):
        sa, uid_a = a
        sb, _ = b
        r = sa.post(f"{API}/dependents", json={"name": "TEST_ Kid", "relation": "child", "gender": "female"})
        assert r.status_code == 200, r.text
        dep = r.json()["dependent_id"]
        CREATED["deps"].append(dep)
        for v in (150, 152):
            r = sa.post(f"{API}/vitals", json={"profile_id": dep, "systolic": v})
            assert r.status_code == 200 and r.json()["profile_id"] == dep
        assert len(sa.get(f"{API}/vitals", params={"profile_id": dep}).json()) == 2
        assert sa.get(f"{API}/vitals/latest", params={"profile_id": dep}).json()["systolic"]["value"] == 152
        t = {x["metric"]: x for x in sa.get(f"{API}/vitals/trends", params={"profile_id": dep}).json()["trends"]}
        assert t["systolic"]["status"] == "above_limit"
        al = MONGO.alerts.find_one({"profile_id": dep, "type": "vital_trend"})
        assert al and al["message"].startswith("TEST_ Kid:")
        r = sa.post(f"{API}/medications", json={"profile_id": dep, "name": "TEST_ Syrup", "dosage": "5 ml",
                                               "times": ["08:00"], "frequency": "daily"})
        assert r.status_code == 200, r.text
        meds = sa.get(f"{API}/medications", params={"profile_id": dep}).json()
        assert [m["name"] for m in meds] == ["TEST_ Syrup"]
        assert sa.get(f"{API}/medications/schedule/today", params={"profile_id": dep}).status_code == 200
        r = sa.post(f"{API}/chat/sessions", json={"profile_id": dep})
        assert r.status_code == 200 and r.json()["profile_id"] == dep
        assert sa.get(f"{API}/pharmacy/orders", params={"profile_id": dep}).status_code == 200
        assert sa.get(f"{API}/pharmacy/cart", params={"profile_id": dep}).status_code == 200
        # self data isolated from dependent
        assert len(sa.get(f"{API}/medications").json()) == 0
        # another user cannot use A's dependent
        assert sb.get(f"{API}/vitals", params={"profile_id": dep}).status_code == 404
        assert sb.post(f"{API}/vitals", json={"profile_id": dep, "systolic": 100}).status_code == 404
        # deleting the dependent revokes access
        sa.delete(f"{API}/dependents/{dep}")
        assert sa.get(f"{API}/vitals", params={"profile_id": dep}).status_code == 404


# ---------- (5) no_data + Arabic ----------
class TestTrendsCopy:
    def test_no_data_and_ar(self, b):
        sb, _ = b
        d = sb.get(f"{API}/vitals/trends").json()
        for t in d["trends"]:
            assert t["status"] == "no_data" and t["severity"] is None
            assert t["label_ar"] and t["message_ar"] and t["readings"] == 0
        sb.post(f"{API}/vitals", json={"glucose": 60})
        sb.post(f"{API}/vitals", json={"glucose": 61})
        g = {x["metric"]: x for x in sb.get(f"{API}/vitals/trends").json()["trends"]}["glucose"]
        assert g["status"] == "below_limit" and "سكر الدم" in g["message_ar"]


# ---------- (2)(6) limits ----------
class TestLimits:
    def test_partial_limits_stay_standard(self, layla, a):
        _, uid = a
        r = layla.put(f"{API}/doctor/patients/{uid}/vital-limits",
                      json={"systolic_max": 160, "systolic_min": None, "diastolic_max": None, "diastolic_min": None,
                            "glucose_max": None, "glucose_min": None, "note": "TEST_"})
        assert r.status_code == 200, r.text
        t = {x["metric"]: x for x in r.json()["trends"]}
        assert t["systolic"]["limit_source"] == "doctor" and t["systolic"]["limit"] == {"max": 160, "min": 90}
        assert t["diastolic"]["limit_source"] == "standard" and t["glucose"]["limit_source"] == "standard"

    @pytest.mark.parametrize("body", [{"diastolic_max": 60}, {"systolic_min": 120, "systolic_max": None},
                                      {"glucose_max": 90, "glucose_min": 100}])
    def test_one_sided_invalid_422(self, layla, a, body):
        _, uid = a
        r = layla.put(f"{API}/doctor/patients/{uid}/vital-limits", json=body)
        if body == {"systolic_min": 120, "systolic_max": None}:
            assert r.status_code == 200  # 120 < standard max 140 -> valid
        else:
            assert r.status_code == 422, r.text

    def test_reset(self, layla, a):
        _, uid = a
        r = layla.delete(f"{API}/doctor/patients/{uid}/vital-limits")
        assert r.status_code == 200 and r.json()["limits"] is None


# ---------- (3)(7) ratings ----------
def _rating(acc, stars):
    rid = f"rate_TEST_{uuid.uuid4().hex[:8]}"
    MONGO.hospital_ratings.insert_one({"rating_id": rid, "encounter_id": f"enc_{rid}", "account_id": acc, "stars": stars,
                                       "comment": "", "hidden": False, "patient_user_id": "x",
                                       "updated_at": "2026-01-01"})
    CREATED["ratings"].append(rid)


class TestRatings:
    def test_top_rated_unrounded(self, a):
        sa, _ = a
        st = list(MONGO.hospital_ratings.aggregate([{"$match": {"account_id": JEDDAH, "hidden": False}},
                                                    {"$group": {"_id": None, "s": {"$sum": "$stars"}, "n": {"$sum": 1}}}]))
        s0, n0 = (st[0]["s"], st[0]["n"]) if st else (0, 0)
        # Pad Jeddah with ratings so the average is exactly 4.45 (needs total sum/n = 4.45 -> 20 ratings, sum 89)
        target_n = max(20, ((n0 // 20) + 1) * 20)
        need_sum = int(4.45 * target_n + 0.5) - s0
        k = target_n - n0
        assert k * 1 <= need_sum <= k * 5, "cannot construct 4.45 with existing ratings"
        stars = [5] * k
        excess = 5 * k - need_sum
        i = 0
        while excess > 0:
            dec = min(4, excess)
            stars[i] -= dec
            excess -= dec
            i += 1
        for s in stars:
            _rating(JEDDAH, s)
        card = next(c for c in sa.get(f"{API}/care/hospitals").json() if c["account_id"] == JEDDAH)
        assert card["rating_count"] == target_n and card["rating_avg"] == 4.5, card
        assert card["top_rated"] is False, card
        r = sa.get(f"{API}/care/hospitals/{JEDDAH}/reviews").json()
        assert list(r["breakdown"].keys()) == ["5", "4", "3", "2", "1"]
        # one more 5 pushes to >= 4.5 raw? (sum+5)/(n+1) = 94/21 = 4.476 -> still no badge; add enough 5s
        while True:
            _rating(JEDDAH, 5)
            st = MONGO.hospital_ratings.count_documents({"account_id": JEDDAH, "hidden": False})
            tot = sum(x["stars"] for x in MONGO.hospital_ratings.find({"account_id": JEDDAH, "hidden": False}))
            if tot / st >= 4.5:
                break
        card = next(c for c in sa.get(f"{API}/care/hospitals").json() if c["account_id"] == JEDDAH)
        assert card["top_rated"] is True

    def test_reviews_404_unlisted_suspended(self, a):
        sa, _ = a
        acc = MONGO.accounts.find_one({"account_id": JEDDAH})
        CREATED["accounts_restore"][JEDDAH] = {"listed_in_app": acc.get("listed_in_app"), "status": acc.get("status")}
        assert sa.get(f"{API}/care/hospitals/{JEDDAH}/reviews").status_code == 200
        assert sa.get(f"{API}/care/hospitals/{JEDDAH.lower()}/reviews").status_code == 200
        MONGO.accounts.update_one({"account_id": JEDDAH}, {"$set": {"listed_in_app": False}})
        assert sa.get(f"{API}/care/hospitals/{JEDDAH}/reviews").status_code == 404
        MONGO.accounts.update_one({"account_id": JEDDAH}, {"$set": {"listed_in_app": True, "status": "suspended"}})
        assert sa.get(f"{API}/care/hospitals/{JEDDAH}/reviews").status_code == 404
        MONGO.accounts.update_one({"account_id": JEDDAH}, {"$set": CREATED["accounts_restore"][JEDDAH]})
        assert sa.get(f"{API}/care/hospitals/ACC-NOPE00/reviews").status_code == 404


# ---------- (4) CSV active ----------
HDR = ("sku,name_en,name_ar,generic_name,form,strength,category,requires_prescription,sfda_registration_number,"
       "days_supply,pack_size,price_sar,stock_status")


def _upload(sess, text):
    return sess.post(f"{API}/pharmacy-portal/catalog/import", files={"file": ("p.csv", io.BytesIO(text.encode()), "text/csv")})


def _items(pharm):
    return {i["sku"]: i for i in pharm.get(f"{API}/pharmacy-portal/catalog").json()["items"]}


class TestCsvActive:
    def test_template_has_active(self, pharm):
        lines = pharm.get(f"{API}/pharmacy-portal/catalog/template.csv").content.decode("utf-8-sig").splitlines()
        assert lines[0].split(",")[-1] == "active" and lines[1].endswith(",yes")

    def test_active_preserved_and_respected(self, pharm):
        r = _upload(pharm, HDR + ",active\nTEST_A1,TEST_ A1,,,,,otc,no,,,,5,in_stock,no\nTEST_A2,TEST_ A2,,,,,otc,no,,,,5,in_stock,\n")
        assert r.status_code == 200 and r.json()["created"] == 2, r.text
        it = _items(pharm)
        assert it["TEST_A1"]["active"] is False and it["TEST_A2"]["active"] is True
        # empty 'active' keeps existing False
        _upload(pharm, HDR + ",active\nTEST_A1,TEST_ A1 v2,,,,,otc,no,,,,6,in_stock,\n")
        assert _items(pharm)["TEST_A1"]["active"] is False
        # missing column keeps existing False
        r = _upload(pharm, HDR + "\nTEST_A1,TEST_ A1 v3,,,,,otc,no,,,,7,in_stock\n")
        assert r.json()["updated"] == 1
        it = _items(pharm)["TEST_A1"]
        assert it["active"] is False and it["price_sar"] == 7.0
        # explicit yes re-activates
        _upload(pharm, HDR + ",active\nTEST_A1,TEST_ A1,,,,,otc,no,,,,7,in_stock,yes\n")
        assert _items(pharm)["TEST_A1"]["active"] is True
        # explicit no deactivates an active one
        _upload(pharm, HDR + ",active\nTEST_A2,TEST_ A2,,,,,otc,no,,,,5,in_stock,No\n")
        assert _items(pharm)["TEST_A2"]["active"] is False

    def test_active_invalid_value(self, pharm):
        r = _upload(pharm, HDR + ",active\nTEST_A3,TEST_ A3,,,,,otc,no,,,,5,in_stock,maybe\n")
        d = r.json()
        # report behaviour: invalid value should be a row error rather than silently 'inactive'
        print("invalid active ->", d, _items(pharm).get("TEST_A3", {}).get("active"))
        assert d["errors"] or d["created"] == 0, f"'maybe' silently accepted: {d}"
