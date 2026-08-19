"""Read-only patient data access for clinical agents.

Every function returns (data, document_ids). Agents never query the database directly,
so `agent_runs.input_refs` can record exactly which documents fed a generation.
"""
import json
from datetime import datetime, timedelta
from statistics import mean

from . import REFERENCE_DIR


def _srv():
    # Imported lazily: server.py imports this module at startup.
    import server
    return server


def _direction(values):
    if len(values) < 4:
        return "insufficient_data"
    half = len(values) // 2
    first, second = mean(values[:half]), mean(values[half:])
    if first == 0:
        return "stable"
    delta = (second - first) / abs(first) * 100
    if delta > 5:
        return "rising"
    if delta < -5:
        return "falling"
    return "stable"


async def get_health_profile(db, patient_user_id):
    srv = _srv()
    user = await db.users.find_one({"user_id": patient_user_id}, srv.USER_PROJECTION)
    if not user:
        return {"name": None, "profile_text": "", "health_profile": {}}, []
    return {
        "name": user.get("name"),
        "profile_text": srv.health_profile_context(user).strip(),
        "health_profile": user.get("health_profile") or {},
    }, [patient_user_id]


async def get_vitals_summary(db, profile_id, days=90):
    srv = _srv()
    since = srv.iso(srv.now_utc() - timedelta(days=days))
    docs = await db.vitals.find(
        {"profile_id": profile_id, "recorded_at": {"$gte": since}}, {"_id": 0}
    ).sort("recorded_at", 1).to_list(2000)

    metrics = {}
    for field, (lo, hi, unit, label) in srv.VITAL_RANGES.items():
        series = [(d["recorded_at"], d[field]) for d in docs if d.get(field) is not None]
        if not series:
            continue
        values = [v for _, v in series]
        out_of_range = [v for v in values if v < lo or v > hi]
        flagged = [d for d in docs if d.get(field) is not None and (d[field] < lo or d[field] > hi)]
        metrics[field] = {
            "label": label,
            "unit": unit,
            "normal_range": f"{lo}-{hi} {unit}",
            "readings": len(values),
            "latest": values[-1],
            "latest_at": series[-1][0],
            "min": min(values),
            "max": max(values),
            "mean": round(mean(values), 1),
            "direction": _direction(values),
            "out_of_range_count": len(out_of_range),
            # Citable document ids so answers can point at specific readings.
            "recent_readings": [
                {"vital_id": d["vital_id"], "recorded_at": d["recorded_at"], "value": d[field]}
                for d in docs[-5:] if d.get(field) is not None
            ],
            "out_of_range_readings": [
                {"vital_id": d["vital_id"], "recorded_at": d["recorded_at"], "value": d[field]}
                for d in flagged[-8:]
            ],
        }
    data = {
        "window_days": days,
        "total_readings": len(docs),
        "first_reading_at": docs[0]["recorded_at"] if docs else None,
        "last_reading_at": docs[-1]["recorded_at"] if docs else None,
        "metrics": metrics,
    }
    return data, [d["vital_id"] for d in docs]


async def get_medications_with_adherence(db, profile_id, days=90):
    srv = _srv()
    since_date = (srv.now_utc() - timedelta(days=days)).strftime("%Y-%m-%d")
    meds = await db.medications.find({"profile_id": profile_id, "active": True}, {"_id": 0}).to_list(100)
    logs = await db.dose_logs.find(
        {"profile_id": profile_id, "date": {"$gte": since_date}}, {"_id": 0}
    ).to_list(5000)

    out = []
    for med in meds:
        med_logs = [l for l in logs if l["medication_id"] == med["medication_id"]]
        taken = sum(1 for l in med_logs if l.get("status") == "taken")
        missed = sum(1 for l in med_logs if l.get("status") == "missed")
        total = taken + missed
        out.append({
            "medication_id": med["medication_id"],
            "name": med["name"],
            "dosage": med.get("dosage"),
            "times_per_day": len(med.get("times") or []),
            "instructions": med.get("instructions"),
            "started_at": med.get("created_at"),
            "doses_taken": taken,
            "doses_missed": missed,
            "adherence_pct": round(taken / total * 100) if total else None,
            "logged_doses": total,
        })
    return {"window_days": days, "medications": out}, [m["medication_id"] for m in meds]


async def get_recent_alerts(db, patient_user_id, days=90):
    srv = _srv()
    since = srv.iso(srv.now_utc() - timedelta(days=days))
    docs = await db.alerts.find(
        {"user_id": patient_user_id, "created_at": {"$gte": since}}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    data = [{
        "alert_id": a["alert_id"], "type": a.get("type"), "severity": a.get("severity"),
        "message": a.get("message"), "created_at": a.get("created_at"),
    } for a in docs]
    return {"window_days": days, "alerts": data}, [a["alert_id"] for a in docs]


async def get_recent_screening_reports(db, patient_user_id, limit=3, encounter_id=None, stale_days=90):
    srv = _srv()
    docs = await db.health_reports.find(
        {"user_id": patient_user_id}, {"_id": 0}
    ).sort("generated_at", -1).to_list(limit)
    now = srv.now_utc()
    data = []
    for r in docs:
        try:
            age_days = (now - datetime.fromisoformat(r["generated_at"])).days
        except (ValueError, TypeError):
            age_days = None
        data.append({
            "report_id": r["report_id"],
            "generated_at": r.get("generated_at"),
            "age_days": age_days,
            "stale": age_days is not None and age_days > stale_days,
            "shared_for_this_visit": bool(encounter_id) and r.get("shared_encounter_id") == encounter_id,
            "findings": r.get("findings") or [],
            "findings_extracted": bool(r.get("findings_extracted_at")),
            "content": (r.get("content") or "")[:4000],
        })
    return {"reports": data, "stale_after_days": stale_days}, [r["report_id"] for r in docs]


async def get_symptom_timeline(db, patient_user_id, days=180):
    """Groups structured screening findings by symptom so repetition over time is visible."""
    srv = _srv()
    since = srv.iso(srv.now_utc() - timedelta(days=days))
    docs = await db.health_reports.find(
        {"user_id": patient_user_id, "generated_at": {"$gte": since}}, {"_id": 0}
    ).sort("generated_at", 1).to_list(50)

    groups = {}
    for r in docs:
        for f in r.get("findings") or []:
            key = (f.get("symptom") or "").strip().lower()
            if not key:
                continue
            groups.setdefault(key, []).append({
                "finding_id": f["finding_id"],
                "report_id": r["report_id"],
                "generated_at": r["generated_at"],
                "severity": f.get("severity"),
                "onset": f.get("onset"),
                "patient_words": f.get("patient_words"),
            })

    timeline = [{
        "symptom": symptom,
        "times_reported": len(items),
        "first_reported_at": items[0]["generated_at"],
        "last_reported_at": items[-1]["generated_at"],
        "occurrences": items,
    } for symptom, items in sorted(groups.items(), key=lambda kv: -len(kv[1]))]
    return {"window_days": days, "symptoms": timeline}, [i["report_id"] for g in timeline for i in g["occurrences"]]


async def get_intake_responses(db, encounter_id):
    form = await db.intake_forms.find_one({"encounter_id": encounter_id}, {"_id": 0})
    if not form:
        return {"status": "not_generated", "answered": []}, []
    answers = {r["question_id"]: r for r in form.get("responses", [])}
    answered = [{
        "question_id": q["question_id"],
        "question": q["text"],
        "type": q["type"],
        "required": q.get("required", False),
        "answer": answers.get(q["question_id"], {}).get("answer"),
        "answered_at": answers.get(q["question_id"], {}).get("answered_at"),
    } for q in form.get("questions", [])]
    data = {
        "intake_form_id": form["intake_form_id"],
        "status": form["status"],
        "expires_at": form.get("expires_at"),
        "answered": answered,
        "unanswered_count": sum(1 for a in answered if a["answer"] in (None, "", [])),
    }
    return data, [form["intake_form_id"]]


def _load_interactions():
    return json.loads((REFERENCE_DIR / "interactions.json").read_text(encoding="utf-8"))


async def get_interaction_flags(db, profile_id):
    """Bounded reference lookup against a static table. No clinical judgement."""
    meds = await db.medications.find({"profile_id": profile_id, "active": True}, {"_id": 0}).to_list(100)
    ref = _load_interactions()
    names = [(m["medication_id"], (m.get("name") or "").lower()) for m in meds]

    def match(term):
        return [mid for mid, name in names if term.lower() in name]

    flags = []
    for pair in ref["pairs"]:
        a_matches, b_matches = match(pair["drug_a"]), match(pair["drug_b"])
        if a_matches and b_matches and set(a_matches) != set(b_matches):
            flags.append({
                "drug_a": pair["drug_a"], "drug_b": pair["drug_b"],
                "severity": pair["severity"], "note": pair["note"],
                "medication_ids": sorted(set(a_matches + b_matches)),
            })
    data = {"source": ref["source"], "version": ref["version"], "flags": flags}
    return data, [m["medication_id"] for m in meds]
