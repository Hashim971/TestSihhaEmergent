"""Unit tests for triage/rules.py — the deterministic safety floor. No I/O, no LLM."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from triage import rules  # noqa: E402


def finding(symptom, words, severity="moderate", fid="find_1"):
    return {"finding_id": fid, "symptom": symptom, "patient_words": words, "severity": severity}


def codes(flags):
    return [f["code"] for f in flags]


class TestEmergencyFlags:
    def test_chest_pain(self):
        flags = rules.detect_red_flags([finding("Chest pain", "I have chest pain since morning")])
        assert "CHEST_PAIN" in codes(flags)
        assert rules.floor_level(flags) == "emergency_now"

    def test_stroke_signs(self):
        flags = rules.detect_red_flags([finding("Speech", "my speech is slurred and my face droops")])
        assert "STROKE_SIGNS" in codes(flags) and rules.floor_level(flags) == "emergency_now"

    def test_self_harm(self):
        flags = rules.detect_red_flags([finding("Mood", "sometimes I think about suicide", "mild")])
        assert "SELF_HARM" in codes(flags) and rules.floor_level(flags) == "emergency_now"

    def test_arabic_chest_pain_is_caught(self):
        flags = rules.detect_red_flags([finding("ألم", "عندي ألم في الصدر منذ الصباح")])
        assert "CHEST_PAIN" in codes(flags)

    def test_two_part_rule_needs_both_halves(self):
        one = rules.detect_red_flags([finding("Bleeding", "some bleeding today")])
        both = rules.detect_red_flags([finding("Bleeding", "I am pregnant and there is bleeding")])
        assert "PREGNANCY_BLEEDING" not in codes(one)
        assert "PREGNANCY_BLEEDING" in codes(both)


class TestUrgentFlags:
    def test_fainting_is_urgent_not_emergency(self):
        flags = rules.detect_red_flags([finding("Fainting", "I passed out at work")])
        assert rules.floor_level(flags) == "urgent_24h"

    def test_severe_severity_alone_raises_to_urgent(self):
        flags = rules.detect_red_flags([finding("Back pain", "my back hurts a lot", "severe")])
        assert codes(flags) == ["SEVERE_SYMPTOM"] and rules.floor_level(flags) == "urgent_24h"

    def test_infant_fever(self):
        flags = rules.detect_red_flags([finding("Fever", "my baby has a fever since last night")])
        assert "INFANT_FEVER" in codes(flags) and rules.floor_level(flags) == "urgent_24h"


class TestNoFlags:
    def test_mild_rash_has_no_floor(self):
        flags = rules.detect_red_flags([finding("Rash", "a small itchy rash on my arm", "mild")])
        assert flags == [] and rules.floor_level(flags) == "self_care"

    def test_empty_findings(self):
        assert rules.detect_red_flags([]) == []
        assert rules.detect_red_flags(None) == []


class TestVitals:
    def _vitals(self, metric, value):
        return {"metrics": {metric: {"latest": value}}}

    def test_low_oxygen_is_an_emergency(self):
        flags = rules.detect_red_flags([], self._vitals("spo2", 85))
        assert rules.floor_level(flags) == "emergency_now"

    def test_borderline_oxygen_is_urgent(self):
        flags = rules.detect_red_flags([], self._vitals("spo2", 91))
        assert rules.floor_level(flags) == "urgent_24h"

    def test_high_blood_pressure_is_urgent(self):
        assert rules.floor_level(rules.detect_red_flags([], self._vitals("systolic", 190))) == "urgent_24h"

    def test_normal_vitals_produce_nothing(self):
        assert rules.detect_red_flags([], self._vitals("systolic", 120)) == []

    def test_glucose_is_read_in_mg_dl(self):
        assert rules.detect_red_flags([], self._vitals("glucose", 110)) == []
        assert rules.floor_level(rules.detect_red_flags([], self._vitals("glucose", 45))) == "emergency_now"

    def test_garbage_values_are_ignored(self):
        assert rules.detect_red_flags([], {"metrics": {"spo2": {"latest": "n/a"}}}) == []


class TestLevelMaths:
    def test_ordering(self):
        assert rules.rank("emergency_now") > rules.rank("urgent_24h") > rules.rank("routine_2w")

    def test_highest_wins(self):
        assert rules.highest("self_care", "urgent_24h", "routine_2w") == "urgent_24h"

    def test_unknown_levels_are_ignored(self):
        assert rules.highest("nonsense", "routine_2w") == "routine_2w"

    def test_every_level_has_a_timeframe(self):
        assert all(level in rules.TIMEFRAMES for level in rules.LEVELS)
