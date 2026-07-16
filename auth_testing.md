# Auth Testing Playbook (Emergent Google Auth)

## Step 1: Create Test User & Session
mongosh --eval "
use('sihha_ai');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'test.user.' + Date.now() + '@example.com',
  name: 'Test User',
  picture: 'https://via.placeholder.com/150',
  role: 'patient',
  sharing_enabled: false,
  created_at: new Date().toISOString()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000).toISOString(),
  created_at: new Date().toISOString()
});
print('Session token: ' + sessionToken);
print('User ID: ' + userId);
"

## Step 2: Test Backend API
curl -X GET "$API_URL/api/auth/me" -H "Authorization: Bearer YOUR_SESSION_TOKEN"

## Step 3: Browser Testing (set cookie)
await page.context.add_cookies([{
    "name": "session_token",
    "value": "YOUR_SESSION_TOKEN",
    "domain": "<preview-domain>",
    "path": "/",
    "httpOnly": true,
    "secure": true,
    "sameSite": "None"
}]);

## Checklist
- User document has user_id field (custom UUID)
- Session user_id matches user's user_id
- All queries exclude _id
- /api/auth/me returns user data
- Dashboard loads without redirect
