# Sihha AI

Real-time healthcare management platform powered by multimodal AI. Sihha AI combines conversational health screening, computer-vision pill identification, vitals tracking, medication adherence, family/dependent management, and a doctor portal into a single React + FastAPI + MongoDB application.

Based on the patent: *System and Method for Real-Time Healthcare Management Using Multimodal Data Integration* (Sihha AI, July 2024).

---

## Table of Contents
1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Tech Stack](#tech-stack)
4. [Architecture](#architecture)
5. [Project Structure](#project-structure)
6. [Environment Variables](#environment-variables)
7. [Getting Started](#getting-started)
8. [API Reference](#api-reference)
9. [Data Model](#data-model)
10. [Third-Party Integrations](#third-party-integrations)
11. [Design System](#design-system)
12. [Test Credentials](#test-credentials)
13. [Testing](#testing)
14. [Roadmap](#roadmap)

---

## Overview

Sihha AI is a full-stack SaaS designed to be a patient's day-to-day health companion and a clinician's monitoring dashboard. Patients onboard with a short health profile, chat with an AI clinician that remembers their history, identify unknown pills from a photo, track vitals and medication adherence, and manage dependents (children, parents). Doctors can opt-in patients, review vitals trends, unread alerts, medication adherence, and downloadable screening reports.

Everything is built on a single FastAPI backend and a single-page React frontend, backed by MongoDB Atlas.

---

## Key Features

### Patient
- **Email/Password auth** with JWT access + refresh tokens (httpOnly cookies), bcrypt hashing, brute-force lockout.
- **5-step onboarding wizard**: general info (height, weight, DOB with Gregorian/Hijri), health history, medications, lifestyle. Data injected into every AI interaction.
- **Settings page** to edit the health profile at any time; AI picks up changes on the next message.
- **AI Health Chat & Screening** — GPT-5.5 with SSE streaming, one-question-at-a-time clinician prompt, session history, PDF report download (jsPDF).
- **Pill Identification** — upload a photo → user's HuggingFace CNN Space (`Hashim971/Tessihha`) predicts the class and returns a Grad-CAM attention map → GPT-5.5 fills in uses, dosage, side effects and warnings. GPT-5.5 Vision fallback if the Space is down. Expandable identification history so users can re-read past results.
- **Vitals tracking** — manual entry + simulated wearable stream (HR, BP, glucose, SpO₂, temperature), recharts trends, automatic out-of-range alert generation.
- **Medications** — CRUD, daily schedule, dose taken/missed logging, adherence stats, missed-dose alerts.
- **Dependents** — full CRUD for family members with a profile switcher that scopes vitals, meds and chat.
- **Alerts bell** with unread count and mark-as-read.

### Doctor
- **Role toggle**, patient sharing opt-in, shared patient list with unread alerts.
- **Patient summary**: vitals chart, alerts, medications, adherence percentage, screening reports.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | React (CRA + craco), React Router, Tailwind CSS, shadcn/ui, lucide-react, recharts, jsPDF, sonner |
| Backend | FastAPI, Motor (async MongoDB), Pydantic, PyJWT, bcrypt, emergentintegrations (`LlmChat`), gradio_client |
| Database | MongoDB Atlas (`cluster0.ntwaj1g.mongodb.net`, db: `sihha_ai`) |
| AI — Text/Vision | Emergent Universal LLM Key → GPT-5.5 (text + vision) |
| AI — CNN | HuggingFace Space `Hashim971/Pills-Classifier` via `gradio_client` |
| Auth | JWT (15 min access + 7 d refresh) in httpOnly cookies, Bearer fallback |
| Process manager | supervisor (`frontend`, `backend`) |

---

## Architecture

```
┌────────────┐   HTTPS   ┌──────────────────────┐   Motor    ┌──────────────────┐
│  React SPA │──────────▶│  FastAPI (/api/*)    │───────────▶│ MongoDB Atlas    │
│  (port 3000)│◀──────────│  (port 8001)         │            │  sihha_ai        │
└────────────┘  cookies  └──────────────────────┘            └──────────────────┘
                              │        │
                              │        ├── gradio_client ──▶ HF Space (Pills-Classifier)
                              │        └── emergentintegrations ──▶ GPT-5.5 (text + vision)
```

- All backend routes are prefixed with `/api` (Kubernetes ingress rule).
- Frontend calls the backend exclusively through `process.env.REACT_APP_BACKEND_URL`.
- Auth tokens live in httpOnly cookies; axios is configured with `withCredentials: true`.

---

## Project Structure

```
/app
├── backend/
│   ├── server.py            FastAPI app: auth, chat, pill, vitals, meds, dependents, doctor
│   ├── requirements.txt
│   └── .env                 MONGO_URL, DB_NAME, EMERGENT_LLM_KEY, HF_TOKEN, JWT_SECRET
├── frontend/
│   ├── package.json
│   ├── craco.config.js
│   ├── tailwind.config.js
│   ├── .env                 REACT_APP_BACKEND_URL
│   ├── public/
│   └── src/
│       ├── App.js           Routes
│       ├── index.js / index.css
│       ├── lib/api.js       Axios instance (withCredentials)
│       ├── context/AuthContext.js
│       ├── components/
│       │   ├── Layout.jsx
│       │   ├── ProtectedRoute.jsx
│       │   ├── YesNo.jsx
│       │   └── ui/          shadcn primitives
│       └── pages/
│           ├── Landing.jsx
│           ├── Auth.jsx
│           ├── Onboarding.jsx
│           ├── Settings.jsx
│           ├── Dashboard.jsx
│           ├── HealthChat.jsx
│           ├── PillIdentify.jsx
│           ├── Medications.jsx
│           ├── Dependents.jsx
│           └── DoctorPortal.jsx
├── memory/
│   ├── PRD.md
│   └── test_credentials.md
├── test_reports/
│   └── iteration_1.json
├── design_guidelines.json
├── auth_testing.md
└── image_testing.md
```

---

## Environment Variables

### `backend/.env`
| Key | Purpose |
|---|---|
| `MONGO_URL` | MongoDB Atlas connection string |
| `DB_NAME` | `sihha_ai` |
| `EMERGENT_LLM_KEY` | Emergent Universal LLM Key (GPT-5.5) |
| `HF_TOKEN` | HuggingFace token for the Pills-Classifier Space |
| `JWT_SECRET` | Signing key for access + refresh tokens |

### `frontend/.env`
| Key | Purpose |
|---|---|
| `REACT_APP_BACKEND_URL` | Public backend URL used by the SPA |

> Do **not** hardcode any of these — the app reads them from `.env` at startup. Missing values fail fast on purpose.

---

## Getting Started

The app runs under supervisor in this environment.

```bash
# View services
sudo supervisorctl status

# Restart after .env or dependency changes
sudo supervisorctl restart backend
sudo supervisorctl restart frontend

# Tail logs
tail -n 100 /var/log/supervisor/backend.*.log
tail -n 100 /var/log/supervisor/frontend.*.log
```

Backend runs on `0.0.0.0:8001`, frontend on `3000`. Public URL is read from `frontend/.env`.

Install deps if needed:
```bash
# Backend
cd /app/backend && pip install -r requirements.txt
# Frontend
cd /app/frontend && yarn install
```

---

## API Reference

All routes are prefixed with `/api`.

### Auth
| Method | Route | Purpose |
|---|---|---|
| POST | `/auth/register` | Create account, returns cookies |
| POST | `/auth/login` | Login, sets access + refresh cookies |
| POST | `/auth/logout` | Clear cookies |
| POST | `/auth/refresh` | Rotate access token |
| GET  | `/auth/me` | Current user + health profile |

### Health Profile
| Method | Route | Purpose |
|---|---|---|
| PUT | `/user/profile` (a.k.a. `/profile/health`) | Update onboarding/settings health data |

### AI
| Method | Route | Purpose |
|---|---|---|
| POST | `/chat` | AI chat (SSE stream) using health profile in system prompt |
| POST | `/identify-pill` | HF CNN + GPT-5.5 pill identification |
| GET  | `/pill-history` | Past identifications for the current user |
| GET  | `/reports` | Screening reports list |

### Vitals / Meds / Dependents / Doctor
| Method | Route | Purpose |
|---|---|---|
| GET/POST | `/vitals` | Manual + simulated wearable vitals |
| GET/POST/PUT/DELETE | `/medications` | Medication CRUD |
| POST | `/medications/{id}/dose` | Log dose taken / missed |
| GET/POST/PUT/DELETE | `/dependents` | Dependent CRUD |
| GET | `/doctor/patients` | Patients who opted-in to sharing |
| GET | `/doctor/patients/{id}` | Full patient summary |
| GET/POST | `/alerts` | Alerts list + mark-read |

---

## Data Model

MongoDB collections (all `_id` serialized via `PyObjectId`):

| Collection | Shape |
|---|---|
| `users` | `{_id, email, password_hash, name, role, health_profile, share_with_doctors, ...}` |
| `user_sessions` | `{_id, user_id, refresh_token_hash, expires_at}` |
| `dependents` | `{_id, user_id, name, dob, ...}` |
| `vitals` | `{_id, user_id|dependent_id, type, value, source: manual|wearable, taken_at}` |
| `alerts` | `{_id, user_id, kind, message, read, created_at}` |
| `chat_sessions` | `{_id, user_id, started_at, kind: chat|screening}` |
| `chat_messages` | `{_id, session_id, role, content, created_at}` |
| `health_reports` | `{_id, user_id, session_id, pdf_meta, created_at}` |
| `pill_history` | `{_id, user_id, image_url, pill_name, cnn_label, gradcam_url, details, created_at}` |
| `medications` | `{_id, user_id|dependent_id, name, dose, schedule, ...}` |
| `dose_logs` | `{_id, medication_id, status: taken|missed, at}` |

All timestamps are `datetime.now(timezone.utc)`.

---

## Third-Party Integrations

| Service | Purpose | Notes |
|---|---|---|
| **Emergent Universal LLM Key** | GPT-5.5 text + vision via `emergentintegrations.LlmChat` | Used for chat, screening reports, pill detail generation and vision fallback. |
| **HuggingFace Gradio Space** | `Hashim971/Tessihha` CNN + Grad-CAM | Called via `gradio_client` with `HF_TOKEN`. API: `/classify_pill`. |
| **MongoDB Atlas** | Managed database | Cluster `cluster0.ntwaj1g.mongodb.net`, db `sihha_ai`. |

---

## Design System

Organic & Earthy palette — sand, forest green, terracotta accents. Typography: **Outfit** (display) + **IBM Plex Sans** (body). See `/app/design_guidelines.json` for the full spec (color tokens, spacing scale, motion, component conventions).

All interactive elements use `data-testid` for QA automation.

---

## Test Credentials

Kept in `/app/memory/test_credentials.md`. Examples:

| Role | Email | Password |
|---|---|---|
| Doctor (seeded admin) | `admin@sihha.ai` | `Admin@123` |
| Patient | `patient1@test.com` | `password123` |

---

## Testing

- Backend + frontend covered by the testing agent — latest report: `/app/test_reports/iteration_1.json` (all passing).
- Auth-focused notes: `/app/auth_testing.md`.
- Pill / image flow notes: `/app/image_testing.md`.

Quick manual smoke test:
```bash
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
curl -s -X POST "$API/api/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"email":"admin@sihha.ai","password":"Admin@123"}'
```

---

## Roadmap

### P0
- **Forgot password flow** — backend pattern ready; frontend UI + email delivery pending.

### P1
- **Appointment booking** (patent workflow 4).
- **Predictive analytics** — trend analysis over vitals that warns before thresholds are crossed.
- **Doctor–patient explicit assignment** (currently: any doctor sees any opted-in patient).
- Calorie tracking alerts.

### P2
- **Doctor portal enhancements** — patient health-profile summary at a glance.
- **"Add to My Medications"** button on identified pills → push into adherence schedule.
- **Email verification on signup** (Resend / SendGrid).
- Voice input, body-map symptom input, notification email/SMS, counterfeit pill detection, real wearable integrations.
- Report list page for patients.

---

## License

Proprietary — Sihha AI. Patent pending: *System and Method for Real-Time Healthcare Management Using Multimodal Data Integration* (July 2024).
