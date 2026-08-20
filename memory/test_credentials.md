# Sihha AI — Test Credentials

All accounts use standard email/password JWT auth (httpOnly cookies).

## Admin / seeded doctor
- `admin@sihha.ai` / `Admin@123` — role: doctor (seeded by `seed_and_index()` from backend/.env)

## Phase 1 seeded accounts (`cd /app/backend && python seed_phase1.py`)
- `dr.layla@sihha.ai` / `Doctor@123` — doctor, owns the 5 seeded encounters
- `omar.patient@sihha.ai` / `Patient@123` — patient, hypertensive, 90 days vitals + 2 meds, sharing ON
- `noura.patient@sihha.ai` / `Patient@123` — patient, diabetic, low adherence (~62%), sharing ON
- `sami.patient@sihha.ai` / `Patient@123` — patient, stable, sharing ON

## Sign-in pages
- Patients: `/auth` · Clinicians: `/auth/clinician` (separate pages; using the wrong one is refused).
- Clinician self-signup only creates a pending request (`clinician_requested`); the admin approves it from
  `/admin/assignments`, which calls `PUT /api/admin/users/{user_id}/role`.

## Notes
- Pharmacy marketplace (Phase 6): seed with `cd /app/backend && set -a && . ./.env && set +a && python seed_pharmacy.py`.
  omar.patient then has Concor 4 days from runout. Partners: Nahdi (handoff + sponsored) and Al Dawaa (in_app).
  Prescription images go to Emergent Object Storage; there is no delivery and no payment anywhere.
- Scribe transcription is LIVE (`TRANSCRIPTION_PROVIDER=hosted` in backend/.env) — recording a consultation
  transcribes the real audio. Automated test suites pin it to the free fixture transcriber by calling
  `PUT /api/admin/transcription {"provider":"stub"}` as the admin and restoring it afterwards
  (a runtime override stored in the `app_settings` collection; delete that row to fall back to the env value).
- Note to the patient: after a doctor signs a SOAP note they draft a bilingual (Arabic + English) plain-language
  summary, edit it, then `POST /api/artifacts/{id}/publish` sends it to the patient, who reads it at `/visits`.
- `ALLOW_SELF_ROLE_CHANGE=false` in backend/.env — self role switching returns 403 and the sidebar toggle is
  only rendered for the admin account. Change roles directly in Mongo or via the admin if a doctor is needed.
- Any account created via `POST /api/auth/register` starts as `patient` with `sharing_enabled: true`
  (consent on by default) and **no assigned doctor** — it is invisible to doctors until the patient picks one
  in Settings or the admin assigns one at `/admin/assignments`.
- `admin@sihha.ai` is the only `is_admin` account (matched on `ADMIN_EMAIL` in backend/.env) and sees every
  patient regardless of assignment. All 11 existing patients are currently assigned to `dr.layla@sihha.ai`.
