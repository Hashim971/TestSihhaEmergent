"""Unit tests for the deterministic refill engine — arithmetic and safe matching only."""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pharmacy import refill  # noqa: E402

TODAY = datetime(2026, 6, 20, tzinfo=timezone.utc)


def med(**over):
    base = {"medication_id": "med_1", "name": "Concor", "dosage": "5 mg", "times": ["08:00"],
            "quantity_dispensed": 30, "units_per_dose": 1,
            "dispensed_on": (TODAY - timedelta(days=26)).isoformat()}
    base.update(over)
    return base


def catalog_item(**over):
    base = {"item_id": "item_1", "pharmacy_id": "pharm_1", "name_en": "Concor 5mg",
            "name_ar": "كونكور ٥ ملغ", "generic_name": "Bisoprolol", "strength": "5 mg",
            "is_controlled": False, "active": True, "price_sar": 42.5}
    base.update(over)
    return base


class TestArithmetic:
    def test_daily_units_uses_times_and_units_per_dose(self):
        assert refill.daily_units(med(times=["08:00", "20:00"], units_per_dose=2)) == 4

    def test_twenty_six_taken_of_thirty_leaves_four_days(self):
        p = refill.project(med(), taken_doses=26, today=TODAY)
        assert p["days_remaining"] == 4
        assert p["projected_runout_date"] == "2026-06-24"

    def test_thirty_days_left_is_not_due(self):
        p = refill.project(med(quantity_dispensed=35), taken_doses=5, today=TODAY)
        assert p["days_remaining"] == 30

    def test_twice_daily_halves_the_runway(self):
        p = refill.project(med(times=["08:00", "20:00"], quantity_dispensed=20), taken_doses=0,
                           today=TODAY)
        assert p["days_remaining"] == 10

    def test_unknown_pack_gives_no_projection(self):
        p = refill.project(med(quantity_dispensed=None), taken_doses=10, today=TODAY)
        assert p["days_remaining"] is None and p["projected_runout_date"] is None

    def test_consumption_never_goes_negative(self):
        p = refill.project(med(), taken_doses=99, today=TODAY)
        assert p["units_remaining"] == 0 and p["days_remaining"] == 0


class TestMatching:
    def test_trade_name_with_strength_matches(self):
        m = refill.match_catalog(med(), [catalog_item()])
        assert m["confidence"] == "high" and m["item"]["item_id"] == "item_1"
        assert m["requires_user_confirmation"] is True

    def test_generic_name_matches(self):
        m = refill.match_catalog(med(name="Bisoprolol"), [catalog_item()])
        assert m["confidence"] == "high"

    def test_a_different_generic_is_never_suggested(self):
        m = refill.match_catalog(med(name="Lisinopril"), [catalog_item()])
        assert m["confidence"] == "none" and m["item"] is None
        assert m["search_query"] == "Lisinopril"

    def test_partial_name_does_not_match(self):
        m = refill.match_catalog(med(name="Con"), [catalog_item()])
        assert m["confidence"] == "none"

    def test_controlled_items_are_never_suggested(self):
        m = refill.match_catalog(med(), [catalog_item(is_controlled=True)])
        assert m["confidence"] == "none"

    def test_all_matching_offers_are_returned_for_comparison(self):
        second = catalog_item(item_id="item_2", pharmacy_id="pharm_2", price_sar=39.95)
        m = refill.match_catalog(med(), [catalog_item(), second])
        assert len(m["matches"]) == 2
