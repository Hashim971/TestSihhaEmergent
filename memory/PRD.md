# Sihha AI — PRD

## Original Problem Statement
"Connect to My TestSihha Repo and rebuild the whole thing use my patent document as a supporting document"
Patent: System and Method for Real-Time Healthcare Management Using Multimodal Data Integration (Sihha AI, July 2024).

## User Choices
- Fresh full-stack rebuild: React + FastAPI + MongoDB (old Vite/Supabase/Firebase code preserved in /app/legacy)
- Everything: core + dependents + doctor portal
- AI: Emergent Universal LLM Key, GPT-5.5 text + vision; original system prompt from legacy healthAI.ts reused for screening chat
- Auth: Emergent-managed Google social login
- Vitals: manual entry + simulated wearable data

## Architecture
- Backend: FastAPI (/app/backend/server.py), MongoDB (db: sihha_ai), emergentintegrations LlmChat (openai gpt-5.5)
- Frontend: CRA + craco + Tailwind (Organic & Earthy design: sand/forest green/terracotta, Outfit + IBM Plex Sans)
- Auth: Emergent Google OAuth, session_token httpOnly cookie (7d), Bearer fallback
- Collections: users, user_sessions, dependents, vitals, alerts, chat_sessions, chat_messages, health_reports, pill_history, medications, dose_logs

## Implemented (June 2026 — MVP, tested 100% backend + frontend)
- Google login, landing page, protected routes
- Patient dashboard: vital cards (HR, BP, glucose, SpO2, temp), recharts trends, manual vitals entry, wearable simulation (7 days), out-of-range alert generation
- AI Health Chat/Screening: SSE streaming GPT-5.5, one-question-at-a-time clinician prompt (from original repo), session history, PDF report download (jsPDF), reports stored
- Pill Identification: photo upload → GPT-5.5 vision → structured result (name, uses, dosage, side effects, warnings, confidence), history
- Medications: CRUD, daily schedule, dose taken/missed logging, missed-dose alerts, adherence stats
- Dependents: family profiles CRUD, profile switcher scoping vitals/meds/chat
- Doctor portal: role toggle, patient sharing opt-in, shared patient list with unread alerts, patient summary (vitals chart, alerts, meds, adherence, screening reports)
- Alerts bell with unread count + mark-read

## Backlog
- P1: Appointment booking flow (patent workflow 4), calorie tracking alerts, predictive analytics trends endpoint
- P1: Doctor-patient explicit assignment (currently: all sharing patients visible to any doctor)
- P2: Voice input, body-map symptom input, notification email/SMS, counterfeit pill detection, real wearable integrations
- P2: Report list page for patients (reports currently downloadable from chat; API /api/reports exists)
