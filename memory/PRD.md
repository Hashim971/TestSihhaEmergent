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
- Phase 3 — Clinical Scribe, Arabic-first (Transcriber protocol + stub provider, SOAP notes, consent gate): PENDING
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

## Backlog- P1: Appointment booking flow (patent workflow 4), calorie tracking alerts, predictive analytics trends endpoint
- P1: Doctor-patient explicit assignment (currently: all sharing patients visible to any doctor)
- P2: Voice input, body-map symptom input, notification email/SMS, counterfeit pill detection, real wearable integrations
- P2: Report list page for patients (reports currently downloadable from chat; API /api/reports exists)
