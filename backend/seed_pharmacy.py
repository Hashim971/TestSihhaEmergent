"""Phase 6 seed: partner pharmacies, catalog and one patient four days from running out.

Run: cd /app/backend && set -a && . ./.env && set +a && python seed_pharmacy.py
Idempotent — it clears the seeded pharmacies, their catalog and the seeded medication first.
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta

from motor.motor_asyncio import AsyncIOMotorClient

REFILL_PATIENT_EMAIL = "omar.patient@sihha.ai"


def iso(dt=None):
    return (dt or datetime.now(timezone.utc)).isoformat()


def pid(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


PHARMACIES = [
    {
        "name_en": "Nahdi Pharmacy", "name_ar": "صيدلية النهدي",
        "sfda_license": "SFDA-PH-DEMO-100241", "moh_license": "MOH-RUH-DEMO-55120",
        "cr_number": "CR-1010DEMO4471",
        "fulfilment_mode": "handoff",
        "handoff_url_template": "https://partner.nahdi.example/cart?items={sku_list}&branch={branch_id}",
        "sponsorship": {"tier": "gold", "rank": 1, "active_until": None},
        "branches": [
            {"branch_id": "br_nahdi_olaya", "city": "Riyadh", "lat": 24.6944, "lng": 46.6853,
             "delivery_zones": ["Olaya", "Sulaimaniyah", "Malaz"], "hours": "08:00–00:00 daily"},
            {"branch_id": "br_nahdi_jeddah", "city": "Jeddah", "lat": 21.5810, "lng": 39.1653,
             "delivery_zones": ["Al Hamra", "Ar Rawdah"], "hours": "09:00–01:00 daily"},
        ],
    },
    {
        "name_en": "Al Dawaa Pharmacy", "name_ar": "صيدلية الدواء",
        "sfda_license": "SFDA-PH-DEMO-100987", "moh_license": "MOH-RUH-DEMO-55901",
        "cr_number": "CR-2050DEMO8812",
        "fulfilment_mode": "in_app",
        "handoff_url_template": None,
        "sponsorship": {"tier": None, "rank": None, "active_until": None},
        "branches": [
            {"branch_id": "br_dawaa_narjis", "city": "Riyadh", "lat": 24.8384, "lng": 46.6469,
             "delivery_zones": ["Narjis", "Yasmin", "Nakheel"], "hours": "08:00–23:00 daily"},
        ],
    },
]

# (name_en, name_ar, generic, form, strength, category, rx, controlled, pack, days, price, both_pharmacies)
CATALOG = [
    ("Concor 5mg", "كونكور ٥ ملغ", "Bisoprolol", "tablet", "5 mg", "prescription", True, False, 30, 30, 42.50, True),
    ("Glucophage 500mg", "جلوكوفاج ٥٠٠ ملغ", "Metformin", "tablet", "500 mg", "prescription", True, False, 30, 30, 26.00, True),
    ("Lipitor 20mg", "ليبيتور ٢٠ ملغ", "Atorvastatin", "tablet", "20 mg", "prescription", True, False, 30, 30, 68.00, True),
    ("Amaryl 2mg", "أماريل ٢ ملغ", "Glimepiride", "tablet", "2 mg", "prescription", True, False, 30, 30, 39.75, True),
    ("Norvasc 5mg", "نورفاسك ٥ ملغ", "Amlodipine", "tablet", "5 mg", "prescription", True, False, 30, 30, 33.00, True),
    ("Ventolin Inhaler", "فينتولين بخاخ", "Salbutamol", "inhaler", "100 mcg", "prescription", True, False, 1, 30, 21.50, True),
    ("Augmentin 625mg", "أوجمنتين ٦٢٥ ملغ", "Amoxicillin/Clavulanate", "tablet", "625 mg", "prescription", True, False, 21, 7, 47.00, True),
    ("Nexium 40mg", "نيكسيوم ٤٠ ملغ", "Esomeprazole", "capsule", "40 mg", "prescription", True, False, 28, 28, 88.00, True),
    ("Euthyrox 50mcg", "يوثيروكس ٥٠ ميكروغرام", "Levothyroxine", "tablet", "50 mcg", "prescription", True, False, 50, 50, 24.00, True),
    ("Diamicron MR 60mg", "ديامكرون ٦٠ ملغ", "Gliclazide", "tablet", "60 mg", "prescription", True, False, 30, 30, 55.00, True),

    ("Tramal 50mg", "ترامال ٥٠ ملغ", "Tramadol", "capsule", "50 mg", "prescription", True, True, 20, 10, 0.0, False),
    ("Rivotril 0.5mg", "ريفوتريل ٠٫٥ ملغ", "Clonazepam", "tablet", "0.5 mg", "prescription", True, True, 30, 30, 0.0, False),
    ("Concerta 18mg", "كونسيرتا ١٨ ملغ", "Methylphenidate", "tablet", "18 mg", "prescription", True, True, 30, 30, 0.0, False),

    ("Panadol Extra", "بنادول إكسترا", "Paracetamol/Caffeine", "tablet", "500 mg", "otc", False, False, 24, None, 17.00, True),
    ("Panadol Advance", "بنادول أدفانس", "Paracetamol", "tablet", "500 mg", "otc", False, False, 24, None, 14.00, False),
    ("Brufen 400mg", "بروفين ٤٠٠ ملغ", "Ibuprofen", "tablet", "400 mg", "otc", False, False, 20, None, 19.50, True),
    ("Strepsils Honey & Lemon", "ستربسلز عسل وليمون", "Amylmetacresol", "lozenge", "1.2 mg", "otc", False, False, 24, None, 22.00, False),
    ("Otrivin Nasal Spray", "أوتريفين بخاخ للأنف", "Xylometazoline", "spray", "0.1%", "otc", False, False, 1, None, 18.75, False),
    ("Gaviscon Double Action", "جافيسكون", "Alginate", "suspension", "300 ml", "otc", False, False, 1, None, 31.00, True),
    ("Zyrtec 10mg", "زيرتك ١٠ ملغ", "Cetirizine", "tablet", "10 mg", "otc", False, False, 20, None, 27.50, False),
    ("Voltaren Emulgel", "فولتارين جل", "Diclofenac", "gel", "1%", "otc", False, False, 1, None, 36.00, True),
    ("Buscopan 10mg", "بوسكوبان ١٠ ملغ", "Hyoscine", "tablet", "10 mg", "otc", False, False, 20, None, 23.00, False),
    ("Fenistil Gel", "فينيستيل جل", "Dimetindene", "gel", "0.1%", "otc", False, False, 1, None, 25.00, False),

    ("Vitamin D3 50000 IU", "فيتامين د ٥٠٠٠٠", "Cholecalciferol", "capsule", "50000 IU", "supplement", False, False, 8, None, 45.00, True),
    ("Centrum Adults", "سنتروم للبالغين", "Multivitamin", "tablet", "-", "supplement", False, False, 60, None, 92.00, True),
    ("Omega 3 1000mg", "أوميغا ٣ ١٠٠٠ ملغ", "Fish oil", "capsule", "1000 mg", "supplement", False, False, 60, None, 78.00, False),
    ("Ferrous Sulfate 200mg", "كبريتات الحديد", "Ferrous sulfate", "tablet", "200 mg", "supplement", False, False, 30, None, 19.00, False),
    ("Calcium + D3", "كالسيوم مع د٣", "Calcium carbonate", "tablet", "600 mg", "supplement", False, False, 60, None, 54.00, True),
    ("Zinc 50mg", "زنك ٥٠ ملغ", "Zinc gluconate", "tablet", "50 mg", "supplement", False, False, 30, None, 33.00, False),
    ("Magnesium 400mg", "مغنيسيوم ٤٠٠ ملغ", "Magnesium oxide", "tablet", "400 mg", "supplement", False, False, 60, None, 61.00, False),
    ("Vitamin C 1000mg", "فيتامين سي ١٠٠٠ ملغ", "Ascorbic acid", "effervescent", "1000 mg", "supplement", False, False, 20, None, 29.00, True),

    ("Omron M2 Blood Pressure Monitor", "جهاز قياس ضغط أومرون", None, "device", "-", "device", False, False, 1, None, 245.00, True),
    ("Accu-Chek Instant Glucometer", "جهاز سكر أكيوتشيك", None, "device", "-", "device", False, False, 1, None, 189.00, True),
    ("Accu-Chek Test Strips (50)", "شرائط سكر أكيوتشيك", None, "strips", "50 strips", "device", False, False, 50, None, 115.00, True),
    ("Digital Thermometer", "ميزان حرارة رقمي", None, "device", "-", "device", False, False, 1, None, 39.00, False),
    ("Fingertip Pulse Oximeter", "مقياس تشبع الأكسجين", None, "device", "-", "device", False, False, 1, None, 129.00, False),
    ("Compressor Nebulizer", "جهاز استنشاق", None, "device", "-", "device", False, False, 1, None, 275.00, False),

    ("Cetaphil Gentle Cleanser", "سيتافيل منظف", None, "lotion", "236 ml", "personal_care", False, False, 1, None, 68.00, True),
    ("La Roche-Posay Sunscreen SPF50", "لاروش بوزيه واقي شمس", None, "cream", "50 ml", "personal_care", False, False, 1, None, 135.00, True),
    ("Baby Wipes (72)", "مناديل أطفال", None, "wipes", "72 pcs", "personal_care", False, False, 1, None, 12.50, False),
    ("Sensodyne Toothpaste", "معجون سنسوداين", None, "paste", "75 ml", "personal_care", False, False, 1, None, 26.00, False),
    ("Hand Sanitizer 500ml", "معقم يدين", None, "gel", "500 ml", "personal_care", False, False, 1, None, 21.00, False),
    ("Nivea Body Moisturiser", "نيفيا مرطب", None, "lotion", "400 ml", "personal_care", False, False, 1, None, 34.00, True),
]

STOCK_CYCLE = ["in_stock", "in_stock", "in_stock", "low", "in_stock", "out_of_stock"]


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    names = [p["name_en"] for p in PHARMACIES]
    old = await db.pharmacies.find({"name_en": {"$in": names}}, {"_id": 0, "pharmacy_id": 1}).to_list(10)
    if old:
        await db.catalog_items.delete_many({"pharmacy_id": {"$in": [p["pharmacy_id"] for p in old]}})
    await db.pharmacies.delete_many({"name_en": {"$in": names}})

    pharmacy_ids = []
    for spec in PHARMACIES:
        doc = {"pharmacy_id": pid("pharm"), **spec, "active": True,
               "created_at": iso(), "updated_at": iso()}
        await db.pharmacies.insert_one(dict(doc))
        pharmacy_ids.append(doc["pharmacy_id"])
        print(f"pharmacy {doc['name_en']} ({doc['fulfilment_mode']}) -> {doc['pharmacy_id']}")

    inserted = 0
    for idx, row in enumerate(CATALOG):
        (name_en, name_ar, generic, form, strength, category, rx, controlled,
         pack, days, price, both) = row
        targets = pharmacy_ids if both else [pharmacy_ids[idx % 2]]
        for n, pharmacy_id in enumerate(targets):
            markup = 1.0 if n == 0 else 0.94
            item = {
                "item_id": pid("item"),
                "pharmacy_id": pharmacy_id,
                "sfda_registration_number": f"SFDA-REG-{20000 + idx}" if rx else None,
                "sku": f"SKU-{idx:03d}-{n}",
                "name_en": name_en,
                "name_ar": name_ar,
                "generic_name": generic,
                "form": form,
                "strength": strength,
                "category": category,
                "requires_prescription": rx,
                "is_controlled": controlled,
                "pack_size": pack,
                "days_supply": days,
                "price_sar": round((price or 0) * markup, 2),
                "stock_status": STOCK_CYCLE[(idx + n) % len(STOCK_CYCLE)] if not controlled else "in_stock",
                "image_url": None,
                "active": True,
                "created_at": iso(),
                "updated_at": iso(),
            }
            await db.catalog_items.insert_one(dict(item))
            inserted += 1
    print(f"catalog items: {inserted}")

    patient = await db.users.find_one({"email": REFILL_PATIENT_EMAIL}, {"_id": 0, "user_id": 1})
    if not patient:
        print(f"! {REFILL_PATIENT_EMAIL} not found — run seed_phase1.py first")
        return
    profile_id = patient["user_id"]
    await db.medications.delete_many({"profile_id": profile_id, "name": "Concor"})
    dispensed_on = datetime.now(timezone.utc) - timedelta(days=26)
    med = {
        "medication_id": pid("med"),
        "user_id": patient["user_id"],
        "profile_id": profile_id,
        "name": "Concor",
        "dosage": "5 mg",
        "times": ["08:00"],
        "instructions": "One tablet in the morning with water",
        "quantity_dispensed": 30,
        "units_per_dose": 1,
        "dispensed_on": iso(dispensed_on),
        "active": True,
        "created_at": iso(),
    }
    await db.medications.insert_one(dict(med))
    await db.dose_logs.delete_many({"medication_id": med["medication_id"]})
    for day in range(26):
        date = (dispensed_on + timedelta(days=day)).strftime("%Y-%m-%d")
        await db.dose_logs.insert_one({
            "dose_log_id": pid("dose"), "medication_id": med["medication_id"],
            "user_id": patient["user_id"], "profile_id": profile_id,
            "date": date, "time": "08:00", "status": "taken", "logged_at": iso(),
        })
    print(f"medication {med['name']} -> 26 taken doses, 4 days remaining ({med['medication_id']})")

    # A second medication far from runout, so the "not due" case is covered too.
    await db.medications.delete_many({"profile_id": profile_id, "name": "Glucophage"})
    long_dispense = datetime.now(timezone.utc) - timedelta(days=5)
    long_med = {
        "medication_id": pid("med"), "user_id": patient["user_id"], "profile_id": profile_id,
        "name": "Glucophage", "dosage": "500 mg", "times": ["08:00"],
        "instructions": "One tablet after breakfast", "quantity_dispensed": 35, "units_per_dose": 1,
        "dispensed_on": iso(long_dispense), "active": True, "created_at": iso(),
    }
    await db.medications.insert_one(dict(long_med))
    await db.dose_logs.delete_many({"medication_id": long_med["medication_id"]})
    for day in range(5):
        await db.dose_logs.insert_one({
            "dose_log_id": pid("dose"), "medication_id": long_med["medication_id"],
            "user_id": patient["user_id"], "profile_id": profile_id,
            "date": (long_dispense + timedelta(days=day)).strftime("%Y-%m-%d"),
            "time": "08:00", "status": "taken", "logged_at": iso(),
        })
    print(f"medication {long_med['name']} -> 30 days remaining (not due)")
    print("done")


if __name__ == "__main__":
    asyncio.run(main())
