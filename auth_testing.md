# Auth testing playbook (Emergent-managed Google sign-in)

## How this app is wired
- Google sign-in is **patients only**. Clinicians and admins keep the password portal at `/auth/clinician`.
- `POST /api/auth/google/session {session_id}` exchanges the Emergent session for **this app's own JWT cookies**
  (`access_token` / `refresh_token`), so every existing route keeps working unchanged. The Emergent
  `session_token` is stored in `user_sessions` (provider `google`, 7-day expiry) for audit and revocation.
- A Google email that already has a password account is **linked** (same `user_id`, `auth_providers.google: true`).
  A Google email belonging to a doctor or admin is refused with 403.
- New Google users are created as `role: "patient"`, `onboarding_completed: false`, and land on `/onboarding`.
- Frontend: `AppRouter` in `App.js` checks `useLocation().hash` for `session_id=` **during render** and renders
  `pages/AuthCallback.jsx`; `AuthContext` skips its `/auth/me` check while that hash is present.

## Testing the exchange endpoint
```bash
API=https://<preview-host>/api
# invalid/expired session id must be rejected
curl -s -X POST $API/auth/google/session -H 'Content-Type: application/json' \
  -d '{"session_id":"not-a-real-session"}' -i | head -1   # expect 401
```

## Testing the callback wiring without Google
Open `https://<preview-host>/dashboard#session_id=fake-session`. Expected: the "Signing you in…" screen renders,
the POST fails, a toast explains the link expired, and the browser lands on `/auth`. That proves the hash
detection, the AuthProvider race-condition guard and the error path.

## Testing an authenticated session
The app's session is a normal JWT cookie, so tests sign in with the password accounts in
`/app/memory/test_credentials.md` (`POST /api/auth/login`) and reuse the cookie jar — there is no separate
`session_token` cookie to plant.

## Full Google round trip
Needs a human: click **Continue with Google** on `/auth`, pick a Google account, and confirm you land on
`/onboarding` (new account) or `/dashboard` (existing account), with the name and photo in the sidebar.

## Checklist
- [ ] `session_id` in the URL fragment is processed once (useRef guard, StrictMode safe)
- [ ] Hash is cleared with `history.replaceState` after the exchange
- [ ] Users are matched by lowercase email; `_id` is never returned (`USER_PROJECTION`)
- [ ] Clinician/admin emails are refused with 403 on the Google path
- [ ] `redirect` is built from `window.location.origin` — never hardcoded, no fallbacks
