"""Pure compliance rules for the pharmacy marketplace. No I/O, no LLM, fail closed.

Called from three independent layers: catalog ingestion, add-to-cart and checkout.
Every failure is returned as {"rule": <RULE NAME>, "message": <human sentence>, "item_id": <id|None>}
so the API can tell the user precisely what is wrong.
"""
from datetime import datetime, timezone

MAX_PRESCRIPTION_SUPPLY_DAYS = 90
CATEGORIES = ("prescription", "otc", "supplement", "device", "personal_care")
REQUIRED_PHARMACY_LICENCES = ("sfda_license", "moh_license", "cr_number")

CONTROLLED_NOT_ORDERABLE = "CONTROLLED_NOT_ORDERABLE"
UNKNOWN_CATEGORY = "UNKNOWN_CATEGORY"
MISSING_SFDA_REGISTRATION = "MISSING_SFDA_REGISTRATION"
MISSING_DAYS_SUPPLY = "MISSING_DAYS_SUPPLY"
PHARMACY_LICENCE_INCOMPLETE = "PHARMACY_LICENCE_INCOMPLETE"
PHARMACY_UNAVAILABLE = "PHARMACY_UNAVAILABLE"
ITEM_UNAVAILABLE = "ITEM_UNAVAILABLE"
ITEM_OUT_OF_STOCK = "ITEM_OUT_OF_STOCK"
INVALID_QUANTITY = "INVALID_QUANTITY"
MAX_SUPPLY_EXCEEDED = "MAX_SUPPLY_EXCEEDED"
PRESCRIPTION_REQUIRED = "PRESCRIPTION_REQUIRED"
PRESCRIPTION_REJECTED = "PRESCRIPTION_REJECTED"
PRESCRIPTION_EXPIRED = "PRESCRIPTION_EXPIRED"
PRESCRIPTION_NOT_VERIFIED = "PRESCRIPTION_NOT_VERIFIED"
EMPTY_CART = "EMPTY_CART"


def _v(rule, message, item_id=None):
    return {"rule": rule, "message": message, "item_id": item_id}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def check_catalog_item(item: dict, pharmacy: dict = None) -> list:
    """Layer 1 — ingestion. An item that fails here is never stored as orderable."""
    out = []
    item_id = item.get("item_id")
    if item.get("is_controlled"):
        out.append(_v(CONTROLLED_NOT_ORDERABLE,
                      "Controlled medicines cannot be ordered online. Available in-store with a "
                      "prescription only.", item_id))
    if item.get("category") not in CATEGORIES:
        out.append(_v(UNKNOWN_CATEGORY, f"Unknown catalog category {item.get('category')!r}.", item_id))
    if item.get("requires_prescription"):
        if not item.get("sfda_registration_number"):
            out.append(_v(MISSING_SFDA_REGISTRATION,
                          "Prescription medicines need an SFDA registration number before they can be "
                          "listed.", item_id))
        if not item.get("days_supply"):
            out.append(_v(MISSING_DAYS_SUPPLY,
                          "Prescription medicines need a days-supply figure so the three-month cap can be "
                          "enforced.", item_id))
    if pharmacy is not None:
        out.extend(check_pharmacy(pharmacy))
    return out


def check_pharmacy(pharmacy: dict) -> list:
    out = []
    missing = [k for k in REQUIRED_PHARMACY_LICENCES if not (pharmacy or {}).get(k)]
    if missing:
        out.append(_v(PHARMACY_LICENCE_INCOMPLETE,
                      "The partner pharmacy is missing its " + ", ".join(missing) + "."))
    if not (pharmacy or {}).get("active", False):
        out.append(_v(PHARMACY_UNAVAILABLE, "This partner pharmacy is not currently taking orders."))
    return out


def check_add_to_cart(item: dict, pharmacy: dict, qty: int, qty_already_in_cart: int = 0) -> list:
    """Layer 2 — add to cart. Includes every ingestion rule; a bad item never becomes orderable late."""
    out = check_catalog_item(item, pharmacy)
    item_id = item.get("item_id")
    if not item.get("active", False):
        out.append(_v(ITEM_UNAVAILABLE, "This product is no longer listed.", item_id))
    if item.get("stock_status") == "out_of_stock":
        out.append(_v(ITEM_OUT_OF_STOCK, "This product is out of stock at this pharmacy.", item_id))
    if not isinstance(qty, int) or qty < 1:
        out.append(_v(INVALID_QUANTITY, "Quantity must be a whole number of packs, at least one.", item_id))
    elif item.get("requires_prescription"):
        days = item.get("days_supply") or 0
        total_days = (qty + max(qty_already_in_cart, 0)) * days
        if days and total_days > MAX_PRESCRIPTION_SUPPLY_DAYS:
            out.append(_v(MAX_SUPPLY_EXCEEDED,
                          f"Prescription medicines are capped at a {MAX_PRESCRIPTION_SUPPLY_DAYS}-day supply. "
                          f"That quantity covers {total_days} days.", item_id))
    return out


def check_prescription(prescription: dict, now_iso: str = None, require_verified: bool = False) -> list:
    """Sihha never verifies. It only checks a prescription is attached, not rejected, not expired."""
    now_iso = now_iso or _now_iso()
    if not prescription:
        return [_v(PRESCRIPTION_REQUIRED,
                   "This order contains prescription medicines. Attach a prescription so the pharmacy's "
                   "pharmacist can verify it.")]
    status = prescription.get("verification_status")
    out = []
    if status == "rejected":
        out.append(_v(PRESCRIPTION_REJECTED,
                      "The pharmacy's pharmacist rejected this prescription"
                      + (f": {prescription['rejection_reason']}" if prescription.get("rejection_reason") else ".")))
    expires = prescription.get("expires_at")
    if expires and expires < now_iso:
        out.append(_v(PRESCRIPTION_EXPIRED, "This prescription has expired. A newer one is needed."))
    if require_verified and status != "verified":
        out.append(_v(PRESCRIPTION_NOT_VERIFIED,
                      "The pharmacy's pharmacist has not verified this prescription yet."))
    return out


def check_checkout(cart_items: list, pharmacy: dict, prescription: dict = None,
                   now_iso: str = None, require_verified: bool = False) -> list:
    """Layer 3 — checkout. Re-runs every item rule, then the prescription rules."""
    out = []
    if not cart_items:
        return [_v(EMPTY_CART, "Your basket is empty.")]
    out.extend(check_pharmacy(pharmacy))
    days_by_item = {}
    for entry in cart_items:
        item, qty = entry["item"], entry["qty"]
        out.extend(check_add_to_cart(item, pharmacy, qty))
        if item.get("requires_prescription"):
            days_by_item[item["item_id"]] = qty * (item.get("days_supply") or 0)
    for item_id, days in days_by_item.items():
        if days > MAX_PRESCRIPTION_SUPPLY_DAYS and not any(
                v["rule"] == MAX_SUPPLY_EXCEEDED and v["item_id"] == item_id for v in out):
            out.append(_v(MAX_SUPPLY_EXCEEDED,
                          f"Prescription medicines are capped at a {MAX_PRESCRIPTION_SUPPLY_DAYS}-day supply.",
                          item_id))
    if days_by_item:
        out.extend(check_prescription(prescription, now_iso=now_iso, require_verified=require_verified))
    seen, unique = set(), []
    for v in out:
        key = (v["rule"], v["item_id"])
        if key not in seen:
            seen.add(key)
            unique.append(v)
    return unique


def is_orderable(item: dict, pharmacy: dict = None) -> bool:
    """Display helper. Controlled items are shown as information only, never with an order control."""
    return not check_catalog_item(item, pharmacy)
