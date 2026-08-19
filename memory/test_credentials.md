# Sihha AI — Test Credentials

All accounts use standard email/password JWT auth (httpOnly cookies).

## Admin / seeded doctor
- `admin@sihha.ai` / `Admin@123` — role: doctor (seeded by `seed_and_index()` from backend/.env)

## Phase 1 seeded accounts (`cd /app/backend && python seed_phase1.py`)
- `dr.layla@sihha.ai` / `Doctor@123` — doctor, owns the 5 seeded encounters
- `omar.patient@sihha.ai` / `Patient@123` — patient, hypertensive, 90 days vitals + 2 meds, sharing ON
- `noura.patient@sihha.ai` / `Patient@123` — patient, diabetic, low adherence (~62%), sharing ON
- `sami.patient@sihha.ai` / `Patient@123` — patient, stable, sharing ON

## Notes
- `ALLOW_SELF_ROLE_CHANGE=false` in backend/.env — self role switching returns 403 and the sidebar toggle is
  only rendered for the admin account. Change roles directly in Mongo or via the admin if a doctor is needed.
- Any account created via `POST /api/auth/register` starts as `patient` with `sharing_enabled: true`
  (consent on by default) and **no assigned doctor** — it is invisible to doctors until the patient picks one
  in Settings or the admin assigns one at `/admin/assignments`.
- `admin@sihha.ai` is the only `is_admin` account (matched on `ADMIN_EMAIL` in backend/.env) and sees every
  patient regardless of assignment. All 11 existing patients are currently assigned to `dr.layla@sihha.ai`.
