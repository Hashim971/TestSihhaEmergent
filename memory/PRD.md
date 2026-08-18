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
- Phase 2 — Intake Agent (intake_forms, Intake.jsx wizard): PENDING
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

## Backlog- P1: Appointment booking flow (patent workflow 4), calorie tracking alerts, predictive analytics trends endpoint
- P1: Doctor-patient explicit assignment (currently: all sharing patients visible to any doctor)
- P2: Voice input, body-map symptom input, notification email/SMS, counterfeit pill detection, real wearable integrations
- P2: Report list page for patients (reports currently downloadable from chat; API /api/reports exists)
