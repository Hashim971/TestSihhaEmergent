# Seeds admin-pharmacies UI data for iteration 20: one pending app (to reject), one approved pharmacy with a
# silver sponsorship request awaiting payment and one invited staff member. Prints ids. Clean with cleanup_iter19.py.
import os, uuid, requests
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
admin = requests.Session()
admin.post(f"{API}/auth/login", json={"email": "admin@sihha.ai", "password": "Admin@123"}).raise_for_status()
out = {}
for tag in ("rej", "ok"):
    email = f"test_ui_pharm_{tag}_{uuid.uuid4().hex[:5]}@example.com"
    r = requests.post(f"{API}/pharmacy-portal/apply", json={"pharmacy_name": f"TEST_ UI {tag}", "city": "Riyadh",
                      "sfda_license": "SFDA-1", "name": "TEST_ Owner", "phone": "0500000000", "email": email, "password": "Test@1234"})
    r.raise_for_status()
    out[tag] = (r.json()["application_id"], email)
pid = admin.post(f"{API}/admin/pharmacy-applications/{out['ok'][0]}/approve").json()["pharmacy_id"]
owner = requests.Session()
owner.post(f"{API}/auth/login", json={"email": out["ok"][1], "password": "Test@1234"}).raise_for_status()
spr = owner.post(f"{API}/pharmacy-portal/sponsorship/requests", json={"tier": "silver"}).json()["request_id"]
staff = admin.post(f"{API}/admin/pharmacies/{pid}/staff", json={"name": "TEST_ Staff", "email": f"test_staff_{uuid.uuid4().hex[:5]}@example.com"}).json()["user_id"]
print(f"REJ_APP={out['rej'][0]} PID={pid} SPR={spr} STAFF={staff} OWNER={out['ok'][1]}")
