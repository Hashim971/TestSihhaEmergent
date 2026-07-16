# Test Credentials — Sihha AI

Auth is Emergent-managed Google OAuth (no app-managed passwords).

## Test session for automation (inserted in MongoDB, db: sihha_ai)
- user_id: test-ui-1784235150842
- session_token: test_ui_session_1784235150842 (expires ~7 days from 2026-06 test run)
- Use as httpOnly cookie `session_token` on domain ab05f5cb-2f3a-4bd8-b2b4-33cfdc0ac6c8.preview.emergentagent.com, or `Authorization: Bearer <token>`

## Creating fresh test sessions
See /app/auth_testing.md for the mongosh snippet (insert into users + user_sessions).

## Roles
- Users default to role=patient. POST /api/auth/role {"role":"doctor"} to switch (UI: toggle-role-btn).
- Doctor portal lists patients with sharing_enabled=true (UI: toggle-sharing-btn).
