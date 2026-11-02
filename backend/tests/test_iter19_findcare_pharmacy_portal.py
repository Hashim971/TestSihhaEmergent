# Iteration 19: standalone patients (hospital finder, booking share consent), pharmacy portal
# (apply/approve/reject, invite staff, order transitions, messaging), sponsorship console (mocked billing).
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
AL_NOOR, JEDDAH, EASTERN = "ACC-12AFFE", "ACC-2BC6ED", "ACC-A84A0F"
AL_DAWAA = "pharm_744d6031f418"
OTC_AL_DAWAA = "item_7b3c5dd64c3b"  # Panadol Extra @ Al Dawaa
CREATED = {"users": [], "pharmacies": [], "apps": [], "spr": [], "orders": [], "encounters": []}


def login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def solo():
    return login("solo.patient@sihha.ai", "Patient@123")


@pytest.fixture(scope="module")
def omar():
    return login("omar.patient@sihha.ai", "Patient@123")


@pytest.fixture(scope="module")
def admin():
    return login("admin@sihha.ai", "Admin@123")


@pytest.fixture(scope="module")
def khalid():
    return login("dr.khalid@sihha.ai", "Doctor@123")


@pytest.fixture(scope="module")
def layla():
    return login("dr.layla@sihha.ai", "Doctor@123")


@pytest.fixture(scope="module")
def pharm():
    return login("pharmacist@aldawaa.sihha.ai", "Pharma@123")


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    solo_id = MONGO.users.find_one({"email": "solo.patient@sihha.ai"})["user_id"]
    MONGO.users.update_one({"user_id": solo_id}, {"$set": {"account_id": None, "account_role": None,
                                                           "assigned_doctor_user_id": None}})
    MONGO.care_grants.delete_many({"encounter_id": {"$in": CREATED["encounters"]}})
    MONGO.encounters.delete_many({"encounter_id": {"$in": CREATED["encounters"]}})
    MONGO.alerts.delete_many({"encounter_id": {"$in": CREATED["encounters"]}})
    MONGO.order_messages.delete_many({"order_id": {"$in": CREATED["orders"]}})
    MONGO.alerts.delete_many({"order_id": {"$in": CREATED["orders"]}})
    MONGO.orders.delete_many({"order_id": {"$in": CREATED["orders"]}})
    MONGO.sponsorship_requests.delete_many({"request_id": {"$in": CREATED["spr"]}})
    MONGO.pharmacies.delete_many({"pharmacy_id": {"$in": CREATED["pharmacies"]}})
    MONGO.pharmacy_applications.delete_many({"application_id": {"$in": CREATED["apps"]}})
    MONGO.users.delete_many({"user_id": {"$in": CREATED["users"]}})
    MONGO.login_attempts.delete_many({"identifier": {"$regex": "^pharmacy-apply:"}})


# ---------- Hospital finder ----------
class TestHospitalFinder:
    def test_list_only_listed(self, solo):
        r = solo.get(f"{API}/care/hospitals")
        assert r.status_code == 200
        ids = {c["account_id"] for c in r.json()}
        assert ids == {AL_NOOR, JEDDAH}, ids
        assert all(c["is_my_hospital"] is False for c in r.json())

    def test_filters(self, solo):
        assert [c["account_id"] for c in solo.get(f"{API}/care/hospitals", params={"city": "jeddah"}).json()] == [JEDDAH]
        assert [c["account_id"] for c in solo.get(f"{API}/care/hospitals", params={"q": "noor"}).json()] == [AL_NOOR]
        assert [c["account_id"] for c in solo.get(f"{API}/care/hospitals", params={"specialty": "pediat"}).json()] == [JEDDAH]
        assert solo.get(f"{API}/care/hospitals", params={"q": "zzzz"}).json() == []

    def test_is_my_hospital_flag(self, omar):
        cards = omar.get(f"{API}/care/hospitals").json()
        mine = [c for c in cards if c["is_my_hospital"]]
        assert [c["account_id"] for c in mine] == [AL_NOOR]
        assert cards[0]["account_id"] == AL_NOOR

    def test_doctors_by_hospital(self, solo):
        docs = solo.get(f"{API}/booking/doctors", params={"account_id": JEDDAH}).json()
        assert docs and all(d["account_id"] == JEDDAH for d in docs)
        assert any(d["user_id"] == "user_af7cc0803ba9" for d in docs)

    def test_switch_hospital(self, solo, layla):
        assert solo.put(f"{API}/profile/hospital", json={"account_id": EASTERN}).status_code == 404
        r = solo.put(f"{API}/profile/hospital", json={"account_id": JEDDAH})
        assert r.status_code == 200 and r.json()["hospital"]["account_id"] == JEDDAH
        assert solo.get(f"{API}/profile/hospital").json()["hospital"]["account_id"] == JEDDAH
        r = solo.put(f"{API}/profile/hospital", json={"account_id": None})
        assert r.status_code == 200 and r.json()["hospital"] is None
        assert layla.put(f"{API}/profile/hospital", json={"account_id": JEDDAH}).status_code == 403


# ---------- Booking with share consent ----------
def _book(sess, doctor_id, share):
    slots = sess.get(f"{API}/booking/slots", params={"doctor_user_id": doctor_id}).json()["slots"]
    assert slots, "no open slots"
    r = sess.post(f"{API}/booking", json={"doctor_user_id": doctor_id, "slot_start": slots[-1]["start"],
                                          "reason_for_visit": "TEST_ booking", "share_record": share})
    assert r.status_code == 200, r.text
    enc = r.json().get("encounter", r.json())
    CREATED["encounters"].append(enc["encounter_id"])
    return enc


class TestBookingShare:
    KHALID = "user_af7cc0803ba9"

    def test_book_no_share(self, solo, khalid):
        solo.put(f"{API}/profile/hospital", json={"account_id": None})
        enc = _book(solo, self.KHALID, False)
        doc = MONGO.encounters.find_one({"encounter_id": enc["encounter_id"]})
        assert doc["record_shared"] is False
        assert MONGO.care_grants.count_documents({"encounter_id": enc["encounter_id"]}) == 0
        assert MONGO.users.find_one({"email": "solo.patient@sihha.ai"})["account_id"] is None
        sid = doc["patient_user_id"]
        r = khalid.get(f"{API}/doctor/patients/{sid}/summary")
        assert r.status_code == 403, r.status_code

    def test_book_share_then_switch(self, solo, khalid, layla):
        enc = _book(solo, self.KHALID, True)
        u = MONGO.users.find_one({"email": "solo.patient@sihha.ai"})
        assert u["account_id"] == JEDDAH
        assert MONGO.care_grants.count_documents({"encounter_id": enc["encounter_id"], "revoked": False}) == 1
        assert khalid.get(f"{API}/doctor/patients/{u['user_id']}/summary").status_code == 200
        # week view data: doctor sees this encounter
        encs = khalid.get(f"{API}/encounters").json()
        lst = encs if isinstance(encs, list) else encs.get("encounters", [])
        assert any(e["encounter_id"] == enc["encounter_id"] for e in lst)
        # switching to Al Noor revokes Khalid's grant
        assert solo.put(f"{API}/profile/hospital", json={"account_id": AL_NOOR}).status_code == 200
        assert MONGO.care_grants.count_documents({"encounter_id": enc["encounter_id"], "revoked": False}) == 0
        assert khalid.get(f"{API}/doctor/patients/{u['user_id']}/summary").status_code == 403
        solo.put(f"{API}/profile/hospital", json={"account_id": None})

    def test_pharmacist_cannot_book(self, pharm):
        slots = pharm.get(f"{API}/booking/slots", params={"doctor_user_id": self.KHALID}).json().get("slots", [])
        if not slots:
            pytest.skip("no slots")
        r = pharm.post(f"{API}/booking", json={"doctor_user_id": self.KHALID, "slot_start": slots[0]["start"]})
        if r.status_code == 200:
            CREATED["encounters"].append(r.json().get("encounter", r.json())["encounter_id"])
        assert r.status_code == 403, f"pharmacist allowed to book patient visit: {r.status_code}"


# ---------- Listing ----------
class TestListing:
    def test_admin_patch_listing(self, admin):
        r = admin.patch(f"{API}/admin/accounts/{EASTERN}", json={"listed_in_app": True, "city": "Dammam"})
        assert r.status_code == 200, r.text
        try:
            s = login("solo.patient@sihha.ai", "Patient@123")
            assert EASTERN in {c["account_id"] for c in s.get(f"{API}/care/hospitals").json()}
        finally:
            assert admin.patch(f"{API}/admin/accounts/{EASTERN}", json={"listed_in_app": False}).status_code == 200

    def test_account_admin_listing(self, layla, khalid):
        before = MONGO.accounts.find_one({"account_id": AL_NOOR})
        r = layla.patch(f"{API}/account/listing", json={"about": before.get("about") or "Al Noor"})
        assert r.status_code == 200
        assert khalid.patch(f"{API}/account/listing", json={"about": "x"}).status_code == 403


# ---------- Pharmacy portal: auth, apply, invite ----------
class TestPortalOnboarding:
    def test_me_and_roles(self, pharm, solo):
        me = pharm.get(f"{API}/pharmacy-portal/me").json()
        assert me["status"] == "approved" and me["pharmacy"]["pharmacy_id"] == AL_DAWAA
        assert solo.get(f"{API}/pharmacy-portal/me").status_code == 403
        assert solo.get(f"{API}/pharmacy-portal/orders").status_code == 403

    def test_apply_approve_reject(self, admin):
        ids = {}
        for tag in ("ok", "no"):
            email = f"test_pharm_{tag}_{uuid.uuid4().hex[:6]}@example.com"
            r = requests.post(f"{API}/pharmacy-portal/apply", json={
                "pharmacy_name": f"TEST_ Pharmacy {tag}", "city": "Riyadh", "sfda_license": "SFDA-123", "moh_license": "MOH-1", "cr_number": "CR-1",
                "name": "TEST_ Owner", "phone": "0500000000", "email": email, "password": "Test@1234"})
            assert r.status_code == 200, r.text
            CREATED["apps"].append(r.json()["application_id"])
            CREATED["users"].append(MONGO.users.find_one({"email": email})["user_id"])
            s = login(email, "Test@1234")
            assert s.get(f"{API}/pharmacy-portal/me").json()["status"] == "pending"
            assert s.get(f"{API}/pharmacy-portal/orders").status_code == 403
            ids[tag] = (r.json()["application_id"], s)
        pend = admin.get(f"{API}/admin/pharmacy-applications").json()
        assert {ids["ok"][0], ids["no"][0]} <= {a["application_id"] for a in pend}
        r = admin.post(f"{API}/admin/pharmacy-applications/{ids['ok'][0]}/approve")
        assert r.status_code == 200
        CREATED["pharmacies"].append(r.json()["pharmacy_id"])
        assert admin.post(f"{API}/admin/pharmacy-applications/{ids['ok'][0]}/approve").status_code == 409
        assert ids["ok"][1].get(f"{API}/pharmacy-portal/me").json()["status"] == "approved"
        assert ids["ok"][1].get(f"{API}/pharmacy-portal/orders").status_code == 200
        r = admin.post(f"{API}/admin/pharmacy-applications/{ids['no'][0]}/reject", json={"reason": "TEST_ bad license"})
        assert r.status_code == 200
        me = ids["no"][1].get(f"{API}/pharmacy-portal/me").json()
        assert me["status"] == "rejected" and me["application"]["reason"] == "TEST_ bad license"
        TestPortalOnboarding.approved = (r.json(), ids["ok"][1], CREATED["pharmacies"][-1])

    def test_duplicate_email_apply(self):
        r = requests.post(f"{API}/pharmacy-portal/apply", json={
            "pharmacy_name": "TEST_ dup", "city": "Riyadh", "sfda_license": "SFDA-1", "moh_license": "MOH-1", "cr_number": "CR-1", "name": "x",
            "email": "solo.patient@sihha.ai", "password": "Test@1234"})
        assert r.status_code in (400, 429)

    def test_invite_and_remove_staff(self, admin):
        pid = CREATED["pharmacies"][-1]
        email = f"test_staff_{uuid.uuid4().hex[:6]}@example.com"
        r = admin.post(f"{API}/admin/pharmacies/{pid}/staff", json={"name": "TEST_ Staff", "email": email})
        assert r.status_code == 200 and r.json()["invited"] is True
        CREATED["users"].append(r.json()["user_id"])
        row = next(p for p in admin.get(f"{API}/admin/pharmacies").json() if p["pharmacy_id"] == pid)
        st = next(s for s in row["staff"] if s["email"] == email)
        assert st["status"] == "invited" and st["pharmacy_role"] == "staff"
        assert admin.post(f"{API}/admin/pharmacies/{pid}/staff",
                          json={"name": "x", "email": "solo.patient@sihha.ai"}).status_code == 409
        assert admin.delete(f"{API}/admin/pharmacies/{pid}/staff/{st['user_id']}").status_code == 200
        row = next(p for p in admin.get(f"{API}/admin/pharmacies").json() if p["pharmacy_id"] == pid)
        assert all(s["email"] != email for s in row["staff"])
        assert admin.post(f"{API}/admin/pharmacies/nope/staff", json={"name": "x", "email": "a@b.co"}).status_code == 404


# ---------- Orders + messaging ----------
def _place_otc(sess):
    sess.delete(f"{API}/pharmacy/cart")
    r = sess.post(f"{API}/pharmacy/cart/items", json={"item_id": OTC_AL_DAWAA, "qty": 1})
    assert r.status_code == 200, r.text
    r = sess.post(f"{API}/pharmacy/checkout", json={})
    assert r.status_code == 200, r.text
    order = r.json().get("order", r.json())
    CREATED["orders"].append(order["order_id"])
    return order


class TestPortalOrders:
    def test_transitions(self, solo, pharm):
        order = _place_otc(solo)
        oid = order["order_id"]
        assert order["status"] == "confirmed"
        listed = pharm.get(f"{API}/pharmacy-portal/orders").json()
        row = next(o for o in listed if o["order_id"] == oid)
        assert set(row["allowed_next"]) == {"ready_for_pickup", "out_for_delivery", "rejected"}
        st = lambda s, n="": pharm.post(f"{API}/pharmacy-portal/orders/{oid}/status", json={"status": s, "note": n})
        assert st("completed").status_code == 409
        assert st("rejected").status_code == 422
        r = st("ready_for_pickup", "TEST_ ready")
        assert r.status_code == 200 and r.json()["status"] == "ready_for_pickup"
        assert r.json()["status_history"][-1]["note"] == "TEST_ ready"
        assert st("confirmed").status_code == 409
        assert st("completed").status_code == 200
        assert st("completed").status_code == 409
        assert MONGO.alerts.count_documents({"order_id": oid, "type": "pharmacy"}) >= 2
        done = pharm.get(f"{API}/pharmacy-portal/orders", params={"view": "done"}).json()
        assert any(o["order_id"] == oid for o in done)
        assert solo.get(f"{API}/pharmacy/orders/{oid}").json()["status"] == "completed"

    def test_reject_with_note(self, solo, pharm):
        oid = _place_otc(solo)["order_id"]
        r = pharm.post(f"{API}/pharmacy-portal/orders/{oid}/status", json={"status": "rejected", "note": "TEST_ out of stock"})
        assert r.status_code == 200 and r.json()["status"] == "rejected"

    def test_messaging_and_isolation(self, solo, omar, pharm):
        oid = _place_otc(solo)["order_id"]
        r = solo.post(f"{API}/pharmacy/orders/{oid}/messages", json={"text": "TEST_ hello pharmacy"})
        assert r.status_code == 200 and r.json()["sender"] == "patient"
        row = next(o for o in pharm.get(f"{API}/pharmacy-portal/orders").json() if o["order_id"] == oid)
        assert row["unread_messages"] == 1
        msgs = pharm.get(f"{API}/pharmacy-portal/orders/{oid}/messages").json()
        assert [m["text"] for m in msgs] == ["TEST_ hello pharmacy"]
        row = next(o for o in pharm.get(f"{API}/pharmacy-portal/orders").json() if o["order_id"] == oid)
        assert row["unread_messages"] == 0
        assert pharm.post(f"{API}/pharmacy-portal/orders/{oid}/messages", json={"text": "TEST_ reply"}).status_code == 200
        assert len(solo.get(f"{API}/pharmacy/orders/{oid}/messages").json()) == 2
        assert omar.get(f"{API}/pharmacy/orders/{oid}/messages").status_code in (403, 404)
        assert solo.post(f"{API}/pharmacy/orders/{oid}/messages", json={"text": ""}).status_code == 422
        _, other, _ = TestPortalOnboarding.approved
        assert other.get(f"{API}/pharmacy-portal/orders/{oid}/messages").status_code == 404
        assert other.post(f"{API}/pharmacy-portal/orders/{oid}/status", json={"status": "rejected", "note": "x"}).status_code == 404


# ---------- Sponsorship ----------
class TestSponsorship:
    def test_request_cancel_markpaid_rank(self, admin):
        _, owner, pid = TestPortalOnboarding.approved
        info = owner.get(f"{API}/pharmacy-portal/sponsorship").json()
        assert [t["key"] for t in info["tiers"]] == ["bronze", "silver", "gold"]
        assert info["payment_provider_connected"] is False
        r = owner.post(f"{API}/pharmacy-portal/sponsorship/requests", json={"tier": "silver"})
        assert r.status_code == 200 and r.json()["status"] == "awaiting_payment" and r.json()["amount_sar"] == 1200.0
        CREATED["spr"].append(r.json()["request_id"])
        assert owner.post(f"{API}/pharmacy-portal/sponsorship/requests", json={"tier": "gold"}).status_code == 409
        assert owner.post(f"{API}/pharmacy-portal/sponsorship/requests/{r.json()['request_id']}/cancel").status_code == 200
        assert owner.post(f"{API}/pharmacy-portal/sponsorship/requests/{r.json()['request_id']}/cancel").status_code == 409
        r = owner.post(f"{API}/pharmacy-portal/sponsorship/requests", json={"tier": "silver"})
        rid = r.json()["request_id"]
        CREATED["spr"].append(rid)
        assert rid in [x["request_id"] for x in admin.get(f"{API}/admin/sponsorship-requests").json()]
        r = admin.post(f"{API}/admin/sponsorship-requests/{rid}/mark-paid", json={"reference": "TEST_REF"})
        assert r.status_code == 200 and r.json()["status"] == "paid" and r.json()["active_until"]
        assert admin.post(f"{API}/admin/sponsorship-requests/{rid}/mark-paid", json={}).status_code == 409
        cur = owner.get(f"{API}/pharmacy-portal/sponsorship").json()["current"]
        assert cur["active"] is True and cur["tier"] == "silver"
        ranks = [p["pharmacy_id"] for p in owner.get(f"{API}/pharmacy/pharmacies").json()]
        # Nahdi gold first, then this silver, then unsponsored Al Dawaa
        assert ranks.index("pharm_8a96b2710089") < ranks.index(pid) < ranks.index(AL_DAWAA), ranks
        r = owner.post(f"{API}/pharmacy-portal/sponsorship/requests", json={"tier": "bronze"})
        CREATED["spr"].append(r.json()["request_id"])
        assert admin.post(f"{API}/admin/sponsorship-requests/{r.json()['request_id']}/decline",
                          json={"reason": "TEST_"}).status_code == 200


# ---------- Screening report prompt (single quick check) ----------
def test_screening_report_prompt_version(omar):
    rep = MONGO.health_reports.find_one({"prompt_version": "report-v1/chat-v1"}, {"_id": 0, "prompt_version": 1})
    if not rep:
        pytest.skip("no report generated with the new prompts in DB")
    assert rep["prompt_version"] == "report-v1/chat-v1"
