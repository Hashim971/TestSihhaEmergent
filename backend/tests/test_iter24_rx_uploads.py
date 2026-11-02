# Iteration 24: patient prescription uploads (AI read -> confirm -> medications) + visits gating
import io
import os
import pytest
import requests
from PIL import Image, ImageDraw, ImageFont

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


def login(email, pw, path="/api/auth/login"):
    s = requests.Session()
    r = s.post(f"{BASE_URL}{path}", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code} {r.text[:200]}")
    return s


def rx_image():
    img = Image.new("RGB", (900, 600), "white")
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
    except Exception:
        f = ImageFont.load_default()
    lines = ["Dr. Test Clinic - Prescription", "Patient: Solo Patient", "Date: 2026-01-10",
             "Rx:", "1. Metformin 500 mg - 1 tablet twice daily", "2. Atorvastatin 20 mg - once at bedtime",
             "Signed: Dr. Test"]
    for i, ln in enumerate(lines):
        d.text((40, 40 + i * 70), ln, fill="black", font=f)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def solo():
    return login("solo.patient@sihha.ai", "Patient@123")


@pytest.fixture(scope="module")
def omar():
    return login("omar.patient@sihha.ai", "Patient@123")


@pytest.fixture(scope="module")
def upload(solo):
    r = solo.post(f"{BASE_URL}/api/rx-uploads", files={"file": ("rx.png", rx_image(), "image/png")}, timeout=120)
    assert r.status_code == 200, r.text
    doc = r.json()
    yield doc
    # cleanup
    solo.delete(f"{BASE_URL}/api/rx-uploads/{doc['upload_id']}")
    meds = solo.get(f"{BASE_URL}/api/medications").json()
    for m in meds:
        if m.get("rx_upload_id") == doc["upload_id"] or m["name"].startswith("TEST_"):
            solo.delete(f"{BASE_URL}/api/medications/{m['medication_id']}")


class TestRxUpload:
    def test_upload_reads_meds(self, upload):
        assert upload["upload_id"].startswith("rxu_")
        assert upload["status"] == "pending_review"
        assert "path" not in upload and "user_id" not in upload and "_id" not in upload
        assert upload["image_url"] == f"/api/rx-uploads/{upload['upload_id']}/image"
        meds = upload["extracted"]["medications"]
        names = " ".join(m["name"].lower() for m in meds)
        print("extracted:", meds)
        assert "metformin" in names
        met = [m for m in meds if "metformin" in m["name"].lower()][0]
        assert len(met["times"]) == 2

    def test_list_contains(self, solo, upload):
        r = solo.get(f"{BASE_URL}/api/rx-uploads")
        assert r.status_code == 200
        assert upload["upload_id"] in [d["upload_id"] for d in r.json()]

    def test_image_owner(self, solo, upload):
        r = solo.get(f"{BASE_URL}/api{upload['image_url'][4:]}")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/jpeg")
        assert len(r.content) > 1000

    def test_image_other_404(self, omar, upload):
        r = omar.get(f"{BASE_URL}/api/rx-uploads/{upload['upload_id']}/image")
        assert r.status_code == 404
        r = omar.post(f"{BASE_URL}/api/rx-uploads/{upload['upload_id']}/confirm",
                      json={"medications": [{"name": "TEST_x", "dosage": "1", "times": ["08:00"]}]})
        assert r.status_code == 404
        assert omar.delete(f"{BASE_URL}/api/rx-uploads/{upload['upload_id']}").status_code == 404

    def test_image_unauth(self, upload):
        r = requests.get(f"{BASE_URL}/api/rx-uploads/{upload['upload_id']}/image")
        assert r.status_code == 401

    def test_confirm_validation(self, solo, upload):
        u = upload["upload_id"]
        r = solo.post(f"{BASE_URL}/api/rx-uploads/{u}/confirm",
                      json={"medications": [{"name": "TEST_Med", "dosage": "", "times": ["08:00"]}]})
        assert r.status_code == 400
        r = solo.post(f"{BASE_URL}/api/rx-uploads/{u}/confirm",
                      json={"medications": [{"name": "TEST_Med", "dosage": "5 mg", "times": []}]})
        assert r.status_code == 400
        r = solo.post(f"{BASE_URL}/api/rx-uploads/{u}/confirm",
                      json={"medications": [{"name": "TEST_Med", "dosage": "5 mg", "times": ["8am"]}]})
        assert r.status_code == 400
        r = solo.post(f"{BASE_URL}/api/rx-uploads/{u}/confirm", json={"medications": []})
        assert r.status_code == 400

    def test_confirm_adds_meds(self, solo, upload):
        u = upload["upload_id"]
        r = solo.post(f"{BASE_URL}/api/rx-uploads/{u}/confirm", json={"medications": [
            {"name": "TEST_Metformin", "dosage": "500 mg", "times": ["08:00", "20:00"],
             "instructions": "with food", "quantity_dispensed": 60}]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["added"] == 1
        meds = solo.get(f"{BASE_URL}/api/medications").json()
        m = [x for x in meds if x["medication_id"] == body["medication_ids"][0]]
        assert m and m[0]["name"] == "TEST_Metformin" and m[0]["times"] == ["08:00", "20:00"]
        assert m[0]["source"] == "prescription_upload" and m[0]["rx_upload_id"] == u
        lst = solo.get(f"{BASE_URL}/api/rx-uploads").json()
        d = [x for x in lst if x["upload_id"] == u][0]
        assert d["status"] == "confirmed"
        assert body["medication_ids"][0] in d["added_medication_ids"]

    def test_bad_file(self, solo):
        r = solo.post(f"{BASE_URL}/api/rx-uploads", files={"file": ("x.txt", b"hello not an image", "text/plain")})
        assert r.status_code == 400

    def test_soft_delete(self, solo):
        r = solo.post(f"{BASE_URL}/api/rx-uploads", files={"file": ("blank.png", rx_image(), "image/png")},
                      timeout=120)
        assert r.status_code == 200
        u = r.json()["upload_id"]
        assert solo.delete(f"{BASE_URL}/api/rx-uploads/{u}").status_code == 200
        assert u not in [d["upload_id"] for d in solo.get(f"{BASE_URL}/api/rx-uploads").json()]
        assert solo.get(f"{BASE_URL}/api/rx-uploads/{u}/image").status_code == 404


class TestVisitsGating:
    def test_solo_no_account(self, solo):
        me = solo.get(f"{BASE_URL}/api/auth/me").json()
        assert not me.get("account_id")

    def test_omar_has_account(self, omar):
        me = omar.get(f"{BASE_URL}/api/auth/me").json()
        assert me.get("account_id")
