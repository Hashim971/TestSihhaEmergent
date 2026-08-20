import React, { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { toast } from "sonner";
import { X, Trash2, Upload, AlertTriangle, ExternalLink, ShoppingBag } from "lucide-react";

export function CartDrawer({ open, onClose, cart, reload, onOrdered }) {
  const [prescriptions, setPrescriptions] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) api.get("/pharmacy/prescriptions").then(({ data }) => setPrescriptions(data)).catch(() => {});
  }, [open, cart?.prescription_id]);

  if (!open) return null;
  const items = cart?.items || [];
  const needsRx = items.some((i) => i.requires_prescription);
  const blocking = cart?.violations || [];

  const remove = async (itemId) => {
    await api.delete(`/pharmacy/cart/items/${itemId}`);
    reload();
  };

  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append("source", "upload");
      form.append("file", file);
      const { data } = await api.post("/pharmacy/prescriptions", form);
      setPrescriptions((prev) => [data, ...prev]);
      await api.post("/pharmacy/cart/prescription", { prescription_id: data.prescription_id });
      toast.success("Prescription attached — the pharmacy's pharmacist will verify it");
      reload();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Could not upload the prescription");
    } finally {
      setBusy(false);
    }
  };

  const attach = async (prescriptionId) => {
    await api.post("/pharmacy/cart/prescription", { prescription_id: prescriptionId || null });
    reload();
  };

  const checkout = async () => {
    setBusy(true);
    try {
      const { data: order } = await api.post("/pharmacy/checkout", {});
      if (order.fulfilment_mode === "handoff" && order.handoff_url) {
        window.open(order.handoff_url, "_blank", "noopener");
        toast.success("Basket handed to the partner pharmacy — finish the purchase in their tab");
      } else {
        toast.success(order.status === "awaiting_pharmacist_verification"
          ? "Sent to the pharmacy — their pharmacist verifies the prescription next"
          : "Confirmed by the pharmacy — collect it at the branch");
      }
      reload();
      onOrdered(order);
    } catch (e) {
      const violations = e?.response?.data?.detail?.violations;
      if (violations) violations.forEach((v) => toast.error(v.message));
      else toast.error("Checkout failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end" data-testid="cart-drawer">
      <div className="absolute inset-0 bg-ink/30" onClick={onClose} />
      <div className="relative w-full max-w-md h-full bg-white border-l border-line flex flex-col shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-line">
          <h3 className="font-semibold flex items-center gap-2">
            <ShoppingBag className="h-4 w-4 text-forest" /> Your basket
          </h3>
          <button onClick={onClose} data-testid="close-cart-btn" className="p-1.5 rounded-full hover:bg-sand">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {cart?.pharmacy && (
            <div className="border border-line rounded-xl px-3 py-2.5" data-testid="cart-pharmacy">
              <p className="text-sm font-medium">{cart.pharmacy.name_en}</p>
              <p className="text-xs text-ink-soft mt-0.5">
                SFDA {cart.pharmacy.sfda_license} · MOH {cart.pharmacy.moh_license} · CR {cart.pharmacy.cr_number}
              </p>
              <p className="text-[10px] uppercase tracking-wider text-ink-soft mt-1">
                {cart.pharmacy.fulfilment_mode === "handoff"
                  ? "You finish this purchase on the pharmacy's own site"
                  : "Prepared by the pharmacy for collection"}
              </p>
            </div>
          )}

          {items.length === 0 && <p className="text-sm text-ink-soft" data-testid="cart-empty">Your basket is empty.</p>}

          {items.map((line) => (
            <div key={line.item_id} className="border border-line rounded-xl px-3 py-2.5"
              data-testid={`cart-line-${line.item_id}`}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-medium">{line.name_en}</p>
                  <p className="text-xs text-ink-soft" dir="rtl">{line.name_ar}</p>
                  <p className="text-xs text-ink-soft mt-1">
                    {line.qty} × {line.price_sar} SAR
                    {line.requires_prescription ? " · prescription only" : ""}
                  </p>
                </div>
                <button onClick={() => remove(line.item_id)} data-testid={`remove-line-${line.item_id}`}
                  className="p-1.5 rounded-full hover:bg-terracotta/10 text-terracotta">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              {(line.violations || []).map((v) => (
                <p key={v.rule} className="text-xs text-terracotta mt-1.5 flex items-start gap-1"
                  data-testid={`line-violation-${line.item_id}`}>
                  <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0" /> {v.message}
                </p>
              ))}
            </div>
          ))}

          {needsRx && (
            <div className="border border-line rounded-xl px-3 py-3" data-testid="prescription-block">
              <p className="text-sm font-medium">Prescription</p>
              <p className="text-xs text-ink-soft mt-0.5">
                Sihha only passes this to the pharmacy. Their licensed pharmacist decides — we never verify it.
              </p>
              <select value={cart?.prescription_id || ""} onChange={(e) => attach(e.target.value)}
                data-testid="prescription-select"
                className="mt-2 w-full border border-line rounded-lg px-3 py-2 text-sm">
                <option value="">No prescription attached</option>
                {prescriptions.map((rx) => (
                  <option key={rx.prescription_id} value={rx.prescription_id}>
                    {new Date(rx.created_at).toLocaleDateString()} · {rx.verification_status}
                  </option>
                ))}
              </select>
              <label className="btn-outline !py-1.5 !px-3 text-xs mt-2 inline-flex cursor-pointer">
                <Upload className="h-3.5 w-3.5" /> Upload a prescription
                <input type="file" accept="image/*,.pdf" className="hidden" data-testid="prescription-upload-input"
                  onChange={(e) => upload(e.target.files?.[0])} />
              </label>
            </div>
          )}

          {blocking.filter((v) => !v.item_id).map((v) => (
            <p key={v.rule} className="text-xs text-terracotta flex items-start gap-1" data-testid="cart-violation">
              <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0" /> {v.message}
            </p>
          ))}
        </div>

        <div className="border-t border-line px-5 py-4 space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-ink-soft">Total</span>
            <span className="font-heading text-lg font-bold text-forest" data-testid="cart-total">
              {cart?.total_sar || 0} SAR
            </span>
          </div>
          <p className="text-[10px] text-ink-soft">
            Sihha is not a pharmacy. Medicines are dispensed by the licensed partner above. No delivery — collect
            in store or complete the purchase on the partner's site.
          </p>
          <button onClick={checkout} disabled={busy || items.length === 0 || blocking.length > 0}
            data-testid="checkout-btn"
            className={`btn-primary w-full justify-center ${busy || items.length === 0 || blocking.length > 0 ? "opacity-40 cursor-not-allowed" : ""}`}>
            {cart?.pharmacy?.fulfilment_mode === "handoff"
              ? <><ExternalLink className="h-4 w-4" /> Continue at {cart.pharmacy.name_en}</>
              : "Send to the pharmacy"}
          </button>
        </div>
      </div>
    </div>
  );
}
