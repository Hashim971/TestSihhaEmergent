# Auth Testing Playbook (JWT email/password)

Auth is standard email/password with JWT (access 15min + refresh 7d) in httpOnly cookies. Bearer access token also accepted.

## Seeded admin (role: doctor)
- email: admin@sihha.ai
- password: Admin@123

## Step 1: MongoDB Verification
mongosh
use sihha_ai
db.users.findOne({email: "admin@sihha.ai"}, {password_hash: 1})   // hash starts with $2b$
db.users.getIndexes()   // unique index on email

## Step 2: API Testing
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
# Register
curl -c cookies.txt -X POST "$API_URL/api/auth/register" -H "Content-Type: application/json" -d '{"name":"Test User","email":"test@example.com","password":"test123"}'
# Login
curl -c cookies.txt -X POST "$API_URL/api/auth/login" -H "Content-Type: application/json" -d '{"email":"admin@sihha.ai","password":"Admin@123"}'
# Me (cookie)
curl -b cookies.txt "$API_URL/api/auth/me"
# Refresh
curl -b cookies.txt -c cookies.txt -X POST "$API_URL/api/auth/refresh"

## Brute force
5 failed logins for same ip+email → 429 lockout for 15 min (collection: login_attempts).

## Browser Testing
Go to /auth, use auth-tab-login / auth-tab-register, auth-input-name/email/password, auth-submit-btn. Errors shown in auth-error.
