"""Integration tests: screening triage, patient self-booking, and doctor-written prescriptions.

Run:  cd /app/backend && set -a && . ./.env && set +a && \
      REACT_APP_BACKEND_URL=<preview url> python -m pytest tests/test_visits_and_prescriptions.py -q
"""
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

API = f"{os.environ['REACT_APP_BACKEND_URL'].rstrip('/')}/api"
LAYLA = {"email": "dr.layla@sihha.ai", "password": "Doctor@123"}
OMAR = {"email": "omar.patient@sihha.ai", "password": "Patient@123"}
SAMI = {"email": "sami.patient@sihha.ai", "password": "Patient@123"}


def iso():
    return datetime.now(timezone.utc).isoformat()


def login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=60)
    r.raise_for_status()
    return s, r.json()


@pytest.fixture(scope="module")
def db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def doctor():
    ds, me = login(LAYLA)
    ds.put(f"{API}/profile/clinician", json={
        "specialty": "Internal medicine", "clinic": "Al Noor Medical Centre", "city": "Riyadh",
        "bio": "Internal medicine.", "clinic_phone": "+966 11 555 0199"}, timeout=60)
    ds.put(f"{API}/doctor/availability", json={
        "slot_minutes": 30, "tz_offset_minutes": 180,
        "weekly": [{"weekday": d, "start": "09:00", "end": "13:00"} for d in range(7)],
        "blocked_dates": []}, timeout=60)
    return ds, me


@pytest.fixture(scope="module")
def patient():
    return login(OMAR)


def seed_report(db, user_id, content, findings):
    report = {"report_id": f"report_{uuid.uuid4().hex[:12]}", "chat_session_id": f"chat_{uuid.uuid4().hex[:12]}",
              "user_id": user_id, "profile_id": user_id, "content": content, "findings": findings,
              "findings_extracted_at": iso(), "generated_at": iso(), "test_seeded": True}
    db.health_reports.insert_one(dict(report))
    return report


def finding(symptom, words, severity="moderate"):
    return {"finding_id": f"find_{uuid.uuid4().hex[:10]}", "symptom": symptom, "patient_words": words,
            "severity": severity, "onset": "2 days ago", "duration": "2 days", "source_message_ids": []}


@pytest.fixture(scope="module")
def red_flag_report(db, patient):
    _, me = patient
    report = seed_report(db, me["user_id"],
                         "Patient reports chest pain radiating to the left arm with shortness of breath.",
                         [finding("Chest pain", "I have chest pain that goes into my left arm", "severe"),
                          finding("Shortness of breath", "I feel short of breath when I walk")])
    yield report
    db.health_reports.delete_one({"report_id": report["report_id"]})


@pytest.fixture(scope="module")
def mild_report(db, patient):
    _, me = patient
    report = seed_report(db, me["user_id"],
                         "Patient reports a small itchy rash on the forearm for three days, no fever.",
                         [finding("Itchy rash", "a small itchy rash on my arm", "mild")])
    yield report
    db.health_reports.delete_one({"report_id": report["report_id"]})


class TestTriage:
    def test_red_flag_screening_is_triaged_as_an_emergency(self, patient, red_flag_report, db):
        ps, _ = patient
        r = ps.post(f"{API}/reports/{red_flag_report['report_id']}/triage", timeout=240)
        assert r.status_code == 200, r.text
        d = r.json()["disposition"]
        assert d["level"] == "emergency_now"
        assert d["rule_floor"] == "emergency_now"
        assert "CHEST_PAIN" in [f["code"] for f in d["red_flags"]]
        assert d["timeframe"] and d["emergency_number"] == "997"
        assert d["self_care_advice"] == [], "an emergency never gets self-care advice"
        assert d["reasons"], "the patient must be told why"

    def test_reasons_only_cite_findings_that_exist(self, patient, red_flag_report):
        ps, _ = patient
        report = ps.get(f"{API}/reports", timeout=60).json()
        row = next(r for r in report if r["report_id"] == red_flag_report["report_id"])
        valid = {f["finding_id"] for f in row["findings"]}
        cited = [fid for reason in row["disposition"]["reasons"] for fid in reason["finding_ids"]]
        assert cited and all(fid in valid for fid in cited)

    def test_mild_screening_is_not_escalated(self, patient, mild_report):
        ps, _ = patient
        d = ps.post(f"{API}/reports/{mild_report['report_id']}/triage", timeout=240).json()["disposition"]
        assert d["level"] in ("self_care", "routine_2w")
        assert d["rule_floor"] == "self_care" and d["red_flags"] == []
        assert d["recommended_specialty"]

    def test_urgent_screening_alerts_the_patient_and_their_doctor(self, patient, red_flag_report, db, doctor):
        ps, me = patient
        _, doc = doctor
        alerts = ps.get(f"{API}/alerts", timeout=60).json()
        assert any(a["type"] == "triage" and a["severity"] == "critical" for a in alerts)
        doctor_alerts = list(db.alerts.find({"user_id": doc["user_id"], "type": "triage"}, {"_id": 0}))
        assert any(a.get("patient_user_id") == me["user_id"] for a in doctor_alerts)

    def test_another_patient_cannot_triage_my_screening(self, red_flag_report):
        other, _ = login(SAMI)
        assert other.post(f"{API}/reports/{red_flag_report['report_id']}/triage",
                          timeout=120).status_code == 404


class TestBooking:
    def test_availability_is_validated(self, doctor):
        ds, _ = doctor
        bad = ds.put(f"{API}/doctor/availability", json={
            "slot_minutes": 30, "weekly": [{"weekday": 9, "start": "09:00", "end": "10:00"}]}, timeout=60)
        assert bad.status_code == 400
        bad_len = ds.put(f"{API}/doctor/availability", json={"slot_minutes": 7, "weekly": []}, timeout=60)
        assert bad_len.status_code == 400

    def test_patient_sees_their_own_doctor_first(self, patient, doctor):
        ps, _ = patient
        _, doc = doctor
        rows = ps.get(f"{API}/booking/doctors", timeout=60).json()
        assert rows and rows[0]["user_id"] == doc["user_id"] and rows[0]["is_my_doctor"] is True
        assert rows[0]["publishes_slots"] is True and rows[0]["next_slots"]
        assert rows[0]["clinic_phone"], "the card needs a number the patient can call"

    def test_specialty_filter_works(self, patient):
        ps, _ = patient
        assert ps.get(f"{API}/booking/doctors", params={"specialty": "Internal"},
                      timeout=60).json(), "the internal medicine doctor should match"
        assert ps.get(f"{API}/booking/doctors", params={"specialty": "Dermatology"},
                      timeout=60).json() == []

    def test_slots_are_in_the_future_and_labelled_in_clinic_time(self, patient, doctor):
        ps, _ = patient
        _, doc = doctor
        body = ps.get(f"{API}/booking/slots", params={"doctor_user_id": doc["user_id"], "days": 7},
                      timeout=60).json()
        assert body["slots"], "the doctor published hours, so there must be slots"
        assert all(s["start"] > iso() for s in body["slots"])
        assert body["slots"][0]["local_time"].endswith(("00", "30"))
        assert body["clinic_phone"]

    def test_emergency_screening_cannot_be_booked(self, patient, doctor, red_flag_report):
        ps, _ = patient
        _, doc = doctor
        slots = ps.get(f"{API}/booking/slots", params={"doctor_user_id": doc["user_id"]},
                       timeout=60).json()["slots"]
        r = ps.post(f"{API}/booking", json={"doctor_user_id": doc["user_id"], "slot_start": slots[0]["start"],
                                            "report_id": red_flag_report["report_id"]}, timeout=60)
        assert r.status_code == 409 and "997" in r.json()["detail"]

    def test_booking_a_slot_confirms_it_and_shares_the_screening(self, patient, doctor, mild_report, db):
        ps, me = patient
        _, doc = doctor
        slots = ps.get(f"{API}/booking/slots", params={"doctor_user_id": doc["user_id"]},
                       timeout=60).json()["slots"]
        slot = slots[1]
        r = ps.post(f"{API}/booking", json={"doctor_user_id": doc["user_id"], "slot_start": slot["start"],
                                            "report_id": mild_report["report_id"]}, timeout=60)
        assert r.status_code == 200, r.text
        enc = r.json()
        assert enc["status"] == "scheduled" and enc["booked_by"] == "patient"
        assert enc["reason_for_visit"], "the triage suggestion should fill the reason in"
        assert enc["slot_label"] == slot["label"]

        report = db.health_reports.find_one({"report_id": mild_report["report_id"]}, {"_id": 0})
        assert report["shared_encounter_id"] == enc["encounter_id"], "the doctor must see the screening"

        again = ps.post(f"{API}/booking", json={"doctor_user_id": doc["user_id"],
                                                "slot_start": slot["start"]}, timeout=60)
        assert again.status_code == 409, "a taken slot must disappear"

        assert db.alerts.find_one({"user_id": doc["user_id"], "type": "appointment",
                                   "encounter_id": enc["encounter_id"]})
        pytest.encounter_id = enc["encounter_id"]

    def test_doctor_sees_the_booking_on_their_schedule(self, doctor):
        ds, _ = doctor
        rows = ds.get(f"{API}/encounters", timeout=60).json()
        assert pytest.encounter_id in [e["encounter_id"] for e in rows]

    def test_patient_can_cancel_and_the_slot_returns(self, patient, doctor, db):
        ps, _ = patient
        _, doc = doctor
        enc = db.encounters.find_one({"encounter_id": pytest.encounter_id}, {"_id": 0})
        r = ps.post(f"{API}/encounters/{pytest.encounter_id}/cancel", timeout=60)
        assert r.status_code == 200 and r.json()["status"] == "cancelled"
        assert ps.post(f"{API}/encounters/{pytest.encounter_id}/cancel", timeout=60).status_code == 409
        slots = ps.get(f"{API}/booking/slots", params={"doctor_user_id": doc["user_id"]},
                       timeout=60).json()["slots"]
        assert enc["scheduled_at"] in [s["start"] for s in slots]
        assert db.alerts.find_one({"user_id": doc["user_id"], "type": "appointment",
                                   "message": {"$regex": "cancelled"}})

    def test_a_stranger_cannot_cancel_my_visit(self, patient, doctor):
        ps, _ = patient
        _, doc = doctor
        slots = ps.get(f"{API}/booking/slots", params={"doctor_user_id": doc["user_id"]},
                       timeout=60).json()["slots"]
        enc = ps.post(f"{API}/booking", json={"doctor_user_id": doc["user_id"],
                                              "slot_start": slots[2]["start"]}, timeout=60).json()
        other, _ = login(SAMI)
        assert other.post(f"{API}/encounters/{enc['encounter_id']}/cancel", timeout=60).status_code == 403
        pytest.rx_encounter_id = enc["encounter_id"]


class TestPrescriptions:
    def test_doctor_writes_a_draft_and_controlled_items_are_flagged(self, doctor):
        ds, _ = doctor
        r = ds.post(f"{API}/encounters/{pytest.rx_encounter_id}/prescription", json={
            "diagnosis": "Hypertension, controlled", "notes": "Review in four weeks",
            "items": [
                {"drug_name": "Concor", "generic_name": "Bisoprolol", "form": "tablet", "strength": "5 mg",
                 "dose": "1 tablet", "frequency": "once daily", "duration_days": 30, "quantity": 30,
                 "refills": 2, "instructions": "Take in the morning with water"},
                {"drug_name": "Tramal", "generic_name": "Tramadol", "form": "capsule", "strength": "50 mg",
                 "dose": "1 capsule", "frequency": "when needed", "duration_days": 5, "quantity": 10},
            ]}, timeout=60)
        assert r.status_code == 200, r.text
        rx = r.json()
        assert rx["status"] == "draft" and rx["issued_by_name"]
        by_name = {i["drug_name"]: i for i in rx["items"]}
        assert by_name["Tramal"]["is_controlled"] is True
        assert by_name["Tramal"]["dispense_in_clinic"] is True
        assert by_name["Concor"]["is_controlled"] is False and by_name["Concor"]["catalog_match_count"] >= 2
        pytest.rx_id = rx["prescription_id"]

    def test_patient_cannot_see_a_draft(self, patient):
        ps, _ = patient
        assert pytest.rx_id not in [r["prescription_id"] for r in
                                    ps.get(f"{API}/prescriptions", timeout=60).json()]
        assert ps.get(f"{API}/prescriptions/{pytest.rx_id}", timeout=60).status_code == 404

    def test_writing_again_updates_the_same_draft(self, doctor):
        ds, _ = doctor
        r = ds.post(f"{API}/encounters/{pytest.rx_encounter_id}/prescription", json={
            "diagnosis": "Hypertension", "items": [
                {"drug_name": "Concor", "strength": "5 mg", "dose": "1 tablet", "frequency": "once daily"}]},
            timeout=60)
        assert r.json()["prescription_id"] == pytest.rx_id and len(r.json()["items"]) == 1

    def test_empty_prescription_is_rejected(self, doctor):
        ds, _ = doctor
        assert ds.post(f"{API}/encounters/{pytest.rx_encounter_id}/prescription",
                       json={"items": []}, timeout=60).status_code == 400

    def test_signing_sends_it_to_the_patient_and_locks_it(self, doctor, patient, db):
        ds, _ = doctor
        ps, me = patient
        ds.post(f"{API}/encounters/{pytest.rx_encounter_id}/prescription", json={
            "diagnosis": "Hypertension, controlled", "notes": "Review in four weeks",
            "items": [
                {"drug_name": "Concor", "strength": "5 mg", "dose": "1 tablet", "frequency": "once daily",
                 "duration_days": 30, "quantity": 30, "refills": 2},
                {"drug_name": "Tramal", "strength": "50 mg", "dose": "1 capsule", "frequency": "when needed"},
            ]}, timeout=60)
        signed = ds.post(f"{API}/prescriptions/{pytest.rx_id}/sign", timeout=60)
        assert signed.status_code == 200 and signed.json()["status"] == "signed"
        assert signed.json()["signed_at"]
        assert ds.patch(f"{API}/prescriptions/{pytest.rx_id}",
                        json={"items": [{"drug_name": "X"}]}, timeout=60).status_code == 409
        assert ds.post(f"{API}/prescriptions/{pytest.rx_id}/sign", timeout=60).status_code == 409
        mine = ps.get(f"{API}/prescriptions", timeout=60).json()
        assert pytest.rx_id in [r["prescription_id"] for r in mine]
        assert db.alerts.find_one({"user_id": me["user_id"], "type": "prescription",
                                   "prescription_id": pytest.rx_id})

    def test_another_patient_cannot_read_it(self):
        other, _ = login(SAMI)
        assert other.get(f"{API}/prescriptions/{pytest.rx_id}", timeout=60).status_code == 403
        assert pytest.rx_id not in [r["prescription_id"] for r in
                                    other.get(f"{API}/prescriptions", timeout=60).json()]

    def test_basket_options_offer_every_pharmacy_and_block_controlled(self, patient):
        ps, _ = patient
        body = ps.get(f"{API}/prescriptions/{pytest.rx_id}/basket-options", timeout=60).json()
        by_name = {p["drug_name"]: p for p in body["proposals"]}
        assert by_name["Concor"]["orderable"] is True
        assert len(by_name["Concor"]["offers"]) >= 2
        assert by_name["Concor"]["offers"][0]["sponsored"] is True
        assert by_name["Concor"]["requires_user_confirmation"] is True
        assert by_name["Tramal"]["orderable"] is False and by_name["Tramal"]["offers"] == []
        assert "clinic" in by_name["Tramal"]["reason"].lower()

    def test_transmitting_to_a_partner_creates_a_pharmacist_queue_item(self, doctor, patient, db):
        ds, _ = doctor
        ps, _ = patient
        pharmacies = ps.get(f"{API}/pharmacy/pharmacies", timeout=60).json()
        in_app = next(p for p in pharmacies if p["fulfilment_mode"] == "in_app")
        r = ds.post(f"{API}/prescriptions/{pytest.rx_id}/transmit",
                    json={"pharmacy_id": in_app["pharmacy_id"]}, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["order"]["status"] == "awaiting_pharmacist_verification"
        assert body["order"]["prescription_id"] == pytest.rx_id
        assert body["pharmacy"]["sfda_license"] and body["pharmacy"]["moh_license"]
        assert any(u["drug_name"] == "Tramal" for u in body["unmatched"]), \
            "a controlled medicine is never transmitted online"
        assert pytest.rx_id in [o["prescription_id"] for o in
                                ps.get(f"{API}/pharmacy/orders", timeout=60).json()
                                if o.get("prescription_id")]

    def test_unsigned_prescription_cannot_be_transmitted(self, doctor, patient):
        ds, _ = doctor
        ps, _ = patient
        slots = ps.get(f"{API}/booking/slots", timeout=60,
                       params={"doctor_user_id": ds.get(f"{API}/auth/me", timeout=60).json()["user_id"]}
                       ).json()["slots"]
        enc = ps.post(f"{API}/booking", json={"doctor_user_id": ds.get(f"{API}/auth/me", timeout=60)
                                              .json()["user_id"], "slot_start": slots[3]["start"]},
                      timeout=60).json()
        draft = ds.post(f"{API}/encounters/{enc['encounter_id']}/prescription", json={
            "items": [{"drug_name": "Panadol Extra", "dose": "1 tablet", "frequency": "as needed"}]},
            timeout=60).json()
        pharmacies = ps.get(f"{API}/pharmacy/pharmacies", timeout=60).json()
        r = ds.post(f"{API}/prescriptions/{draft['prescription_id']}/transmit",
                    json={"pharmacy_id": pharmacies[0]["pharmacy_id"]}, timeout=60)
        assert r.status_code == 409
        ps.post(f"{API}/encounters/{enc['encounter_id']}/cancel", timeout=60)
