import React, { useState } from "react";
import { toast } from "sonner";
import { Eye, EyeOff, Save } from "lucide-react";

export function ListingTab({ account, save }) {
  const [form, setForm] = useState({
    listed_in_app: !!account.listed_in_app, city: account.city || "", about: account.about || "",
    specialties: (account.specialties || []).join(", "),
  });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await save({ ...form, specialties: form.specialties.split(",").map((s) => s.trim()).filter(Boolean) });
      toast.success(form.listed_in_app ? "Listed in the patient app" : "Hidden from the patient app");
    } catch (err) {
      toast.error(err?.response?.data?.detail?.[0]?.msg || err?.response?.data?.detail || "Could not save the listing");
    } finally {
      setBusy(false);
    }
  };

  const field = "mt-1 w-full border border-line rounded-lg px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-forest";
  return (
    <form onSubmit={submit} className="card p-6 space-y-4 max-w-2xl" data-testid="listing-tab">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Patient app listing</h2>
          <p className="text-sm text-ink-soft mt-1">Listed hospitals appear in Find Care. Patients pick a hospital, then one of its doctors.</p>
        </div>
        <button type="button" onClick={() => setForm({ ...form, listed_in_app: !form.listed_in_app })} data-testid="listing-toggle"
          className={`shrink-0 inline-flex items-center gap-2 px-3 py-2 rounded-full text-xs font-semibold border ${form.listed_in_app ? "bg-forest text-white border-forest" : "bg-white border-line text-ink-soft"}`}>
          {form.listed_in_app ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
          {form.listed_in_app ? "Listed" : "Not listed"}
        </button>
      </div>
      <label className="block text-sm"><span className="text-xs uppercase tracking-[0.15em] text-ink-soft">City</span>
        <input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} className={field} data-testid="listing-city-input" /></label>
      <label className="block text-sm"><span className="text-xs uppercase tracking-[0.15em] text-ink-soft">About (shown to patients)</span>
        <textarea rows={3} maxLength={600} value={form.about} onChange={(e) => setForm({ ...form, about: e.target.value })} className={field} data-testid="listing-about-input" /></label>
      <label className="block text-sm"><span className="text-xs uppercase tracking-[0.15em] text-ink-soft">Specialties, comma separated</span>
        <input value={form.specialties} onChange={(e) => setForm({ ...form, specialties: e.target.value })} placeholder="Cardiology, Family Medicine" className={field} data-testid="listing-specialties-input" /></label>
      <button type="submit" disabled={busy} className="btn-primary" data-testid="listing-save-btn"><Save className="h-4 w-4" /> {busy ? "Saving…" : "Save listing"}</button>
    </form>
  );
}
