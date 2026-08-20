"""Integration tests for the pharmacy marketplace routes (all nine acceptance criteria).

Run:  cd /app/backend && set -a && . ./.env && set +a && \
      REACT_APP_BACKEND_URL=<preview url> python -m pytest tests/test_pharmacy_routes.py -q
Requires: python seed_pharmacy.py
"""
import io
import os

import pytest
import requests
from pymongo import MongoClient

API = f"{os.environ['REACT_APP_BACKEND_URL'].rstrip('/')}/api"
OMAR = {"email": "omar.patient@sihha.ai", "password": "Patient@123"}
SAMI = {"email": "sami.patient@sihha.ai", "password": "Patient@123"}


def login(creds):
    s = requests.Session()
    s.post(f"{API}/auth/login", json=creds, timeout=60).raise_for_status()
    return s


@pytest.fixture(scope="module")
def db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def patient():
    s = login(OMAR)
    s.delete(f"{API}/pharmacy/cart", timeout=60)
    return s


@pytest.fixture(scope="module")
def pharmacies(patient):
    rows = patient.get(f"{API}/pharmacy/pharmacies", timeout=60).json()
    handoff = next(p for p in rows if p["fulfilment_mode"] == "handoff")
    in_app = next(p for p in rows if p["fulfilment_mode"] == "in_app")
    return handoff, in_app


def find(session, q, pharmacy_id=None):
    params = {"q": q}
    if pharmacy_id:
        params["pharmacy_id"] = pharmacy_id
    items = session.get(f"{API}/pharmacy/catalog", params=params, timeout=60).json()["items"]
    assert items, f"no catalog item matching {q}"
    return items[0]


@pytest.fixture(scope="module")
def prescription(patient):
    r = patient.post(f"{API}/pharmacy/prescriptions", data={"source": "upload"},
                     files={"file": ("rx.png", io.BytesIO(b"\x89PNG\r\n\x1a\nfake"), "image/png")},
                     timeout=120)
    assert r.status_code == 200, r.text
    return r.json()


class TestCatalogAndLicences:
    def test_licences_render_on_every_listing(self, pharmacies):
        for pharmacy in pharmacies:
            assert pharmacy["sfda_license"] and pharmacy["moh_license"] and pharmacy["cr_number"]

    def test_sponsored_partner_ranks_first(self, patient):
        items = patient.get(f"{API}/pharmacy/catalog", params={"q": "Concor"}, timeout=60).json()["items"]
        assert len(items) >= 2
        assert items[0]["pharmacy"]["sponsored"] is True

    def test_branch_gives_directions(self, pharmacies):
        handoff, _ = pharmacies
        assert handoff["branches"][0]["directions_url"].startswith("https://www.google.com/maps/dir/")

    def test_controlled_item_is_shown_but_not_orderable(self, patient):
        item = find(patient, "Tramal")
        assert item["is_controlled"] is True
        assert item["orderable"] is False
        assert "CONTROLLED_NOT_ORDERABLE" in [v["rule"] for v in item["violations"]]


class TestCartCompliance:
    def test_controlled_cannot_be_added(self, patient):
        item = find(patient, "Tramal")
        r = patient.post(f"{API}/pharmacy/cart/items", json={"item_id": item["item_id"], "qty": 1},
                         timeout=60)
        assert r.status_code == 422
        assert "CONTROLLED_NOT_ORDERABLE" in [v["rule"] for v in r.json()["detail"]["violations"]]

    def test_more_than_three_months_rejected(self, patient, pharmacies):
        handoff, _ = pharmacies
        item = find(patient, "Concor", handoff["pharmacy_id"])
        r = patient.post(f"{API}/pharmacy/cart/items", json={"item_id": item["item_id"], "qty": 4},
                         timeout=60)
        assert r.status_code == 422
        assert "MAX_SUPPLY_EXCEEDED" in [v["rule"] for v in r.json()["detail"]["violations"]]

    def test_baskets_are_single_pharmacy(self, patient, pharmacies):
        handoff, in_app = pharmacies
        patient.delete(f"{API}/pharmacy/cart", timeout=60)
        a = find(patient, "Concor", handoff["pharmacy_id"])
        b = find(patient, "Concor", in_app["pharmacy_id"])
        assert patient.post(f"{API}/pharmacy/cart/items", json={"item_id": a["item_id"], "qty": 1},
                            timeout=60).status_code == 200
        r = patient.post(f"{API}/pharmacy/cart/items", json={"item_id": b["item_id"], "qty": 1},
                         timeout=60)
        assert r.status_code == 422
        assert r.json()["detail"]["violations"][0]["rule"] == "CART_SINGLE_PHARMACY"

    def test_cart_carries_per_item_compliance_messages(self, patient):
        cart = patient.get(f"{API}/pharmacy/cart", timeout=60).json()
        assert cart["items"] and "violations" in cart["items"][0]
        assert "PRESCRIPTION_REQUIRED" in [v["rule"] for v in cart["violations"]]


class TestCheckout:
    def test_prescription_item_without_a_prescription_fails(self, patient):
        r = patient.post(f"{API}/pharmacy/checkout", json={}, timeout=60)
        assert r.status_code == 422
        assert [v["rule"] for v in r.json()["detail"]["violations"]] == ["PRESCRIPTION_REQUIRED"]

    def test_prescription_upload_is_stored_and_readable(self, patient, prescription):
        assert prescription["verification_status"] == "pending"
        assert prescription["image_path"].startswith("sihha-ai/prescriptions/")
        assert patient.get(f"{API}/pharmacy/prescriptions/{prescription['prescription_id']}/image",
                           timeout=60).status_code == 200

    def test_handoff_produces_a_deep_link_and_stops_there(self, patient, prescription, pharmacies):
        handoff, _ = pharmacies
        patient.post(f"{API}/pharmacy/cart/prescription",
                     json={"prescription_id": prescription["prescription_id"]}, timeout=60)
        r = patient.post(f"{API}/pharmacy/checkout", json={}, timeout=60)
        assert r.status_code == 200, r.text
        order = r.json()
        assert order["status"] == "handed_off" and order["fulfilment_mode"] == "handoff"
        assert order["handoff_url"].startswith("https://partner.nahdi.example/cart?items=")
        assert "SKU-" in order["handoff_url"]
        assert order["pharmacy_snapshot"]["sfda_license"] and order["pharmacy_snapshot"]["moh_license"]
        assert order["pharmacy_snapshot"]["cr_number"]
        assert order["total_sar"] == order["subtotal_sar"] and order["delivery_fee_sar"] == 0
        assert [h["status"] for h in order["status_history"]] == ["handed_off"]
        assert patient.post(f"{API}/pharmacy/orders/{order['order_id']}/cancel",
                            timeout=60).status_code == 409

    def test_in_app_prescription_order_waits_for_the_pharmacist(self, patient, prescription, pharmacies):
        _, in_app = pharmacies
        item = find(patient, "Concor", in_app["pharmacy_id"])
        patient.post(f"{API}/pharmacy/cart/items", json={"item_id": item["item_id"], "qty": 1}, timeout=60)
        patient.post(f"{API}/pharmacy/cart/prescription",
                     json={"prescription_id": prescription["prescription_id"]}, timeout=60)
        r = patient.post(f"{API}/pharmacy/checkout", json={}, timeout=60)
        assert r.status_code == 200, r.text
        order = r.json()
        assert order["status"] == "awaiting_pharmacist_verification"
        assert order["prescription_id"] == prescription["prescription_id"]
        cancelled = patient.post(f"{API}/pharmacy/orders/{order['order_id']}/cancel", timeout=60)
        assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
        assert [h["status"] for h in cancelled.json()["status_history"]][-1] == "cancelled"

    def test_in_app_otc_order_is_confirmed(self, patient, pharmacies):
        _, in_app = pharmacies
        item = find(patient, "Panadol Extra", in_app["pharmacy_id"])
        patient.post(f"{API}/pharmacy/cart/items", json={"item_id": item["item_id"], "qty": 2}, timeout=60)
        r = patient.post(f"{API}/pharmacy/checkout", json={}, timeout=60)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "confirmed"
        assert r.json()["total_sar"] == round(item["price_sar"] * 2, 2)

    def test_orders_are_private(self, patient):
        order_id = patient.get(f"{API}/pharmacy/orders", timeout=60).json()[0]["order_id"]
        other = login(SAMI)
        assert other.get(f"{API}/pharmacy/orders/{order_id}", timeout=60).status_code == 403
        assert order_id not in [o["order_id"] for o in
                                other.get(f"{API}/pharmacy/orders", timeout=60).json()]


class TestRefills:
    def test_medication_four_days_out_is_due_and_thirty_days_is_not(self, patient):
        refills = patient.get(f"{API}/pharmacy/refills", timeout=60).json()
        due = {r["name"]: r for r in refills["due"]}
        upcoming = {r["name"]: r for r in refills["upcoming"]}
        assert "Concor" in due and due["Concor"]["days_remaining"] == 4
        assert due["Concor"]["projected_runout_date"]
        assert "Glucophage" not in due and upcoming["Glucophage"]["days_remaining"] == 30

    def test_a_due_refill_offers_every_pharmacy_sponsored_first(self, patient):
        refills = patient.get(f"{API}/pharmacy/refills", timeout=60).json()
        concor = next(r for r in refills["due"] if r["name"] == "Concor")
        assert concor["match_confidence"] == "high"
        assert concor["requires_user_confirmation"] is True
        assert len(concor["offers"]) >= 2 and concor["offers"][0]["sponsored"] is True
        assert concor["offers"][0]["pharmacy"]["sfda_license"]

    def test_an_unmatched_medication_offers_search_not_a_substitute(self, patient):
        refills = patient.get(f"{API}/pharmacy/refills", timeout=60).json()
        others = [r for r in refills["due"] + refills["upcoming"] + refills["unknown"]
                  if r["match_confidence"] == "none"]
        assert others, "expected at least one medication with no confident catalog match"
        for row in others:
            assert row["suggested_item"] is None and row["offers"] == []
            assert row["search_query"]

    def test_refill_alerts_go_through_the_existing_alerts_collection(self, patient, db):
        db.alerts.delete_many({"type": "refill"})
        first = patient.get(f"{API}/pharmacy/refills", params={"notify": "true"}, timeout=60).json()
        assert first["alerts_raised"] >= 1
        alert = db.alerts.find_one({"type": "refill"}, {"_id": 0})
        assert alert["severity"] == "info" and alert["read"] is False
        again = patient.get(f"{API}/pharmacy/refills", params={"notify": "true"}, timeout=60).json()
        assert again["alerts_raised"] == 0, "an open refill alert must not be duplicated"
        db.alerts.delete_many({"type": "refill"})
