import React, { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { FileSignature, Plus, Trash2, Send, Store, Lock, CheckCircle2 } from "lucide-react";

const EMPTY_ITEM = {
  drug_name: "", generic_name: "", form: "", strength: "", dose: "", frequency: "",
  duration_days: "", quantity: "", refills: 0, instructions: "",
};

export function PrescriptionWriter({ encounterId }) {
  const [rx, setRx] = useState(null);
  const [items, setItems] = useState([{ ...EMPTY_ITEM }]);
  const [meta, setMeta] = useState({ diagnosis: "", notes: "" });
  const [pharmacies, setPharmacies] = useState([]);
  const [pharmacyId, setPharmacyId] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const { data } = await api.get("/prescriptions", { params: { encounter_id: encounterId } });
    const current = data[0] || null;
    setRx(current);
    if (current) {
      setItems(current.items.map((i) => ({ ...EMPTY_ITEM, ...i })));
      setMeta({ diagnosis: current.diagnosis || "", notes: current.notes || "" });
    }
  }, [encounterId]);

  useEffect(() => {
    load().catch(() => {});
    api.get("/pharmacy/pharmacies").then(({ data }) => setPharmacies(data)).catch(() => {});
  }, [load]);

  const signed = rx?.status === "signed";
  const setItem = (i, patch) => setItems(items.map((it, idx) => (idx === i ? { ...it, ...patch } : it)));

  const payload = () => ({
    diagnosis: meta.diagnosis,
    notes: meta.notes,
    items: items.filter((i) => i.drug_name.trim()).map((i) => ({
      ...i,
      duration_days: i.duration_days ? parseInt(i.duration_days, 10) : null,
      quantity: i.quantity ? parseInt(i.quantity, 10) : null,
      refills: parseInt(i.refills || 0, 10),
    })),
  });

  const save = async () => {
    const body = payload();
    if (body.items.length === 0) return toast.error("Add at least one medicine");
    setBusy(true);
    try {
      if (rx && !signed) await api.patch(`/prescriptions/${rx.prescription_id}`, body);
      else await api.post(`/encounters/${encounterId}/prescription`, body);
      toast.success("Prescription saved as a draft");
      await load();
    } catch (e) {
      toast.error(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Could not save");
    } finally {
      setBusy(false);
    }
  };

  const sign = async () => {
    if (!rx) return;
    if (!window.confirm("Sign and send this prescription to the patient? It cannot be edited afterwards.")) return;
    setBusy(true);
    try {
      await api.post(`/prescriptions/${rx.prescription_id}/sign`);
      toast.success("Prescription signed and sent to the patient");
      await load();
    } catch (e) {
      toast.error(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Could not sign");
    } finally {
      setBusy(false);
    }
  };

  const transmit = async () => {
    if (!pharmacyId) return toast.error("Choose a partner pharmacy first");
    setBusy(true);
    try {
      const { data } = await api.post(`/prescriptions/${rx.prescription_id}/transmit`, { pharmacy_id: pharmacyId });
      toast.success(`Sent to ${data.pharmacy.name_en} — their pharmacist verifies before dispensing`);
      (data.unmatched || []).forEach((u) => toast.info(`${u.drug_name}: ${u.reason}`));
      await load();
    } catch (e) {
      toast.error("Could not send to that pharmacy");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card p-6" data-testid="prescription-writer">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold flex items-center gap-2">
            <FileSignature className="h-4 w-4 text-forest" /> Prescription
          </h3>
          <p className="text-xs text-ink-soft mt-0.5">
            Written by you, sent to the patient's app. A partner pharmacist verifies it before dispensing.
          </p>
        </div>
        {signed && (
          <span className="text-xs font-semibold text-forest flex items-center gap-1.5" data-testid="rx-signed-badge">
            <CheckCircle2 className="h-4 w-4" /> Signed {new Date(rx.signed_at).toLocaleString()}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
        <input value={meta.diagnosis} disabled={signed} data-testid="rx-diagnosis-input"
          onChange={(e) => setMeta({ ...meta, diagnosis: e.target.value })} placeholder="Working diagnosis"
          className="border border-line rounded-lg px-3 py-2 text-sm disabled:bg-sand" />
        <input value={meta.notes} disabled={signed} data-testid="rx-notes-input"
          onChange={(e) => setMeta({ ...meta, notes: e.target.value })} placeholder="Note for the patient"
          className="border border-line rounded-lg px-3 py-2 text-sm disabled:bg-sand" />
      </div>

      <div className="mt-4 space-y-3">
        {items.map((item, i) => (
          <div key={i} className="border border-line rounded-xl p-3" data-testid={`rx-item-${i}`}>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {[
                ["drug_name", "Medicine"], ["strength", "Strength"], ["form", "Form"],
                ["dose", "Dose"], ["frequency", "How often"], ["duration_days", "Days"],
                ["quantity", "Quantity"], ["refills", "Refills"],
              ].map(([key, label]) => (
                <input key={key} value={item[key] ?? ""} disabled={signed} placeholder={label}
                  data-testid={`rx-${key}-${i}`} onChange={(e) => setItem(i, { [key]: e.target.value })}
                  className="border border-line rounded-lg px-2.5 py-1.5 text-sm disabled:bg-sand" />
              ))}
            </div>
            <div className="flex items-center gap-2 mt-2">
              <input value={item.instructions ?? ""} disabled={signed} placeholder="Instructions for the patient"
                data-testid={`rx-instructions-${i}`} onChange={(e) => setItem(i, { instructions: e.target.value })}
                className="flex-1 border border-line rounded-lg px-2.5 py-1.5 text-sm disabled:bg-sand" />
              {!signed && items.length > 1 && (
                <button onClick={() => setItems(items.filter((_, idx) => idx !== i))}
                  data-testid={`remove-rx-item-${i}`} className="p-2 rounded-full text-terracotta hover:bg-terracotta/10">
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
            {item.is_controlled && (
              <p className="text-xs text-terracotta mt-2 flex items-center gap-1.5" data-testid={`rx-controlled-${i}`}>
                <Lock className="h-3 w-3" /> Controlled medicine — dispensed in clinic only, never sent online.
              </p>
            )}
          </div>
        ))}
      </div>

      {!signed ? (
        <div className="flex flex-wrap items-center gap-2 mt-4">
          <button onClick={() => setItems([...items, { ...EMPTY_ITEM }])} className="btn-outline !py-1.5 !px-3 text-xs"
            data-testid="add-rx-item-btn">
            <Plus className="h-3.5 w-3.5" /> Add medicine
          </button>
          <button onClick={save} disabled={busy} className="btn-outline !py-1.5 !px-3 text-xs"
            data-testid="save-rx-btn">Save draft</button>
          {rx && (
            <button onClick={sign} disabled={busy} className="btn-primary !py-1.5 !px-3 text-xs"
              data-testid="sign-rx-btn">
              <Send className="h-3.5 w-3.5" /> Sign and send to patient
            </button>
          )}
        </div>
      ) : (
        <div className="mt-4 border-t border-line pt-4">
          {rx.transmitted_at ? (
            <p className="text-sm flex items-center gap-2" data-testid="rx-transmitted-line">
              <Store className="h-4 w-4 text-forest" />
              Sent to {rx.transmitted_pharmacy_name} on {new Date(rx.transmitted_at).toLocaleString()}
            </p>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <select value={pharmacyId} onChange={(e) => setPharmacyId(e.target.value)}
                data-testid="rx-pharmacy-select" className="border border-line rounded-lg px-3 py-2 text-sm bg-white">
                <option value="">Send to a partner pharmacy…</option>
                {pharmacies.map((p) => (
                  <option key={p.pharmacy_id} value={p.pharmacy_id}>
                    {p.name_en} — SFDA {p.sfda_license}
                  </option>
                ))}
              </select>
              <button onClick={transmit} disabled={busy} className="btn-primary !py-1.5 !px-3 text-xs"
                data-testid="transmit-rx-btn">
                <Send className="h-3.5 w-3.5" /> Send to pharmacy
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
