import React, { useState } from "react";
import { toast } from "sonner";
import { BadgeCheck } from "lucide-react";
import { api } from "../../lib/api";

const LABELS = { sfda_license: "SFDA licence", moh_license: "MOH licence", cr_number: "Commercial registration (CR)" };

export function LicencesCard({ licences, onSaved }) {
  const [form, setForm] = useState(() => Object.fromEntries(Object.keys(LABELS).map((k) => [k, licences[k] || ""])));
  const [busy, setBusy] = useState(false);
  const complete = Object.keys(LABELS).every((k) => licences[k]);

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.patch("/pharmacy-portal/licences", form);
      toast.success("Licences saved");
      onSaved();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not save licences");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={save} className="card p-5" data-testid="licences-card">
      <h2 className="text-sm font-semibold flex items-center gap-2"><BadgeCheck className={`h-4 w-4 ${complete ? "text-forest" : "text-amber-600"}`} /> Licences {complete ? "complete" : "needed before patients can order"}</h2>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-3">
        {Object.entries(LABELS).map(([k, label]) => (
          <label key={k} className="block text-sm"><span className="text-xs uppercase tracking-[0.12em] text-ink-soft">{label}</span>
            <input value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} className="mt-1 w-full border border-line rounded-lg px-3 py-2 text-sm" data-testid={`licence-${k}`} /></label>
        ))}
      </div>
      <button type="submit" disabled={busy} className="btn-outline !py-1.5 !px-3 text-xs mt-3" data-testid="licences-save-btn">{busy ? "Saving…" : "Save licences"}</button>
      <p className="text-[11px] text-ink-soft mt-2">Only the pharmacy owner can change these.</p>
    </form>
  );
}
