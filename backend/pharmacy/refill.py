"""Deterministic refill engine. Plain arithmetic over medications and dose_logs — no LLM, no guessing.

A medication is never silently swapped for a different product: a match is only suggested when the
generic name (or the exact trade name) lines up, and the user still has to confirm it in the UI.
"""
import math
import os
import re
from datetime import datetime, timezone, timedelta

REFILL_LEAD_DAYS = int(os.environ.get("REFILL_LEAD_DAYS", "7"))
UPCOMING_WINDOW_DAYS = 30


def _norm(text):
    out = re.sub(r"[^a-z0-9\u0600-\u06ff ]+", " ", (text or "").lower())
    out = re.sub(r"(\d)\s+(mg|mcg|ml|g|iu|%)", r"\1\2", out)
    return re.sub(r"\s+", " ", out).strip()


def daily_units(med: dict) -> float:
    times = med.get("times") or []
    return max(len(times), 1) * float(med.get("units_per_dose") or 1)


def project(med: dict, taken_doses: int, today: datetime = None) -> dict:
    """Returns days_remaining / projected_runout_date, or None values when the pack is unknown."""
    today = today or datetime.now(timezone.utc)
    quantity = med.get("quantity_dispensed")
    dispensed_on = med.get("dispensed_on")
    per_day = daily_units(med)
    if not quantity or not dispensed_on:
        return {"days_remaining": None, "projected_runout_date": None, "units_remaining": None,
                "daily_units": per_day, "doses_taken": taken_doses}
    consumed = taken_doses * float(med.get("units_per_dose") or 1)
    units_remaining = max(float(quantity) - consumed, 0.0)
    days_remaining = int(math.floor(units_remaining / per_day)) if per_day else None
    runout = (today + timedelta(days=days_remaining)).date().isoformat() if days_remaining is not None else None
    return {"days_remaining": days_remaining, "projected_runout_date": runout,
            "units_remaining": round(units_remaining, 2), "daily_units": per_day,
            "doses_taken": taken_doses}


def match_catalog(med: dict, catalog: list) -> dict:
    """High confidence only on an exact generic or exact trade-name match. Otherwise no suggestion."""
    name = _norm(med.get("name"))
    dosage = _norm(med.get("dosage"))
    name_with_dose = _norm(f"{med.get('name')} {med.get('dosage')}")
    candidates = []
    for item in catalog:
        if item.get("is_controlled") or not item.get("active", False):
            continue
        strength = _norm(item.get("strength"))
        trade_en = _norm(item.get("name_en"))
        trade_bare = trade_en.replace(strength, "").strip() if strength else trade_en
        names = {_norm(item.get("generic_name")), trade_en, trade_bare, _norm(item.get("name_ar"))}
        names.discard("")
        score = None
        if name_with_dose and name_with_dose == trade_en:
            score = 0.95
        elif name and name in names:
            score = 0.95 if dosage and strength == dosage else 0.85
        if score:
            candidates.append((score, item))
    if not candidates:
        return {"confidence": "none", "item": None, "matches": [], "search_query": med.get("name")}
    candidates.sort(key=lambda c: -c[0])
    score, item = candidates[0]
    return {"confidence": "high" if score >= 0.85 else "low", "score": score, "item": item,
            "matches": [c[1] for c in candidates if c[0] >= 0.85],
            "search_query": med.get("name"), "requires_user_confirmation": True}


def _sponsor_key(pharmacy: dict, now_iso: str):
    sponsorship = (pharmacy or {}).get("sponsorship") or {}
    active = bool(sponsorship.get("tier")) and (not sponsorship.get("active_until")
                                                or sponsorship["active_until"] > now_iso)
    return (0 if active else 1, sponsorship.get("rank") or 99)


async def compute_refills(db, profile_id: str, lead_days: int = REFILL_LEAD_DAYS,
                          today: datetime = None) -> dict:
    today = today or datetime.now(timezone.utc)
    meds = await db.medications.find({"profile_id": profile_id, "active": True}, {"_id": 0}).to_list(100)
    catalog = await db.catalog_items.find({"active": True}, {"_id": 0}).to_list(1000)
    pharmacies = {p["pharmacy_id"]: p for p in
                  await db.pharmacies.find({"active": True}, {"_id": 0}).to_list(100)}

    due, upcoming, unknown = [], [], []
    for med in meds:
        logs = await db.dose_logs.find(
            {"medication_id": med["medication_id"], "status": "taken",
             **({"date": {"$gte": (med.get("dispensed_on") or "")[:10]}} if med.get("dispensed_on") else {})},
            {"_id": 0, "date": 1},
        ).to_list(2000)
        window = await db.dose_logs.find({"medication_id": med["medication_id"]}, {"_id": 0, "status": 1}
                                         ).to_list(2000)
        taken = len(logs)
        logged = [l for l in window if l["status"] in ("taken", "missed")]
        adherence = round(sum(1 for l in logged if l["status"] == "taken") / len(logged) * 100, 1) \
            if logged else None

        projection = project(med, taken, today=today)
        match = match_catalog(med, catalog)
        now_iso = today.isoformat()
        offers = []
        if match["confidence"] == "high":
            for item in match["matches"]:
                pharmacy = pharmacies.get(item["pharmacy_id"])
                if not pharmacy:
                    continue
                offers.append({"item": item, "pharmacy": {k: pharmacy.get(k) for k in (
                    "pharmacy_id", "name_en", "name_ar", "sfda_license", "moh_license", "cr_number",
                    "fulfilment_mode")}, "sponsored": _sponsor_key(pharmacy, now_iso)[0] == 0})
            offers.sort(key=lambda o: (_sponsor_key(pharmacies[o["item"]["pharmacy_id"]], now_iso),
                                       o["item"]["price_sar"]))
        row = {
            "medication_id": med["medication_id"],
            "name": med["name"],
            "dosage": med.get("dosage"),
            "times_per_day": len(med.get("times") or []),
            "adherence_percent": adherence,
            **projection,
            "suggested_item": offers[0]["item"] if offers else None,
            "offers": offers,
            "match_confidence": match["confidence"],
            "requires_user_confirmation": True,
            "search_query": match["search_query"],
            "pharmacy": offers[0]["pharmacy"] if offers else None,
        }
        if projection["days_remaining"] is None:
            unknown.append(row)
        elif projection["days_remaining"] <= lead_days:
            due.append(row)
        elif projection["days_remaining"] <= UPCOMING_WINDOW_DAYS:
            upcoming.append(row)

    due.sort(key=lambda r: r["days_remaining"])
    upcoming.sort(key=lambda r: r["days_remaining"])
    return {"lead_days": lead_days, "due": due, "upcoming": upcoming, "unknown": unknown}


async def raise_refill_alerts(db, user_id: str, profile_id: str, refills: dict) -> int:
    """One open refill alert per medication, through the existing alerts collection."""
    raised = 0
    for row in refills["due"]:
        existing = await db.alerts.find_one(
            {"profile_id": profile_id, "type": "refill", "medication_id": row["medication_id"],
             "read": False}, {"_id": 0})
        if existing:
            continue
        await db.alerts.insert_one({
            "alert_id": f"alert_{uuid_hex()}",
            "user_id": user_id,
            "profile_id": profile_id,
            "type": "refill",
            "severity": "info",
            "medication_id": row["medication_id"],
            "message": f"{row['name']} runs out in {row['days_remaining']} day(s) — time to reorder",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        raised += 1
    return raised


def uuid_hex():
    import uuid
    return uuid.uuid4().hex[:12]


