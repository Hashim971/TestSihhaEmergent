"""Unit tests for pharmacy/compliance.py — each rule proven independently, no I/O."""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pharmacy import compliance as c  # noqa: E402

PHARMACY = {"pharmacy_id": "pharm_1", "sfda_license": "SFDA-1", "moh_license": "MOH-1",
            "cr_number": "CR-1", "active": True, "fulfilment_mode": "handoff"}


def item(**over):
    base = {"item_id": "item_1", "pharmacy_id": "pharm_1", "sku": "SKU-1", "name_en": "Panadol",
            "name_ar": "بنادول", "category": "otc", "requires_prescription": False,
            "is_controlled": False, "days_supply": None, "sfda_registration_number": None,
            "stock_status": "in_stock", "active": True, "price_sar": 10.0}
    base.update(over)
    return base


def rx_item(**over):
    base = {"category": "prescription", "requires_prescription": True, "days_supply": 30,
            "sfda_registration_number": "SFDA-REG-1"}
    base.update(over)
    return item(**base)


def rules(violations):
    return [v["rule"] for v in violations]


class TestControlled:
    def test_rejected_at_ingestion(self):
        assert c.CONTROLLED_NOT_ORDERABLE in rules(c.check_catalog_item(rx_item(is_controlled=True)))

    def test_rejected_at_add_to_cart(self):
        assert c.CONTROLLED_NOT_ORDERABLE in rules(
            c.check_add_to_cart(rx_item(is_controlled=True), PHARMACY, 1))

    def test_rejected_at_checkout(self):
        entries = [{"item": rx_item(is_controlled=True), "qty": 1}]
        assert c.CONTROLLED_NOT_ORDERABLE in rules(c.check_checkout(entries, PHARMACY))

    def test_not_orderable_but_still_displayable(self):
        assert c.is_orderable(rx_item(is_controlled=True), PHARMACY) is False
        assert c.is_orderable(item(), PHARMACY) is True


class TestPrescriptionRequirement:
    def test_missing_prescription_fails_checkout(self):
        entries = [{"item": rx_item(), "qty": 1}]
        assert rules(c.check_checkout(entries, PHARMACY)) == [c.PRESCRIPTION_REQUIRED]

    def test_rejected_prescription_fails(self):
        entries = [{"item": rx_item(), "qty": 1}]
        rx = {"verification_status": "rejected", "rejection_reason": "illegible",
              "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}
        assert c.PRESCRIPTION_REJECTED in rules(c.check_checkout(entries, PHARMACY, rx))

    def test_expired_prescription_fails(self):
        entries = [{"item": rx_item(), "qty": 1}]
        rx = {"verification_status": "pending",
              "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}
        assert c.PRESCRIPTION_EXPIRED in rules(c.check_checkout(entries, PHARMACY, rx))

    def test_pending_prescription_passes_because_the_pharmacist_verifies(self):
        entries = [{"item": rx_item(), "qty": 1}]
        rx = {"verification_status": "pending",
              "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}
        assert c.check_checkout(entries, PHARMACY, rx) == []

    def test_dispensing_requires_a_verified_prescription(self):
        entries = [{"item": rx_item(), "qty": 1}]
        rx = {"verification_status": "pending",
              "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}
        assert c.PRESCRIPTION_NOT_VERIFIED in rules(
            c.check_checkout(entries, PHARMACY, rx, require_verified=True))

    def test_otc_needs_no_prescription(self):
        assert c.check_checkout([{"item": item(), "qty": 3}], PHARMACY) == []


class TestThreeMonthCap:
    def test_cap_enforced_at_cart_level(self):
        assert c.MAX_SUPPLY_EXCEEDED in rules(c.check_add_to_cart(rx_item(), PHARMACY, 4))

    def test_three_months_exactly_is_allowed(self):
        assert c.MAX_SUPPLY_EXCEEDED not in rules(c.check_add_to_cart(rx_item(), PHARMACY, 3))

    def test_existing_cart_quantity_counts(self):
        assert c.MAX_SUPPLY_EXCEEDED in rules(
            c.check_add_to_cart(rx_item(), PHARMACY, 2, qty_already_in_cart=2))

    def test_cap_re_checked_at_checkout(self):
        assert c.MAX_SUPPLY_EXCEEDED in rules(c.check_checkout([{"item": rx_item(), "qty": 4}], PHARMACY))

    def test_prescription_without_days_supply_is_not_orderable(self):
        assert c.MISSING_DAYS_SUPPLY in rules(c.check_catalog_item(rx_item(days_supply=None)))


class TestLicencesAndFailClosed:
    def test_incomplete_licences_block_everything(self):
        broken = {**PHARMACY, "moh_license": ""}
        assert c.PHARMACY_LICENCE_INCOMPLETE in rules(c.check_add_to_cart(item(), broken, 1))
        assert c.PHARMACY_LICENCE_INCOMPLETE in rules(c.check_checkout([{"item": item(), "qty": 1}], broken))

    def test_inactive_pharmacy_blocks_ordering(self):
        assert c.PHARMACY_UNAVAILABLE in rules(c.check_checkout([{"item": item(), "qty": 1}],
                                                                {**PHARMACY, "active": False}))

    def test_missing_sfda_registration_on_prescription_item(self):
        assert c.MISSING_SFDA_REGISTRATION in rules(
            c.check_catalog_item(rx_item(sfda_registration_number=None)))

    def test_unknown_category_fails_closed(self):
        assert c.UNKNOWN_CATEGORY in rules(c.check_catalog_item(item(category="mystery")))

    def test_inactive_or_out_of_stock_item(self):
        assert c.ITEM_UNAVAILABLE in rules(c.check_add_to_cart(item(active=False), PHARMACY, 1))
        assert c.ITEM_OUT_OF_STOCK in rules(c.check_add_to_cart(item(stock_status="out_of_stock"),
                                                               PHARMACY, 1))

    def test_invalid_quantity(self):
        assert c.INVALID_QUANTITY in rules(c.check_add_to_cart(item(), PHARMACY, 0))

    def test_empty_cart(self):
        assert rules(c.check_checkout([], PHARMACY)) == [c.EMPTY_CART]

    def test_violations_are_deduplicated(self):
        entries = [{"item": rx_item(), "qty": 4}, {"item": rx_item(item_id="item_2"), "qty": 4}]
        out = c.check_checkout(entries, PHARMACY)
        assert len({(v["rule"], v["item_id"]) for v in out}) == len(out)
