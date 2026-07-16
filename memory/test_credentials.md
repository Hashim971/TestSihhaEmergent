# Test Credentials — Sihha AI

Auth: standard email/password (JWT access 15min + refresh 7d, httpOnly cookies; Bearer access token also accepted).

## Seeded admin account (role: doctor — can access Doctor Portal)
- email: admin@sihha.ai
- password: Admin@123

## Test patient account
- email: patient1@test.com
- password: test123
- role: patient

## Endpoints
- POST /api/auth/register {name, email, password}
- POST /api/auth/login {email, password}
- GET /api/auth/me · POST /api/auth/refresh · POST /api/auth/logout
- Brute force: 5 failed logins per ip+email → 15 min lockout (429)

## UI
- /auth page: auth-tab-login, auth-tab-register, auth-input-name/email/password, auth-submit-btn, auth-error
- Role toggle: toggle-role-btn (sidebar). Sharing: toggle-sharing-btn.

See /app/auth_testing.md for full test playbook.
