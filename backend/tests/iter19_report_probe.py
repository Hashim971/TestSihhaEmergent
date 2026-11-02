# One-off live check: screening report uses new prompts (report-v1/chat-v1, 'SCREENING SUMMARY').
import os, requests
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
s = requests.Session()
s.post(f"{API}/auth/login", json={"email": "solo.patient@sihha.ai", "password": "Patient@123"}).raise_for_status()
sid = s.post(f"{API}/chat/sessions", json={}).json()["chat_session_id"]
r = s.post(f"{API}/chat/sessions/{sid}/message", json={"text": "TEST_ I have had a mild sore throat for 2 days, no fever, I am 30 years old, otherwise healthy."}, stream=True, timeout=120)
print("msg status", r.status_code, "".join(c.decode(errors="ignore") for c in r.iter_content(None))[-200:])
rep = s.post(f"{API}/chat/sessions/{sid}/report", timeout=180)
print("report status", rep.status_code)
d = rep.json()
print("prompt_version", d.get("prompt_version"), "has SCREENING SUMMARY", "SCREENING SUMMARY" in (d.get("content") or "").upper())
print("disposition", (d.get("disposition") or {}).get("level"), "report_id", d.get("report_id"))
