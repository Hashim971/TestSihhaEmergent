# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Sihha AI is a healthcare platform for Saudi patients, clinicians, hospitals and pharmacies (Arabic-first, English
second): AI screening chat, pill identification, vitals, medications, visit booking and triage, a live Arabic
clinical scribe, prescriptions, a pharmacy marketplace, and white-label hospital branding. The product spec and
history are in `memory/PRD.md`, and the seeded test accounts are in `memory/test_credentials.md`.

## Two environments

This project is built on Emergent and also runs locally. Most of its docs and test docstrings assume Emergent's
hosted environment, so translate them when working locally:

| | Emergent (hosted) | Local (this Mac) |
|---|---|---|
| Project root | `/app` | this folder |
| Start/stop | `sudo supervisorctl restart backend\|frontend\|all` | `python3 server.py` (Ctrl+C stops both) |
| Logs | `tail -n 100 /var/log/supervisor/backend.err.log` | prefixed `[backend]` / `[frontend]` lines in the launcher's terminal |
| `REACT_APP_BACKEND_URL` | the public preview/production URL | `http://localhost:8001` |

The local root `server.py` is a launcher, not the API. It runs `uvicorn server:app` from `backend/` (with reload)
and `craco start` from `frontend/`, then opens Chrome. Its other modes are `--setup` (create `backend/.venv`,
install deps, write `.env` templates), `--backend-only`, `--frontend-only`, `--no-reload` and `--no-browser`.
Setup drops the `litellm @ …` line from `requirements.txt` on purpose: `emergentintegrations` pins the same wheel
URL without the `#sha256` fragment, and pip treats the two as a conflict.

**The local backend uses the real Atlas database** (`cluster0`, `DB_NAME=sihha_ai`) and the real
`EMERGENT_LLM_KEY`. Anything created, edited or deleted locally changes real data and spends real credits. Point
`DB_NAME` at a throwaway database before running seeds, migrations or destructive tests.

## Rules (always follow)

These rules come from Emergent's E1 agent prompt, which is kept word for word in `.claude/emergent-e1-prompt.md`.
Parts of that prompt only apply inside Emergent: its helper agents (`deep_testing_backend_v2`,
`auto_frontend_testing_agent`, `integration_playbook_expert_v2`, `vision_expert_agent`, `support_agent`,
`emergent_integrations_manager`), `supervisorctl`, the `/app` paths, and its starter template, including the
shadcn `components/ui/` folder. Where that file and this one disagree, follow this file.

The full original prompt is loaded below for reference. Read it through the adaptations above, and skip
instructions that call tools or paths that don't exist here:

@.claude/emergent-e1-prompt.md

### New features (workflow)
1. **Clarify first.** Ask about anything unclear and get any external API keys the feature needs before starting.
2. **Frontend first, with mock data.** Put the mock data in a `mock.js` file rather than hard-coding it in
   components. Every button and form must actually work, using browser state only, so the feature doesn't feel
   empty. Write at most 5 files at a time. Check that it renders (frontend logs and a screenshot), say clearly
   that it's mocked, then stop and ask before starting the backend.
3. **Write `contracts.md` before the backend**, at the repo root. Keep it short. It covers the API contracts, what
   in `mock.js` gets replaced, what the backend has to implement, and how the frontend will be wired to it.
4. **Backend:** MongoDB models, the CRUD endpoints and business logic, and error handling. Then switch the
   frontend to the real endpoints and delete the mock data.
5. **Testing:** test the backend first, and re-test it after every backend change. Ask before every frontend test
   pass, not just the first. Don't re-fix anything a test pass has already fixed.

Design-only change requests get frontend-only changes.

### Services, URLs and env
- All backend routes go on the `api = APIRouter(prefix="/api")` router. The Kubernetes ingress sends `/api/*` to
  port 8001 and everything else to the frontend on 3000, so a route without `/api` breaks in production.
- The backend binds to `0.0.0.0:8001`. Never hard-code URLs or ports in code.
- The frontend reaches the backend only through `process.env.REACT_APP_BACKEND_URL` (in practice via
  `frontend/src/lib/api.js`). The backend reaches MongoDB only through `MONGO_URL` and `DB_NAME`.
- Never change `MONGO_URL` or `REACT_APP_BACKEND_URL` in the hosted environment. Locally they have to point at
  Atlas and localhost, but don't change them without the user's go-ahead.
- Missing required env vars fail at import time on purpose (`os.environ[...]`). When the user hands you a key or
  token, put it in `backend/.env` and restart the backend, because `--reload` doesn't watch `.env`. `backend/.env`
  is gitignored.

### Dependencies
- Frontend: **yarn only**, never npm, and add packages only with `yarn add <pkg>`.
- Backend: never hand-edit `requirements.txt`. Install the package, then regenerate the file with
  `pip install <pkg> && pip freeze > backend/requirements.txt`.
- Trust the versions in `package.json` and `requirements.txt` over memory, and don't downgrade without a reason.

### LLMs and third-party services
- LLM calls (OpenAI, Anthropic, Gemini text and vision, plus gpt-image-1 and Nano Banana image generation) go
  through `emergentintegrations` with `EMERGENT_LLM_KEY`. Don't install provider SDKs directly. The key doesn't
  cover audio, email or any other service.
- Ask the user before mocking any third-party API response, and never mock a service the user has given a valid key for.
- If a feature needs an external key you don't have, ask for it before building on top of it.
- Chat features always carry a session id. Test multi-turn conversations across sessions.
- To get out of an error loop, or to learn a new API, search the web for current docs and examples instead of
  relying on memory. Never say something is impossible without searching first.
- **File, image and video uploads** use chunked uploads to get past proxy size limits. Store the files somewhere
  persistent, handle errors at every step, and show detailed progress.

### Working with the user
- Ask before fixing minor issues you weren't asked to fix. Don't chase low-value fixes or rework something that's
  already been fixed.
- Don't proceed on unclear requests: ask first.
- Before any frontend test pass, ask whether the user wants automated frontend testing or will test it themselves.
- Respond in the user's language. Keep summaries short (under ~100 words), say explicitly when anything is mocked,
  and only claim a feature works if it has been verified.
- Run servers and other long tasks in the background, never in the foreground. On Emergent, start servers only
  through supervisor, never by running uvicorn yourself. Locally, use `python3 server.py`.
- Prefer the backend test suite over ad-hoc `curl` calls for testing the API.

### Frontend and design
- Follow `design_guidelines.json` exactly. The palette is Organic & Earthy (sand, forest green, terracotta), with
  **Outfit** for display text and **IBM Plex Sans** for body text. Never use system-UI fonts.
- shadcn is **not** installed in this repo. Use the hand-rolled `.card`, `.btn-primary` and `.btn-outline` classes
  in `index.css` and the shared components in `src/components/`.
- Icons come from `lucide-react`. Never use emoji as icons.
- Every interactive element gets a `data-testid`.
- Never use default purple/blue or purple/pink schemes, plain primary red/blue/green, or dark saturated gradients.
  Gradients are allowed only on hero sections, section backgrounds, large CTAs and decorative accents, must stay
  under 20% of the viewport, and never go on text areas or small buttons.
- Don't add `.App { text-align: center }` or `transition: all`. Transition specific properties on specific elements.
- Prefer inline editing over modals, and keep form focus rings visible.
- If the user gives a specific colour code, use it.
- Interactive elements must never be the same colour as their background, or nearly so.
- Design for motion and depth:
  - micro-animations on every interaction (hover states, transitions, entrance animations)
  - layered shadows and blurs
  - two to three times more whitespace than feels comfortable
  - loading and selection states
- For performance, animate with CSS transforms rather than position changes, lazy-load images, and keep
  animations at 60fps.
- When you create a React context for auth, import React at the top of the file.
- Don't add a hero background image without asking the user first.
- Write real characters (`<`, `>`, `&`, `"`) in code, never HTML entities.
- Keep components under roughly 300–400 lines.
- Every user-facing string needs an Arabic translation (see i18n below).

## Architecture

### Backend (`backend/`)
- `server.py` holds nearly the whole API in a single file of about 5,400 lines: auth, profile, chat/screening, pill
  identification, vitals, medications, dependents, doctor workspace, booking, prescriptions, admin and white-label.
  It's organised by `# ---------- Section ----------` banners, so grep for those to find a feature.
- **Auth:** JWT access (15 min) and refresh (7 days) tokens in httpOnly `Secure` cookies, with a Bearer fallback.
  `get_current_user` plus role dependencies (`require_doctor`, `require_admin`, `require_account_admin`,
  `require_pharmacist`, `require_not_pharmacist`, `require_staging`) gate the routes. Patients sign in at `/auth`
  and clinicians at `/auth/clinician`. Clinician signup only creates a pending request that an admin approves.
- **Feature flags and staging:** `FEATURE_FLAGS` toggles features per platform. `APP_ENV=staging` turns on the
  staging-only features (white-label) and `require_staging`.
- **`agents/`** holds the AI agents (pre-visit briefing, briefing Q&A, intake, screening extraction, scribe,
  patient summary, triage) plus `transcription/` for speech-to-text.
  - Every agent call goes through `agents/runner.run_agent`. It enforces a 60-second timeout, retries once, and
    writes exactly one append-only `agent_runs` document. Failures raise `AgentRunFailed`.
  - Prompts are versioned files in `agents/prompts/*_vN.md`, whose first line is `version: vN`, loaded with
    `load_prompt()`. Add a new version file instead of editing one that's been shipped.
- **`triage/rules.py`** holds the triage rules. **`pharmacy/`** covers compliance and refills for the marketplace.
- **`emailer.py`** sends email through Emergent's email integration, with bodies only from server-side templates.
  **`usage_report.py`** renders the usage report.
- `migrations/` holds one-off data migrations, and the `seed_*.py` files seed demo data. Both write to whatever
  `DB_NAME` points at.
- Pill identification calls the HuggingFace Space `HF_PILLS_SPACE` (default `Hashim971/Tessihha`) through
  `gradio_client`, with GPT vision as a fallback. Audio is Fernet-encrypted with `AUDIO_ENCRYPTION_KEY` and purged
  after `AUDIO_RETENTION_DAYS`.

### Frontend (`frontend/src/`)
- CRA + craco + Tailwind, with React Router routes in `App.js`.
- `lib/api.js` is the shared axios instance (`withCredentials: true`, base URL from `REACT_APP_BACKEND_URL`).
- Contexts:
  - `AuthContext` holds the session, refreshes tokens, and decides the user's role.
  - `PlatformContext` holds the tenant and white-label branding (`/api/tenant?host=…`) and the feature flags. Use
    `FeatureRoute` to gate whole pages behind a flag.
  - `LanguageContext` handles switching between Arabic and English.
- Pages are grouped by role: the patient pages, the doctor pages (`DoctorDashboard`, `DoctorPortal`,
  `DoctorSchedule`, `EncounterDetail`), `admin/`, and `pharmacy-portal/`.

### i18n
- The Arabic UI is built from a dictionary keyed by the English source strings, so English is the key and
  `ar.json` is the lookup.
- `scripts/i18n_extract.py` regex-scans `frontend/src` into `src/i18n/strings_en.json`, and
  `scripts/i18n_translate.py` fills in `src/i18n/ar.json`. Both use hard-coded `/app/...` paths, so they need
  adjusting to run locally.
- After adding or changing UI strings, re-run both scripts.

### Other folders
- `mobile/` is a Capacitor shell that wraps the web app (it doesn't contain app code). The GitHub workflow
  `.github/workflows/mobile-builds.yml` builds its test APK and iOS simulator build on demand.
- `legacy/` is the old Vite/Supabase app, kept for reference only. Don't change it.
- `test_reports/iteration_N.json` holds Emergent's testing-agent reports.

## Tests

The backend tests in `backend/tests/` are **integration tests against a running server**. They make HTTP calls to
`$REACT_APP_BACKEND_URL/api`, and many of them also connect straight to MongoDB, using the `backend/.env` values
and the seeded accounts from `memory/test_credentials.md`. Start the backend first, then:

```bash
cd backend && set -a && . ./.env && set +a && \
  REACT_APP_BACKEND_URL=http://localhost:8001 .venv/bin/python -m pytest tests/test_assignments.py -q
```

Run one test with `tests/<file>.py::<test_name>`. Not every file under `tests/` is a pytest suite: the
`iter*_seed.py`, `*_probe.py` and `cleanup_*.py` files are one-off scripts. These tests create and delete real
records, so point `DB_NAME` at a test database first.

Frontend: `yarn test` (craco). There's no lint script in `package.json`.
