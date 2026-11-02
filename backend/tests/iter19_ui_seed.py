# Creates one OTC order at Al Dawaa for solo.patient (for UI testing); prints order_id.
import os, requests
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
s = requests.Session()
s.post(f"{API}/auth/login", json={"email": "solo.patient@sihha.ai", "password": "Patient@123"}).raise_for_status()
s.delete(f"{API}/pharmacy/cart")
s.post(f"{API}/pharmacy/cart/items", json={"item_id": "item_7b3c5dd64c3b", "qty": 1}).raise_for_status()
r = s.post(f"{API}/pharmacy/checkout", json={})
r.raise_for_status()
o = r.json().get("order", r.json())
print(o["order_id"], o["status"])
