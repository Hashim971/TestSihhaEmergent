# Iteration 21: vitals trend warnings + doctor limits, hospital ratings + moderation + Find Care sort,
# pharmacy portal products (CSV template/import, add/edit), licences, pharmacy application licences.
import io
import os
import uuid
from datetime import datetime, timedelta, timezone

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
LAYLA, KHALID = "user_b1000ae5aad6", "user_af7cc0803ba9"
AL_DAWAA = "pharm_744d6031f418"
CREATED = {"users": [], "encounters": [], "skus": [], "apps": [], "pharmacies": []}
STATE = {}


def login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return s


def make_patient(tag):
    email = f"test_{tag}_{uuid.uuid4().hex[:6]}@example.com"
    s = requests.Session()
    r = s.post(f"{API}/auth/register", json={"name": f"TEST_ {tag} Patient", "email": email, "password": "Test@1234"})
    assert r.status_code == 200, r.text
    uid = MONGO.users.find_one({"email": email})["user_id"]
    CREATED["users"].append(uid)
    MONGO.users.update_one({"user_id": uid}, {"$set": {"assigned_doctor_user_id": LAYLA, "account_id": AL_NOOR,
                                                       "account_role": "member", "sharing_enabled": True}})
    return login(email, "Test@1234"), uid


@pytest.fixture(scope="module")
def admin():
    return login("admin@sihha.ai", "Admin@123")


@pytest.fixture(scope="module")
def layla():
    return login("dr.layla@sihha.ai", "Doctor@123")


@pytest.fixture(scope="module")
def khalid():
    return login("dr.khalid@sihha.ai", "Doctor@123")


@pytest.fixture(scope="module")
def pharm():
    return login("pharmacist@aldawaa.sihha.ai", "Pharma@123")


@pytest.fixture(scope="module")
def p1():
    return make_patient("p1")


@pytest.fixture(scope="module")
def p2():
    return make_patient("p2")


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    uids = CREATED["users"]
    for col in ("vitals", "alerts", "vital_limits", "vital_trend_notices"):
        MONGO[col].delete_many({"$or": [{"user_id": {"$in": uids}}, {"profile_id": {"$in": uids}}]})
    MONGO.hospital_ratings.delete_many({"encounter_id": {"$in": CREATED["encounters"]}})
    MONGO.encounters.delete_many({"encounter_id": {"$in": CREATED["encounters"]}})
    MONGO.catalog_items.delete_many({"pharmacy_id": AL_DAWAA, "sku": {"$regex": "^TEST_"}})
    MONGO.pharmacy_applications.delete_many({"application_id": {"$in": CREATED["apps"]}})
    MONGO.pharmacies.delete_many({"pharmacy_id": {"$in": CREATED["pharmacies"]}})
    MONGO.users.delete_many({"user_id": {"$in": uids}})
    MONGO.users.update_one({"email": "pharmacist@aldawaa.sihha.ai"}, {"$set": {"pharmacy_role": "owner"}})
    MONGO.login_attempts.delete_many({"identifier": {"$regex": "^pharmacy-apply:"}})


# ---------- Vitals trends ----------
class TestVitalTrends:
    def test_trends_shape_empty(self, p1):
        s, _ = p1
        r = s.get(f"{API}/vitals/trends")
        assert r.status_code == 200
        d = r.json()
        metrics = {t["metric"]: t for t in d["trends"]}
        assert set(metrics) == {"systolic", "diastolic", "glucose"}
        for t in d["trends"]:
            for k in ("status", "message", "limit", "limit_source", "recent_avg", "previous_avg", "change", "series"):
                assert k in t
            assert t["status"] == "ok" and t["limit_source"] == "standard"
        assert metrics["systolic"]["limit"] == {"max": 140, "min": 90}
        assert metrics["glucose"]["limit"] == {"max": 126, "min": 70}

    def test_above_limit_single_alert(self, p1):
        s, uid = p1
        for v in (150, 155):
            assert s.post(f"{API}/vitals", json={"systolic": v, "diastolic": 80}).status_code == 200
        t = {x["metric"]: x for x in s.get(f"{API}/vitals/trends").json()["trends"]}
        assert t["systolic"]["status"] == "above_limit", t["systolic"]
        assert t["diastolic"]["status"] == "ok"
        assert MONGO.alerts.count_documents({"user_id": uid, "type": "vital_trend", "metric": "systolic"}) == 1
        assert s.post(f"{API}/vitals", json={"systolic": 160}).status_code == 200
        assert MONGO.alerts.count_documents({"user_id": uid, "type": "vital_trend", "metric": "systolic"}) == 1
        assert MONGO.vital_trend_notices.count_documents({"profile_id": uid}) == 1
        alerts = s.get(f"{API}/alerts").json()
        rows = alerts if isinstance(alerts, list) else alerts.get("alerts", alerts.get("items", []))
        assert any(a.get("type") == "vital_trend" for a in rows)

    def test_below_limit_glucose(self, p1):
        s, uid = p1
        for v in (60, 62):
            s.post(f"{API}/vitals", json={"glucose": v})
        t = {x["metric"]: x for x in s.get(f"{API}/vitals/trends").json()["trends"]}
        assert t["glucose"]["status"] == "below_limit"

    def test_rising_trend(self, p2):
        s, uid = p2
        now = datetime.now(timezone.utc)
        for d, v in ((10, 120), (9, 121), (3, 132), (2, 133), (1, 134)):
            s.post(f"{API}/vitals", json={"systolic": v, "recorded_at": (now - timedelta(days=d)).isoformat()})
        t = {x["metric"]: x for x in s.get(f"{API}/vitals/trends").json()["trends"]}["systolic"]
        assert t["status"] == "rising", t
        assert t["previous_avg"] == 120.5 and t["recent_avg"] == 133.0 and t["change"] == 12.5
        assert len(t["series"]) == 5


# ---------- Doctor vital limits ----------
class TestDoctorLimits:
    def test_doctor_trends_and_limits(self, layla, p1):
        _, uid = p1
        r = layla.get(f"{API}/doctor/patients/{uid}/vital-trends")
        assert r.status_code == 200
        r = layla.put(f"{API}/doctor/patients/{uid}/vital-limits",
                      json={"systolic_max": 170, "systolic_min": 95, "note": "TEST_ limits"})
        assert r.status_code == 200, r.text
        t = {x["metric"]: x for x in r.json()["trends"]}
        assert t["systolic"]["limit_source"] == "doctor" and t["systolic"]["limit"]["max"] == 170
        assert t["systolic"]["status"] != "above_limit"
        assert t["diastolic"]["limit_source"] == "standard"
        assert r.json()["limits"]["note"] == "TEST_ limits"
        # patient sees doctor limits
        pt = {x["metric"]: x for x in p1[0].get(f"{API}/vitals/trends").json()["trends"]}
        assert pt["systolic"]["limit_source"] == "doctor"

    def test_min_ge_max_422(self, layla, p1):
        _, uid = p1
        r = layla.put(f"{API}/doctor/patients/{uid}/vital-limits", json={"systolic_max": 110, "systolic_min": 115})
        assert r.status_code == 422

    def test_out_of_bounds_422(self, layla, p1):
        _, uid = p1
        assert layla.put(f"{API}/doctor/patients/{uid}/vital-limits", json={"systolic_max": 500}).status_code == 422

    def test_reset(self, layla, p1):
        _, uid = p1
        r = layla.delete(f"{API}/doctor/patients/{uid}/vital-limits")
        assert r.status_code == 200
        t = {x["metric"]: x for x in r.json()["trends"]}
        assert t["systolic"]["limit_source"] == "standard" and t["systolic"]["status"] == "above_limit"
        assert r.json()["limits"] is None

    def test_no_access_403(self, khalid, p1):
        _, uid = p1
        assert khalid.get(f"{API}/doctor/patients/{uid}/vital-trends").status_code == 403
        assert khalid.put(f"{API}/doctor/patients/{uid}/vital-limits", json={"systolic_max": 150}).status_code == 403
        assert khalid.delete(f"{API}/doctor/patients/{uid}/vital-limits").status_code == 403

    def test_patient_cannot_set_limits(self, p1):
        s, uid = p1
        assert s.put(f"{API}/doctor/patients/{uid}/vital-limits", json={"systolic_max": 150}).status_code == 403

    def test_trends_profile_id_idor(self, p2, p1):
        """Another patient should NOT read p1's trends via profile_id."""
        s2, _ = p2
        _, uid1 = p1
        r = s2.get(f"{API}/vitals/trends", params={"profile_id": uid1})
        readings = sum(t["readings"] for t in r.json().get("trends", [])) if r.status_code == 200 else 0
        assert r.status_code in (403, 404) or readings == 0, f"IDOR: p2 sees {readings} readings of p1"


# ---------- Ratings ----------
def _encounter(doc_sess, uid):
    r = doc_sess.post(f"{API}/encounters", json={"patient_user_id": uid, "reason_for_visit": "TEST_ visit"})
    assert r.status_code == 200, r.text
    CREATED["encounters"].append(r.json()["encounter_id"])
    return r.json()["encounter_id"]


class TestRatings:
    def test_rate_flow(self, layla, p1, p2):
        s, uid = p1
        eid = _encounter(layla, uid)
        assert s.post(f"{API}/encounters/{eid}/rating", json={"stars": 5}).status_code == 409
        r = layla.patch(f"{API}/encounters/{eid}", json={"status": "completed"})
        assert r.status_code == 200 and r.json()["account_id"] == AL_NOOR
        assert MONGO.alerts.count_documents({"user_id": uid, "type": "rating_request", "encounter_id": eid}) == 1
        v = s.get(f"{API}/my-visits").json()
        row = next(x for x in v["past"] if x["encounter_id"] == eid)
        assert row["can_rate"] is True and row["my_rating"] is None
        # other patient -> 404
        assert p2[0].post(f"{API}/encounters/{eid}/rating", json={"stars": 1}).status_code == 404
        assert s.post(f"{API}/encounters/{eid}/rating", json={"stars": 6}).status_code == 422
        r = s.post(f"{API}/encounters/{eid}/rating", json={"stars": 4, "comment": "TEST_ good"})
        assert r.status_code == 200
        rid = r.json()["rating_id"]
        r2 = s.post(f"{API}/encounters/{eid}/rating", json={"stars": 5, "comment": "TEST_ great"})
        assert r2.json()["rating_id"] == rid
        assert MONGO.hospital_ratings.count_documents({"encounter_id": eid}) == 1
        row = next(x for x in s.get(f"{API}/my-visits").json()["past"] if x["encounter_id"] == eid)
        assert row["my_rating"]["stars"] == 5 and "patient_user_id" not in row["my_rating"]
        STATE["rating_id"], STATE["eid"] = rid, eid

    def test_reviews_public(self, p2):
        r = p2[0].get(f"{API}/care/hospitals/{AL_NOOR}/reviews")
        assert r.status_code == 200
        d = r.json()
        assert d["count"] >= 1 and set(d["breakdown"]) == {"1", "2", "3", "4", "5"}
        assert any(x["comment"] == "TEST_ great" for x in d["reviews"])
        assert all("patient_user_id" not in x for x in d["reviews"])
        mine = next(x for x in d["reviews"] if x["comment"] == "TEST_ great")
        assert mine["patient_display"] == "TEST_ P."

    def test_find_care_stats_and_sort(self, p2):
        s, _ = p2
        cards = s.get(f"{API}/care/hospitals").json()
        assert cards[0]["is_my_hospital"] is True
        noor = next(c for c in cards if c["account_id"] == AL_NOOR)
        assert noor["rating_count"] >= 1 and noor["rating_avg"] is not None and "trust_score" in noor
        others = [c for c in cards if not c["is_my_hospital"]]
        assert [c["trust_score"] for c in others] == sorted([c["trust_score"] for c in others], reverse=True)
        solo = login("solo.patient@sihha.ai", "Patient@123")
        sc = solo.get(f"{API}/care/hospitals").json()
        assert [c["trust_score"] for c in sc] == sorted([c["trust_score"] for c in sc], reverse=True)

    def test_admin_moderation(self, admin, p2):
        rid = STATE["rating_id"]
        rows = admin.get(f"{API}/admin/accounts/{AL_NOOR}/ratings").json()
        assert any(r["rating_id"] == rid for r in rows)
        before = p2[0].get(f"{API}/care/hospitals/{AL_NOOR}/reviews").json()["count"]
        r = admin.patch(f"{API}/admin/ratings/{rid}", json={"hidden": True})
        assert r.status_code == 200 and r.json()["hidden"] is True
        after = p2[0].get(f"{API}/care/hospitals/{AL_NOOR}/reviews").json()
        assert after["count"] == before - 1 and all(x["rating_id"] != rid for x in after["reviews"])
        assert admin.patch(f"{API}/admin/ratings/{rid}", json={"hidden": False}).status_code == 200
        assert admin.patch(f"{API}/admin/ratings/nope", json={"hidden": True}).status_code == 404

    def test_account_admin_moderation(self, layla, khalid, p2):
        rid = STATE["rating_id"]
        rows = layla.get(f"{API}/account/ratings").json()
        assert any(r["rating_id"] == rid for r in rows)
        assert layla.patch(f"{API}/account/ratings/{rid}", json={"hidden": True}).status_code == 200
        assert layla.patch(f"{API}/account/ratings/{rid}", json={"hidden": False}).status_code == 200
        assert khalid.get(f"{API}/account/ratings").status_code == 403
        # create a Jeddah rating and verify layla can't hide it
        MONGO.hospital_ratings.insert_one({"rating_id": "rate_TEST_jed", "encounter_id": "enc_TEST_jed",
                                           "account_id": JEDDAH, "stars": 3, "comment": "", "hidden": False,
                                           "patient_user_id": "x", "updated_at": "2026-01-01"})
        CREATED["encounters"].append("enc_TEST_jed")
        assert layla.patch(f"{API}/account/ratings/rate_TEST_jed", json={"hidden": True}).status_code == 404

    def test_doctor_without_hospital_409(self, admin, p1):
        s, uid = p1
        eid = _encounter(admin, uid)
        assert admin.patch(f"{API}/encounters/{eid}", json={"status": "completed"}).status_code == 200
        row = next(x for x in s.get(f"{API}/my-visits").json()["past"] if x["encounter_id"] == eid)
        assert row["can_rate"] is False
        assert s.post(f"{API}/encounters/{eid}/rating", json={"stars": 4}).status_code == 409


# ---------- Pharmacy products ----------
def _csv(rows, header="sku,name_en,name_ar,generic_name,form,strength,category,requires_prescription,"
                      "sfda_registration_number,days_supply,pack_size,price_sar,stock_status"):
    return header + "\n" + "\n".join(rows) + "\n"


def _upload(sess, text, name="p.csv"):
    return sess.post(f"{API}/pharmacy-portal/catalog/import",
                     files={"file": (name, io.BytesIO(text.encode()), "text/csv")})


class TestProducts:
    def test_template(self, pharm, p1):
        r = pharm.get(f"{API}/pharmacy-portal/catalog/template.csv")
        assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
        assert "attachment" in r.headers.get("content-disposition", "")
        assert r.content.decode("utf-8-sig").splitlines()[0].startswith("sku,name_en")
        assert p1[0].get(f"{API}/pharmacy-portal/catalog/template.csv").status_code == 403

    def test_import_mixed(self, pharm):
        text = _csv([
            "TEST_OTC1,TEST_ Para,,paracetamol,tablet,500 mg,otc,no,,,24,9.50,in_stock",
            "TEST_RX1,TEST_ Metf,,metformin,tablet,500 mg,prescription,yes,SFDA-1,30,60,18.75,low",
            "TEST_BAD1,TEST_ Bad price,,,,,otc,no,,,,abc,in_stock",
            "TEST_RX2,TEST_ Rx no sfda,,,,,prescription,yes,,,,10,in_stock",
            "TEST_CAT,TEST_ Cat,,,,,weird,no,,,,10,in_stock",
        ])
        r = _upload(pharm, text)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["created"] == 2 and d["updated"] == 0, d
        rows = {e["row"]: e for e in d["errors"]}
        assert set(rows) == {4, 5, 6}, d["errors"]
        assert "price" in rows[4]["error"].lower()
        # re-upload same sku -> update
        r = _upload(pharm, _csv(["TEST_OTC1,TEST_ Para v2,,,,,otc,no,,,,11.00,low"]))
        assert r.json()["created"] == 0 and r.json()["updated"] == 1
        items = {i["sku"]: i for i in pharm.get(f"{API}/pharmacy-portal/catalog").json()["items"]}
        assert items["TEST_OTC1"]["price_sar"] == 11.0 and items["TEST_OTC1"]["name_en"] == "TEST_ Para v2"

    def test_import_missing_columns_and_size(self, pharm):
        assert _upload(pharm, "sku,name_en\nX,Y\n").status_code == 422
        big = _csv(["TEST_BIG,TEST_ x,,,,,otc,no,,,,1," + "a" * 1000] * 1100)
        assert _upload(pharm, big).status_code == 413

    def test_add_edit_product(self, pharm, p1):
        body = {"sku": "TEST_ADD1", "name_en": "TEST_ Added", "category": "otc", "price_sar": 5.5,
                "stock_status": "in_stock", "active": True}
        r = pharm.post(f"{API}/pharmacy-portal/catalog", json=body)
        assert r.status_code == 200, r.text
        iid = r.json()["item_id"]
        assert pharm.post(f"{API}/pharmacy-portal/catalog", json=body).status_code == 409
        rx = {**body, "sku": "TEST_ADDRX", "category": "prescription", "requires_prescription": True}
        assert pharm.post(f"{API}/pharmacy-portal/catalog", json=rx).status_code == 422
        r = pharm.put(f"{API}/pharmacy-portal/catalog/{iid}", json={**body, "price_sar": 7.25})
        assert r.status_code == 200 and r.json()["price_sar"] == 7.25
        assert pharm.put(f"{API}/pharmacy-portal/catalog/item_nope", json=body).status_code == 404
        assert pharm.put(f"{API}/pharmacy-portal/catalog/{iid}", json={**body, "sku": "TEST_OTC1"}).status_code == 409
        # patient marketplace
        cat = p1[0].get(f"{API}/pharmacy/catalog", params={"pharmacy_id": AL_DAWAA, "q": "TEST_", "limit": 100}).json()
        found = {i["sku"]: i for i in cat["items"]}
        assert found["TEST_ADD1"]["orderable"] is True and found["TEST_ADD1"]["price_sar"] == 7.25
        assert found["TEST_RX1"]["orderable"] is True
        # deactivate -> disappears
        pharm.put(f"{API}/pharmacy-portal/catalog/{iid}", json={**body, "active": False})
        cat = p1[0].get(f"{API}/pharmacy/catalog", params={"pharmacy_id": AL_DAWAA, "q": "TEST_", "limit": 100}).json()
        assert "TEST_ADD1" not in {i["sku"] for i in cat["items"]}
        STATE["otc_item"] = found["TEST_OTC1"]["item_id"]

    def test_cart_orderable(self, p1):
        s, _ = p1
        s.delete(f"{API}/pharmacy/cart")
        r = s.post(f"{API}/pharmacy/cart/items", json={"item_id": STATE["otc_item"], "qty": 1})
        assert r.status_code == 200, r.text
        s.delete(f"{API}/pharmacy/cart")


class TestLicences:
    def test_owner_update_and_staff_403(self, pharm):
        d = pharm.get(f"{API}/pharmacy-portal/catalog").json()
        orig = d["licences"]
        assert set(orig) == {"sfda_license", "moh_license", "cr_number"} and d["pharmacy_problems"] == []
        r = pharm.patch(f"{API}/pharmacy-portal/licences", json={"cr_number": orig["cr_number"]})
        assert r.status_code == 200 and r.json()["licences"]["cr_number"] == orig["cr_number"]
        MONGO.users.update_one({"email": "pharmacist@aldawaa.sihha.ai"}, {"$set": {"pharmacy_role": "staff"}})
        try:
            assert pharm.patch(f"{API}/pharmacy-portal/licences", json={"cr_number": "X"}).status_code == 403
        finally:
            MONGO.users.update_one({"email": "pharmacist@aldawaa.sihha.ai"}, {"$set": {"pharmacy_role": "owner"}})

    def test_apply_requires_moh_cr_and_approve_copies(self, admin):
        email = f"test_pharm_{uuid.uuid4().hex[:6]}@example.com"
        base = {"pharmacy_name": "TEST_ Ph21", "city": "Riyadh", "sfda_license": "SFDA-123", "name": "TEST_ Owner",
                "phone": "0500000000", "email": email, "password": "Test@1234"}
        r = requests.post(f"{API}/pharmacy-portal/apply", json=base)
        assert r.status_code == 422
        r = requests.post(f"{API}/pharmacy-portal/apply", json={**base, "moh_license": "MOH-1", "cr_number": "CR-1"})
        assert r.status_code == 200, r.text
        app_id = r.json()["application_id"]
        CREATED["apps"].append(app_id)
        CREATED["users"].append(MONGO.users.find_one({"email": email})["user_id"])
        r = admin.post(f"{API}/admin/pharmacy-applications/{app_id}/approve")
        assert r.status_code == 200, r.text
        pid = r.json()["pharmacy_id"]
        CREATED["pharmacies"].append(pid)
        ph = MONGO.pharmacies.find_one({"pharmacy_id": pid})
        assert ph["moh_license"] == "MOH-1" and ph["cr_number"] == "CR-1"
        s = login(email, "Test@1234")
        d = s.get(f"{API}/pharmacy-portal/catalog").json()
        assert d["pharmacy_problems"] == [], d["pharmacy_problems"]
        MONGO.catalog_items.delete_many({"pharmacy_id": pid})
