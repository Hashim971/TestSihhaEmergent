# Sihha AI — PRD

## Original Problem Statement
"Connect to My TestSihha Repo and rebuild the whole thing use my patent document as a supporting document"
Patent: System and Method for Real-Time Healthcare Management Using Multimodal Data Integration (Sihha AI, July 2024).

## User Choices
- Fresh full-stack rebuild: React + FastAPI + MongoDB (old Vite/Supabase/Firebase code preserved in /app/legacy)
- Everything: core + dependents + doctor portal
- AI: Emergent Universal LLM Key, GPT-5.5 text + vision; original system prompt from legacy healthAI.ts reused for screening chat
- Auth: standard email/password JWT (replaced Google OAuth per user request, June 2026). Access token 15min + refresh 7d in httpOnly cookies, bcrypt hashing, brute-force lockout (5 fails/15min), seeded admin (admin@sihha.ai / Admin@123, role doctor). /auth page with login/signup tabs.
- Vitals: manual entry + simulated wearable data

## Architecture
- Backend: FastAPI (/app/backend/server.py), MongoDB Atlas (cluster0.ntwaj1g.mongodb.net, db: sihha_ai — migrated from local MongoDB June 2026; connection in backend/.env MONGO_URL), emergentintegrations LlmChat (openai gpt-5.5)
- Frontend: CRA + craco + Tailwind (Organic & Earthy design: sand/forest green/terracotta, Outfit + IBM Plex Sans)
- Auth: Emergent Google OAuth, session_token httpOnly cookie (7d), Bearer fallback
- Collections: users, user_sessions, dependents, vitals, alerts, chat_sessions, chat_messages, health_reports, pill_history, medications, dose_logs

## Implemented (June 2026 — MVP, tested 100% backend + frontend)
- Settings page (/settings, sidebar nav): edit health profile anytime — pre-filled from saved data, same sections as onboarding, saves via PUT /api/profile/health (AI picks up changes immediately).
- Post-signup onboarding wizard (5 steps: Account ✓ → General Info with height/weight/DOB + Gregorian/Hijri → Health History → Medications → Lifestyle, yes/no toggles with conditional detail fields, skip option). Stored as users.health_profile; AI chat + screening reports inject this profile into the system prompt (verified: chatbot recalls allergies/medications).
- Google login, landing page, protected routes
- Patient dashboard: vital cards (HR, BP, glucose, SpO2, temp), recharts trends, manual vitals entry, wearable simulation (7 days), out-of-range alert generation
- AI Health Chat/Screening: SSE streaming GPT-5.5, one-question-at-a-time clinician prompt (from original repo), session history, PDF report download (jsPDF), reports stored
- Pill Identification: photo upload → user's own HuggingFace Space CNN (Hashim971/Pills-Classifier via gradio_client, HF_TOKEN in backend/.env) predicts class + Grad-CAM attention map → GPT-5.5 generates details (uses, dosage, side effects, warnings); GPT-5.5 vision as fallback if Space is down. Frontend shows CNN Model badge + Grad-CAM image. (Updated June 2026)
- Medications: CRUD, daily schedule, dose taken/missed logging, missed-dose alerts, adherence stats
- Dependents: family profiles CRUD, profile switcher scoping vitals/meds/chat
- Doctor portal: role toggle, patient sharing opt-in, shared patient list with unread alerts, patient summary (vitals chart, alerts, meds, adherence, screening reports)
- Alerts bell with unread count + mark-read

## Phase Plan (from user artifact `Emergent_Prompts_v2_Code_Grounded.md`, June 2026)
Strict ADDITIVE-ONLY contract: no refactors, no renames, no new npm/pip packages, no touching /app/legacy.
- Phase 0 — Security fixes: DONE (June 2026)
- Phase 1 — Agent runtime + Pre-Visit Briefing Agent + interactive follow-up: DONE (June 2026)
- Phase 2 — Intake Agent (intake_forms, Intake.jsx wizard): DONE (June 2026)
- Phase 3 — Clinical Scribe, Arabic-first: DONE (June 2026)
- Phase 4 — Coding Agent, NPHIES/ICD-10-AM FHIR R4 (signed notes only): PENDING
- Phase 5 — Triage Agent (deterministic red-flag rules before LLM, feature-flagged off): PENDING
- Phase 6 — Pharmacy Marketplace (independent track; compliance.py, refill.py, handoff + in_app fulfilment): PENDING

## Phase 0 — Security fixes (completed June 2026, 7/7 tests pass)
- `password_hash` no longer leaks: `POST /api/auth/role`, `GET /api/doctor/patients`, `GET /api/doctor/patients/{id}/summary` now use `USER_PROJECTION`. Audited all other `db.users` queries (login line 199 intentionally keeps the hash internally).
- Self-promotion to doctor gated behind `ALLOW_SELF_ROLE_CHANGE` (default `false` → 403 "Role changes are administered, not self-service."). Set to `true` in backend/.env for dev so the Layout role toggle still works; frontend now catches 403 and shows a sonner error.
- CORS default changed from `*` to `http://localhost:3000`; app raises a startup RuntimeError if `CORS_ORIGINS` contains `*` while credentials are enabled. (Note: the k8s ingress adds its own `access-control-allow-origin: *` header on the public URL — app-level behaviour verified against localhost:8001.)
- Regression tests appended to `/app/backend/tests/backend_test.py`: `TestNoPasswordHashLeak`, `TestSelfRoleChangeGate`, `TestCorsNotWildcard`.

## Phase 1 — Agent runtime + Pre-Visit Briefing (completed June 2026)
Backend: `/app/backend/agents/` package — `tools.py` (only data path to patient records; returns data + document ids
for `input_refs`, includes citable `recent_readings`/`out_of_range_readings` per vital metric and
`get_interaction_flags` against the static `reference/interactions.json`), `runner.py` (60s timeout, one retry,
exactly one append-only `agent_runs` doc per attempt, ids only — never patient text), `previsit.py`
(PreVisitBriefingAgent, gpt-5.5, strict JSON validated by Pydantic with one repair retry),
`briefing_qa.py` (record-only follow-up agent; refuses diagnosis/treatment/referral; every factual answer must cite).
Prompts live in `agents/prompts/previsit_v1.md` and `briefing_qa_v1.md` (first line sets `prompt_version`).
Collections: `encounters`, `agent_runs`, `clinical_artifacts` (draft → reviewed → signed, 409 once signed),
`briefing_threads` (one per artifact, usable after signing). Indexes added in `seed_and_index()`.
Routes (all doctor routes go through `assert_doctor_can_access_patient`, the single place doctor–patient
assignment will land): POST/GET `/api/encounters`, GET/PATCH `/api/encounters/{id}`,
POST `/api/agents/previsit/{encounter_id}`, GET/PATCH `/api/artifacts/{id}`, POST `/api/artifacts/{id}/sign`,
GET/POST `/api/artifacts/{id}/thread`, GET `/api/agents/runs`.
Frontend: `DoctorSchedule.jsx` (/doctor/schedule, list + create form + briefing badge),
`EncounterDetail.jsx` (/doctor/encounters/:id — generate, inline edit with 800ms debounced PATCH, sign,
low-confidence callout, non-dismissible AI-draft banner), `components/BriefingSections.jsx`,
`components/FollowUpPanel.jsx` (citation chips scroll+highlight the cited section, refusals render muted,
uncited answers are marked "No citations — unverified" on purpose). Schedule nav added to the doctor block.
Seed: `python /app/backend/seed_phase1.py` — 1 doctor, 3 sharing patients (90 days vitals + dose logs,
adherence 92/62/97%), 5 encounters. Credentials in `/app/memory/test_credentials.md`.
Tests: `/app/backend/tests/test_phase1_agents.py` — 16 pass (incl. 403 cases, low-confidence empty record,
edit persistence, sign→409, audit integrity, vitals-id citations, three refusal cases).
Frontend testing agent: 12/12 flows pass (`/app/test_reports/iteration_2.json`).
## Bug fix — doctor portal showed only seeded patients (June 2026)
Reported: "the doctor profile is not fetching real patient data — 2 users with screening reports did not show up."
Root cause: `/api/doctor/patients` filters on `sharing_enabled: True` and registration created users with
`sharing_enabled: False`, so real users (hashim@gmail.com, hhisham@gmail.com) were invisible. Data access was fine.
Fix (user chose consent-on-by-default): registration now sets `sharing_enabled: True`; existing patients
backfilled by the one-off `backend/migrations/enable_sharing_default.py` (9 switched on); patients can still opt out
from the sidebar toggle and disappear from the portal when they do. Screening reports stay visible to doctors.
Also fixed as follow-up: `_decorate_encounters` N+1 lookups (GET /api/encounters 15-18s → ~1s) and a loading
skeleton on /doctor/schedule so the empty state no longer flashes. Verified by the testing agent —
`/app/test_reports/iteration_3.json`, 100% backend and frontend.

## Doctor assignment — one doctor per patient (June 2026)
Consent (`sharing_enabled`) now pairs with assignment (`users.assigned_doctor_user_id`, plus `assigned_by`
= patient | admin | migration and `assigned_at`). One doctor at a time: choosing a new doctor transfers care and
revokes the previous doctor immediately.
- `with_capabilities()` marks the account whose email matches `ADMIN_EMAIL` as `is_admin` (returned from
  register / login / `/auth/me`); `require_admin` guards the admin routes. The admin keeps full clinical
  visibility so it can manage assignments.
- New routes: `GET /api/doctors` (directory: user_id, name, email only), `PUT /api/profile/doctor`
  (patient picks their doctor), `GET /api/admin/patients`, `PUT /api/admin/patients/{id}/doctor`.
- `GET /api/doctor/patients` filters on `assigned_doctor_user_id` (admin bypasses) and
  `assert_doctor_can_access_patient` — the single gate used by the summary route and every Phase 1 agent
  route — now requires consent AND assignment, returning 403 otherwise.
- Frontend: `components/MyDoctorCard.jsx` in Settings (patients only, warns if sharing is off),
  `pages/AdminAssignments.jsx` at `/admin/assignments` with an unassigned-count banner and per-patient
  doctor dropdown, nav item gated on `user.is_admin`. Doctor Portal now has an explicit load-error retry
  instead of silently swallowing a failed fetch.
- Migration `backend/migrations/assign_existing_patients.py` assigned the 12 existing patients to
  dr.layla@sihha.ai (the admin sees everyone regardless).
- Tests: `/app/backend/tests/test_assignments.py` — 13 pass; Phase 0 (7) and Phase 1 (16) still pass.
  Frontend testing agent 8/8 (`/app/test_reports/iteration_4.json`).

## Phase 2 — Intake Agent (completed June 2026)
`agents/intake.py` + `agents/prompts/intake_v1.md`: generates 5-8 plain-language, non-leading questions
(≤2 free text, ≤4 required, single_choice/scale preferred, escape options, no diagnostic language) from the
health profile, active medications, 30-day alerts and the encounter's reason for visit. Validated with Pydantic
(`IntakeForm` enforces the 5-8 and ≤2-text bounds) with one repair retry, and it runs through the Phase 1
`runner.py`, so every generation lands in `agent_runs` with `output_ref` → `intake_forms`.
Collection `intake_forms` (unique on `encounter_id`, plus patient+status index): questions, upserted
`responses`, `status` pending → partial → complete, `expires_at` (encounter time, floored at now+24h so a form
is never born expired). Regeneration is blocked with 409 once the patient has started answering.
Routes: `POST /api/agents/intake/{encounter_id}` (doctor), `GET /api/intake/{encounter_id}` and
`POST /api/intake/{encounter_id}/responses` (patient-owner only, partial upsert by question_id, 409 after
expiry, 400 on unknown question), `GET /api/doctor/intake/{encounter_id}`. Completion inserts an `info`
severity alert for the doctor — `info` is styled sage/green in `Layout.jsx` and `DoctorPortal.jsx`, never terracotta.
Briefing wiring: `tools.get_intake_responses()` feeds `gather_context`, the Pre-Visit Briefing Agent moved to
`previsit_v2.md` (prompt_version v2, treats intake answers as first-class evidence and names disagreements
with measured data); `previsit_v1.md` stays on disk so older `agent_runs` remain resolvable.
Frontend: `pages/Intake.jsx` at `/intake/:encounterId` (one question per screen, progress bar, Back/Next,
autosave on advance, resumes at the first unanswered question, reuses `YesNo.jsx` for Yes/No options,
completion screen), `components/IntakeCard.jsx` on the encounter page above the briefing, and an intake
prompt card on the patient dashboard driven by the `intake` field now returned by `GET /api/encounters`.
A hint next to Regenerate appears when intake was completed after the current briefing was written.
Tests: `/app/backend/tests/test_phase2_intake.py` — 13 pass; frontend testing agent 10/10
(`/app/test_reports/iteration_5.json`). Three generated forms manually reviewed for diagnostic language.
Note: the legacy `user_sessions` tests in `backend_test.py` are now explicitly skipped (pre-JWT era).

## Intake answers inline in the briefing (June 2026)
`chief_concerns[].intake_refs` (list of intake `question_id`s) added to the briefing schema; prompt bumped to
`previsit_v3.md` (v1 and v2 stay on disk for audit). `tools.get_intake_responses` now returns `question_id` per
answer so the agent can only reference real ids. `ConcernsCard` renders each referenced answer inline under the
concern — question plus the patient's quoted answer, capped at 3 with a "+N more" note. Verified by
`test_phase2_intake.py` (asserts v3 and that every `intake_refs` id exists in the form) and by screenshot.
Two fixes found while doing this: regenerating a briefing now returns the newest artifact (the encounter and
schedule lookups were taking whichever came first, so a regenerated briefing could stay hidden), and a doctor
can no longer self-switch to the patient role while patients are assigned to them (409) — that had silently
orphaned Dr. Layla's panel during a test run.

## Screening findings — screening as citable briefing evidence (June 2026)
The AI screening now feeds the briefing the way intake does, in six parts:
1. `agents/screening.py` + `prompts/screening_extract_v1.md` — a `ScreeningExtractionAgent` turns each report into
   `findings: [{finding_id, symptom, onset, duration, severity, patient_words, source_message_ids, report_id}]`,
   verbatim patient quotes only, transcript message ids validated against the DB, no diagnostic labels. Runs
   automatically inside `POST /api/chat/sessions/{sid}/report` (never fails the report) and on demand via
   `POST /api/doctor/reports/{report_id}/findings`. Re-extraction reuses the previous `finding_id` for a matching
   symptom so citations in existing briefings never dangle.
2. `PUT /api/reports/{report_id}/share` — the patient links a screening to a specific upcoming visit
   (`shared_encounter_id`, `shared_at`); the briefing gives that report precedence.
3. `tools.get_symptom_timeline()` groups findings by symptom across 180 days → "reported 3 times since 12 May".
4. Staleness: reports older than 90 days are flagged `stale` and the prompt must not present them as current.
5. Intake prompt bumped to `intake_v2.md` — it receives the findings and asks follow-ups instead of re-asking.
6. `GET /api/doctor/screening/{encounter_id}` — reports with findings, transcript excerpts, timeline; rendered by
   `components/ScreeningCard.jsx` (expandable findings, transcript excerpts, "Ask about this" into the follow-up
   thread, shared/stale badges) and inline under each concern via `screening_refs` in `ConcernsCard`.
Briefing prompt is now `previsit_v4.md` (v1-v3 retained for audit); `ChiefConcern` gained `screening_refs`.
Patient side: `components/ShareScreeningCard.jsx` in Health Chat, hydrated from `GET /api/reports` so a report
stays shareable after a reload. A hint appears next to Regenerate when a screening is shared after the briefing
was written (same pattern as intake).
Migration `migrations/backfill_screening_findings.py` structured the pre-existing reports (idempotent).
Hardening: `ALLOW_SELF_ROLE_CHANGE=false` and the sidebar role toggle is admin-only — self-promotion had twice
flipped seeded patients into doctors and corrupted panel data during test runs.
Tests: `/app/backend/tests/test_screening_findings.py` — 12 pass; frontend testing agent 9/9
(`/app/test_reports/iteration_6.json`).

## Clinician workspace + split sign-in (June 2026)
Doctors no longer see patient tooling. `Layout.jsx` now picks between `patientNav` and `doctorNav`
(Dashboard, Patients, Schedule, Settings — plus Assignments for the admin); the sharing toggle and the
dependent profile switcher are patient-only, replaced by a "Clinician workspace" label.
New `pages/DoctorDashboard.jsx` at `/doctor` (the old portal moved to `/doctor/patients`, headed "My Patients"),
fed by `GET /api/doctor/dashboard`: panel size, visits today/this week, briefings to write, drafts awaiting
signature, intakes waiting on patients, unread alerts across the panel and recent agent runs with latency.
Split sign-in: `/auth` (patients) and `/auth/clinician` (`Auth.jsx` takes a `portal` prop), cross-linked, with
mismatched credentials refused on both sides ("use the patient/clinician sign-in") and immediately logged out.
The landing page has separate Patient and Clinician entry points in the header and hero.
Clinician signup exists but grants nothing: `POST /api/auth/register` with `requested_role: "doctor"` creates a
normal patient flagged `clinician_requested`, and only the admin can promote via `PUT /api/admin/users/{id}/role`
(demotion returns 409 while patients are still assigned). Approve button lives on `/admin/assignments`.
Tests: `/app/backend/tests/test_doctor_workspace.py` — 12 pass; frontend testing agent 8/8
(`/app/test_reports/iteration_7.json`).

## Dashboard polish: alert grouping, clinician profiles, day view (June 2026)
- **Alert grouping**: `GET /api/doctor/dashboard` now returns `alert_groups`, one per (type, severity), with a count,
  the patients involved (resolved via `profile_id` for alerts raised *for* the doctor, e.g. intake completions),
  the latest timestamp and up to 5 sample items. `components/AlertGroups.jsx` renders "189 medication alerts" /
  "10 pre-visit intakes completed" with expandable detail; critical is terracotta, warning lightly tinted, info sage.
- **Clinician profile**: `PUT /api/profile/clinician` (specialty, clinic, city, bio) and `GET /api/doctors` now
  returns those public fields, excluding the admin ops account. `components/ClinicianProfileCard.jsx` appears in
  Settings for doctors (patient health sections are hidden for them), and `MyDoctorCard` shows
  "Name — Specialty · Clinic, City" plus a details block with the bio for the chosen doctor.
- **Day view**: `components/DayView.jsx` replaces the flat "Today" list — hour rows from an hour before the first
  visit to an hour after the last, current hour highlighted, each visit showing time, patient, reason, intake hint
  and briefing badge ("Signed" / "Draft" / "No briefing"). The old flat list became "Later this week".
Tests: `test_doctor_workspace.py` grew to 18 passing (group integrity, patient naming, profile visibility,
directory field whitelist); frontend testing agent iteration_8 — all core criteria passed, and its three
follow-ups (intake group names, warning tint, admin in directory) are fixed and re-verified.

## Phase 3 — Clinical Scribe, Arabic-first (completed June 2026)
Transcription is abstracted behind `agents/transcription/base.py` (`Transcriber` protocol) with two
implementations — `stub.py` (reads `fixtures/consultation_ar_sa.json`, a Saudi-dialect consultation with
code-switched English drug names, a stated BP of 150/95 and two inaudible passages) and `hosted.py` (hosted
speech-to-text via the Emergent key, segment timestamps, confidence from avg_logprob). Selection is
`TRANSCRIPTION_PROVIDER` (default `stub`); no vendor name appears in `scribe.py` or any route, and a test
asserts that.
`consultation_audio` collection: multipart chunked upload (`POST /api/encounters/{id}/audio/init`,
`/api/audio/{id}/chunk`, `/api/audio/{id}/complete`), Fernet-encrypted at rest under `AUDIO_STORAGE_DIR` with
0600 perms, `retention_expires_at` from `AUDIO_RETENTION_DAYS` (30). `purge_expired_audio()` hard-deletes the
bytes and keeps the metadata row with `deleted_at` set; exposed as `POST /api/admin/audio/purge`, scheduled
daily in `.emergent/crons.yml`, and runnable via `backend/scripts/audio_retention.py`.
Consent: `POST /api/encounters/{id}/consent` writes `recording_consent` on the encounter; every audio route
goes through `_consented_encounter()` and returns 403 without it. The UI gate (`components/ScribePanel.jsx`)
keeps the record button disabled until the checkbox is ticked and consent is posted.
`agents/scribe.py` + `prompts/scribe_v1.md` produce a `soap_note` clinical_artifact through the Phase 1 runner
and draft → sign flow. Objective vitals come from `get_vitals_summary` (`source: "recorded"`); transcript-stated
vitals are added separately with `conflict` populated on both entries. Segments below
`TRANSCRIPTION_CONFIDENCE_THRESHOLD` land in `low_confidence_segments`, and signing is blocked with 409 until
each is acknowledged via `POST /api/artifacts/{id}/acknowledge` (the UI disables Sign until then).
`GET /api/encounters/{id}/soap` returns consent, audio state and the latest note.
Tests: `/app/backend/tests/test_phase3_scribe.py` — 16 pass, covering all seven acceptance criteria.
Verified in the browser: recorded-vs-stated BP conflict, Arabic low-confidence passages, Sign disabled until
acknowledged, drug name "Concor" preserved rather than corrected.

## Real audio switch + Note to the patient (June 2026)
- **Live transcription**: `TRANSCRIPTION_PROVIDER=hosted` is now the app default and verified end-to-end with real
  Saudi-dialect Arabic audio (transcript kept the drug name "كونكور", stated 150/95 flagged against the recorded
  120/92). Fix that unblocked it: the decrypted working file is now written with a real audio extension derived from
  the upload's mime type (`AUDIO_EXTENSIONS`) — the provider rejects unknown extensions. A runtime override lives in
  `app_settings.transcription_provider` with admin routes `GET/PUT /api/admin/transcription` (stub | hosted); the
  pytest suites flip it to `stub` and restore it, so automated runs cost nothing.
- **Scribe playback**: `components/ScribePanel.jsx` loads `/api/audio/{id}/stream` as a blob into an `<audio>`
  element beside the note, and each low-confidence passage has a Play button that seeks to its segment start.
- **Note to the patient** (doctor reviews and sends, never auto-published): `agents/patient_summary.py` +
  `prompts/patient_summary_v1.md` turn a *signed* SOAP note into `{ar, en}` × `{what_we_discussed, diagnosis_plain,
  medications[], next_steps[], red_flags[]}` — plain language, no jargon, drug names untouched, nothing invented.
  Routes: `POST /api/artifacts/{id}/patient-summary` (409 until the note is signed, 409 once a summary was sent),
  `PATCH /api/artifacts/{id}` for edits (now also 409 on `published`), `POST /api/artifacts/{id}/publish` (sets
  `published_at`, raises an `info` alert for the patient), `GET /api/patient/visit-summaries` (decorated with the
  doctor name and reason for visit). `GET /api/encounters/{id}/soap` returns the summary alongside the note.
  Frontend: `components/PatientSummaryPanel.jsx` (Arabic/English toggle, RTL, inline editing, Send to Patient) inside
  the scribe panel once signed, and `pages/VisitSummaries.jsx` at `/visits` with a patient nav item.
- Tests: `/app/backend/tests/test_patient_summary.py` — 13 pass (draft gate, bilingual content, Arabic script,
  audit refs, publish + patient visibility + alert, published lock, cross-patient isolation, admin-only switch);
  `test_phase3_scribe.py` still 16 pass. Frontend testing agent iteration_9 — 8/8 flows, no issues.

## Phase 6 — Pharmacy Marketplace (June 2026)
Discovery-first marketplace: the patient finds **which partner pharmacy has their medicine**, then buys on the
partner's own site (`handoff`) or gets directions to the branch. **There is no delivery and no payment.** The
business model is **sponsored placement** — `pharmacies.sponsorship = {tier, rank, active_until}` puts paying
partners at the top of the catalog and of every refill offer list, with a visible "Sponsored" badge.
- **Compliance, three independent layers, fail closed** (`backend/pharmacy/compliance.py`, pure functions, unit
  tested): controlled substances are rejected at ingestion, at add-to-cart and at checkout (shown as
  information-only with an in-store notice and no order control); prescription items need an attached,
  non-rejected, non-expired prescription — Sihha only transmits it, the partner's licensed pharmacist verifies
  (`require_verified` exists for the dispensing gate, never for Sihha); prescription quantities capped at a
  90-day supply counting what is already in the basket; SFDA + MOH + CR licences are mandatory and rendered on
  every listing, basket and order. Every failure returns a named rule (`CONTROLLED_NOT_ORDERABLE`,
  `MAX_SUPPLY_EXCEEDED`, `PRESCRIPTION_REQUIRED`, …) so the UI can say exactly what is wrong.
- **Refill engine** (`backend/pharmacy/refill.py`, deterministic, no LLM): `days_remaining` and
  `projected_runout_date` from pack size vs `dose_logs` marked taken, plus adherence. Due at ≤ 7 days, raised
  through the existing `alerts` collection (`type: "refill"`, deduped per medication). Matching is exact
  generic/trade-name only — a low-confidence medication surfaces a "Find this" search, **never** a substitute.
  Medications gained optional `quantity_dispensed`, `units_per_dose`, `dispensed_on` (also in the Medications form).
- **Routes**: `/api/pharmacy/pharmacies`, `/catalog`, `/catalog/{id}`, `GET/POST/DELETE /cart` (+ `/items`,
  `/items/{id}`, `/prescription`), `POST /prescriptions` (Emergent Object Storage) + `GET /prescriptions` +
  `/prescriptions/{id}/image`, `POST /checkout` (branches on `fulfilment_mode`), `GET /orders`, `/orders/{id}`,
  `POST /orders/{id}/cancel`, `GET /refills`. Baskets are single-pharmacy (`CART_SINGLE_PHARMACY`).
  `handoff` orders terminate at `handed_off` with a populated partner deep link; `in_app` orders land on
  `awaiting_pharmacist_verification` (prescription involved) or `confirmed`.
- **Frontend**: `/pharmacy` (Refills Due leads, search + categories, bilingual product cards, partner licences,
  cart slide-over with per-line compliance messages, branching checkout) and `/pharmacy/orders` with a status
  timeline. Components in `components/pharmacy/`.
- **Seed** (`seed_pharmacy.py`): Nahdi (handoff, sponsored) + Al Dawaa (in_app) with clearly fake licences,
  43 products / 67 listings across all categories including 3 controlled and 10 prescription-only, and
  omar.patient sitting 4 days from running out of Concor.
- Tests: `test_pharmacy_compliance.py` (23), `test_pharmacy_refill.py` (12), `test_pharmacy_routes.py`
  (integration, all nine acceptance criteria). Frontend testing agent iteration_10: 10/10 flows, no issues.
- Also fixed: README data-model/tech-stack corrections; the previsit agent now drops citations that do not
  match a real finding or intake answer; the doctor dashboard no longer lists encounters whose patient was
  deleted.

## Phase 7 — Screening triage, self-booking, and doctor prescriptions (June 2026)
Answers "does this screening need a visit, and how does it get booked?" plus e-prescribing after the visit.
- **Triage** (`backend/triage/rules.py` + `agents/triage.py`, prompt `triage_v1.md`): after every screening report, a
  deterministic red-flag scan of the patient's own words (English + Arabic) and their latest vitals sets a **floor**
  urgency; the LLM may raise it and can never lower it (`rule_floor`, `model_level`, `escalated_by_rules` are all
  stored). Levels: `emergency_now` / `urgent_24h` / `routine_2w` / `self_care`, each with a timeframe, reasons that
  may only cite real `finding_id`s, a recommended specialty, a ready-made reason-for-visit line, watch-for signs and
  (non-emergency only) self-care advice. Emergency and urgent dispositions alert the patient AND their assigned
  doctor through the existing alerts collection. Route: `POST /api/reports/{id}/triage`; runs automatically inside
  `POST /api/chat/sessions/{sid}/report`.
- **Booking** (instant confirmation, no approval step — user's choice): doctors publish weekly hours
  (`doctor_availability`, `GET/PUT /api/doctor/availability`, clinic-local times via `tz_offset_minutes`);
  `GET /api/booking/doctors` ranks the patient's own doctor first and filters by specialty/city;
  `GET /api/booking/slots` subtracts booked encounters, blocked dates and the past; `POST /api/booking` creates the
  encounter, auto-shares the screening to it and alerts the doctor (warning severity when urgent).
  **Booking is refused with 409 for an `emergency_now` screening** — that case shows call-997 guidance instead.
  Booking a clinician who is not the patient's assigned doctor creates a time-boxed `care_grants` record, and
  `assert_doctor_can_access_patient` now accepts assignment **or** an active grant. `POST /api/encounters/{id}/cancel`
  frees the slot and notifies the other side.
- **Doctor prescriptions**: `POST /api/encounters/{id}/prescription` (draft, upserts one draft per encounter),
  `PATCH /api/prescriptions/{id}`, `POST /api/prescriptions/{id}/sign` (locks it, alerts the patient),
  `POST /api/prescriptions/{id}/transmit` (partner pharmacy; creates an `awaiting_pharmacist_verification` order for
  `in_app` partners), `GET /api/prescriptions`, `GET /api/prescriptions/{id}/basket-options` (catalog matches per
  item, sponsored-first, patient confirms each — never auto-substituted). Controlled medicines are detected against
  the catalog and marked `dispense_in_clinic`: never transmitted, never orderable. Prescriptions live in the same
  `prescriptions` collection as uploaded images (`source: "encounter"`), so they attach to a pharmacy basket.
- **Frontend**: `components/TriageCard.jsx` (full width above /chat), `pages/BookVisit.jsx` at `/book`,
  `components/AvailabilityCard.jsx` (doctor Settings), `components/PrescriptionWriter.jsx` (encounter detail),
  `pages/Prescriptions.jsx` at `/prescriptions` with PDF download and the confirm-each-match ordering flow.
  New patient nav items: Book a Visit, Prescriptions.
- Tests: `test_triage_rules.py` (20 unit) and `test_visits_and_prescriptions.py` (23 integration) all pass;
  frontend testing agent iteration_11: 8/8 flows, no issues. Stale directory-field whitelists updated for
  the new `clinic_phone`.

## Backlog- P1: Appointment booking flow (patent workflow 4), calorie tracking alerts, predictive analytics trends endpoint
- P1: Doctor-patient explicit assignment (currently: all sharing patients visible to any doctor)
- P2: Voice input, body-map symptom input, notification email/SMS, counterfeit pill detection, real wearable integrations
- P2: Report list page for patients (reports currently downloadable from chat; API /api/reports exists)
