"""Triage: how soon should this patient be seen? Deterministic safety floor, no LLM.

These rules never diagnose. They set a **minimum** urgency for a screening based on red flags found in the
patient's own words and their recent vitals. The triage agent may raise the level; it can never lower it.
"""
import re

LEVELS = ("self_care", "routine_2w", "urgent_24h", "emergency_now")
TIMEFRAMES = {
    "emergency_now": "Right now — emergency care",
    "urgent_24h": "Within 24 hours",
    "routine_2w": "Within about two weeks",
    "self_care": "No visit needed for now",
}
EMERGENCY_NUMBER = "997"


def rank(level: str) -> int:
    return LEVELS.index(level) if level in LEVELS else 0


def highest(*levels) -> str:
    known = [l for l in levels if l in LEVELS]
    return max(known, key=rank) if known else "self_care"


# any: fires when ONE phrase is present. all: every phrase group must have a hit.
RED_FLAGS = [
    {"code": "CHEST_PAIN", "level": "emergency_now", "label": "Chest pain or pressure",
     "any": ["chest pain", "pain in my chest", "chest pressure", "chest tightness", "tight chest",
             "ألم في الصدر", "ضغط في الصدر", "ضيق في الصدر"],
     "guidance": "Chest pain can be a heart attack. This is not something to book for later."},
    {"code": "STROKE_SIGNS", "level": "emergency_now", "label": "Possible stroke signs",
     "any": ["face droop", "slurred speech", "can't speak", "cannot speak", "weakness on one side",
             "one side of my body", "sudden numbness", "شلل", "تلعثم", "ضعف في جهة واحدة"],
     "guidance": "Sudden weakness, drooping or speech trouble needs emergency care within minutes."},
    {"code": "SEVERE_BREATHLESSNESS", "level": "emergency_now", "label": "Severe breathlessness",
     "any": ["can't breathe", "cannot breathe", "struggling to breathe", "gasping",
             "breathless at rest", "ضيق نفس شديد", "لا أستطيع التنفس"],
     "guidance": "Trouble breathing at rest is an emergency."},
    {"code": "ANAPHYLAXIS", "level": "emergency_now", "label": "Possible severe allergic reaction",
     "any": ["throat swelling", "tongue swelling", "throat closing", "anaphyla", "تورم الحلق",
             "تورم اللسان"],
     "guidance": "A swelling throat or tongue can close the airway. Emergency care now."},
    {"code": "SELF_HARM", "level": "emergency_now", "label": "Thoughts of self-harm",
     "any": ["suicide", "suicidal", "kill myself", "end my life", "hurt myself", "الانتحار",
             "إيذاء نفسي"],
     "guidance": "You deserve immediate support. Please reach emergency services or a crisis line now."},
    {"code": "HEAVY_BLEEDING", "level": "emergency_now", "label": "Heavy or uncontrolled bleeding",
     "any": ["heavy bleeding", "bleeding won't stop", "bleeding that won't stop", "vomiting blood",
             "blood in my vomit", "black stool", "نزيف شديد", "دم في القيء"],
     "guidance": "Bleeding that does not stop, or blood in vomit or stool, is an emergency."},
    {"code": "PREGNANCY_BLEEDING", "level": "emergency_now", "label": "Bleeding in pregnancy",
     "all": [["pregnant", "pregnancy", "حامل"], ["bleeding", "blood", "نزيف"]],
     "guidance": "Bleeding during pregnancy needs to be seen straight away."},
    {"code": "SEIZURE", "level": "emergency_now", "label": "Seizure",
     "any": ["seizure", "convulsion", "fitting", "تشنج", "نوبة صرع"],
     "guidance": "A new seizure needs emergency assessment."},
    {"code": "SUDDEN_VISION_LOSS", "level": "emergency_now", "label": "Sudden vision loss",
     "any": ["sudden vision loss", "lost my vision", "went blind", "فقدان البصر"],
     "guidance": "Sudden loss of vision must be seen immediately."},
    {"code": "FAINTING", "level": "urgent_24h", "label": "Fainting or blackout",
     "any": ["fainted", "passed out", "blacked out", "loss of consciousness", "إغماء"],
     "guidance": "Losing consciousness needs to be checked quickly."},
    {"code": "HEAD_INJURY", "level": "urgent_24h", "label": "Head injury",
     "any": ["hit my head", "head injury", "fell on my head", "ارتجاج", "ضربة في الرأس"],
     "guidance": "A head injury should be assessed within the day."},
    {"code": "INFANT_FEVER", "level": "urgent_24h", "label": "Fever in a baby",
     "all": [["baby", "infant", "newborn", "رضيع", "مولود"], ["fever", "temperature", "حرارة", "حمى"]],
     "guidance": "Fever in a baby is assessed the same day."},
    {"code": "PERSISTENT_FEVER", "level": "urgent_24h", "label": "Fever that will not settle",
     "all": [["fever", "high temperature", "حمى", "حرارة"],
             ["five days", "5 days", "six days", "6 days", "a week", "أسبوع"]],
     "guidance": "A fever lasting close to a week needs a clinician to look at it."},
    {"code": "SEVERE_DEHYDRATION", "level": "urgent_24h", "label": "Possible dehydration",
     "all": [["vomiting", "diarrhoea", "diarrhea", "قيء", "إسهال"],
             ["can't keep", "cannot keep", "no urine", "not urinating", "dizzy", "دوخة"]],
     "guidance": "Not keeping fluids down needs same-day care."},
]

VITAL_RULES = [
    ("systolic", lambda v: v <= 90, "emergency_now", "Very low blood pressure recorded"),
    ("systolic", lambda v: v >= 180, "urgent_24h", "Very high blood pressure recorded"),
    ("diastolic", lambda v: v >= 120, "urgent_24h", "Very high diastolic pressure recorded"),
    ("heart_rate", lambda v: v >= 130, "urgent_24h", "Very fast heart rate recorded"),
    ("heart_rate", lambda v: v <= 45, "urgent_24h", "Very slow heart rate recorded"),
    ("spo2", lambda v: v <= 88, "emergency_now", "Very low oxygen saturation recorded"),
    ("spo2", lambda v: 88 < v <= 92, "urgent_24h", "Low oxygen saturation recorded"),
    ("temperature", lambda v: v >= 39.5, "urgent_24h", "High fever recorded"),
    # Glucose is stored in mg/dL.
    ("glucose", lambda v: v <= 54, "emergency_now", "Dangerously low blood sugar recorded"),
    ("glucose", lambda v: v >= 300, "urgent_24h", "Very high blood sugar recorded"),
]


def _norm(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _hit(haystack, phrase):
    return _norm(phrase) in haystack


def detect_red_flags(findings, vitals=None) -> list:
    """Deterministic scan of the patient's own words plus their latest vitals."""
    flags = []
    for finding in findings or []:
        haystack = _norm(f"{finding.get('symptom', '')} {finding.get('patient_words', '')}")
        if not haystack:
            continue
        for rule in RED_FLAGS:
            matched = False
            if "any" in rule:
                matched = any(_hit(haystack, p) for p in rule["any"])
            elif "all" in rule:
                matched = all(any(_hit(haystack, p) for p in group) for group in rule["all"])
            if matched and not any(f["code"] == rule["code"] for f in flags):
                flags.append({"code": rule["code"], "label": rule["label"], "level": rule["level"],
                              "guidance": rule["guidance"], "finding_id": finding.get("finding_id"),
                              "source": "symptom"})
        if finding.get("severity") == "severe" and not any(f["code"] == "SEVERE_SYMPTOM" for f in flags):
            flags.append({"code": "SEVERE_SYMPTOM", "label": "A symptom described as severe",
                          "level": "urgent_24h",
                          "guidance": "A symptom this severe should be seen within the day.",
                          "finding_id": finding.get("finding_id"), "source": "symptom"})

    metrics = (vitals or {}).get("metrics") or {}
    for metric, test, level, label in VITAL_RULES:
        value = (metrics.get(metric) or {}).get("latest")
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if test(numeric) and not any(f["code"] == f"VITAL_{metric.upper()}_{level}" for f in flags):
            flags.append({"code": f"VITAL_{metric.upper()}_{level}", "label": f"{label} ({numeric})",
                          "level": level, "guidance": "A recorded reading outside the safe range.",
                          "finding_id": None, "source": "vitals"})
    return flags


def floor_level(flags) -> str:
    """The lowest urgency the disposition is allowed to be."""
    return highest(*[f["level"] for f in flags]) if flags else "self_care"
