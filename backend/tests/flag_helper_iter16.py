# Helper for iteration 16 UI tests: python flag_helper_iter16.py off|override|restore|show
import sys
import requests
from dotenv import dotenv_values

API = dotenv_values('/app/frontend/.env')['REACT_APP_BACKEND_URL'].rstrip('/') + "/api"
s = requests.Session()
s.post(f"{API}/auth/login", json={"email": "admin@sihha.ai", "password": "Admin@123"}).raise_for_status()
acc = s.get(f"{API}/admin/accounts", params={"q": "Al Noor"}).json()["items"][0]
aid = acc["account_id"]
cmd = sys.argv[1]
if cmd == "off":
    s.put(f"{API}/admin/flags/pharmacy_marketplace", json={"enabled": False})
    s.patch(f"{API}/admin/accounts/{aid}", json={"features": {"white_label": True}})
elif cmd == "override":
    s.patch(f"{API}/admin/accounts/{aid}", json={"features": {"white_label": True, "pharmacy_marketplace": True}})
elif cmd == "globalon":
    s.put(f"{API}/admin/flags/pharmacy_marketplace", json={"enabled": True})
elif cmd == "restore":
    s.put(f"{API}/admin/flags/pharmacy_marketplace", json={"enabled": True})
    s.patch(f"{API}/admin/accounts/{aid}", json={"features": {"white_label": True}})
print(aid, s.get(f"{API}/admin/accounts/{aid}").json()["features"],
      {f["key"]: f["enabled"] for f in s.get(f"{API}/admin/flags").json()["flags"]})
