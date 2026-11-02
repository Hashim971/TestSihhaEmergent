# Probe: PUT /api/profile/doctor bypasses the one-active-hospital rule (iteration 19). Restores state.
import os, requests
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
def login(e, p):
    s = requests.Session(); s.post(f"{API}/auth/login", json={"email": e, "password": p}).raise_for_status(); return s
solo = login("solo.patient@sihha.ai", "Patient@123")
layla = login("dr.layla@sihha.ai", "Doctor@123")
sid = solo.get(f"{API}/auth/me").json()["user_id"]
solo.put(f"{API}/profile/hospital", json={"account_id": "ACC-2BC6ED"})
r = solo.put(f"{API}/profile/doctor", json={"doctor_user_id": "user_b1000ae5aad6"})
print("choose Layla (Al Noor) while hospital=Jeddah:", r.status_code)
print("hospital now:", (solo.get(f"{API}/profile/hospital").json().get("hospital") or {}).get("account_id"))
print("Layla access to record:", layla.get(f"{API}/doctor/patients/{sid}/summary").status_code)
solo.put(f"{API}/profile/doctor", json={"doctor_user_id": None})
solo.put(f"{API}/profile/hospital", json={"account_id": None})
print("restored:", solo.get(f"{API}/profile/hospital").json())
