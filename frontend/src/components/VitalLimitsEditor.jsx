import React, { useState } from "react";
import { toast } from "sonner";
import { SlidersHorizontal, RotateCcw } from "lucide-react";
import { api } from "../lib/api";

const FIELDS = [
  ["systolic", "Systolic (mmHg)"],
  ["diastolic", "Diastolic (mmHg)"],
  ["glucose", "Blood sugar (mg/dL)"],
];

export function VitalLimitsEditor({ patientId, data, onChange }) {
  const [open, setOpen] = useState(false);
  const initial = () => Object.fromEntries(data.trends.flatMap((t) => [[`${t.metric}_min`, t.limit.min], [`${t.metric}_max`, t.limit.max]]));
  const [form, setForm] = useState(initial);
  const [note, setNote] = useState(data.limits?.note || "");
  const [busy, setBusy] = useState(false);

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const base = initial();
      const custom = data.limits || {};
      // Only send limits the doctor changed or had already customised, so untouched metrics stay standard.
      const body = { note, ...Object.fromEntries(Object.entries(form).map(([k, v]) => [k,
        v === "" || (Number(v) === Number(base[k]) && custom[k] == null) ? null : Number(v)])) };
      const { data: next } = await api.put(`/doctor/patients/${patientId}/vital-limits`, body);
      onChange(next);
      setOpen(false);
      toast.success("Limits saved for this patient");
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : d?.[0]?.msg || "Could not save limits");
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    const { data: next } = await api.delete(`/doctor/patients/${patientId}/vital-limits`);
    onChange(next);
    setForm(Object.fromEntries(next.trends.flatMap((t) => [[`${t.metric}_min`, t.limit.min], [`${t.metric}_max`, t.limit.max]])));
    toast.success("Back to standard limits");
  };

  return (
    <div className="mt-4 border-t border-line pt-4" data-testid="vital-limits-editor">
      <div className="flex flex-wrap items-center gap-2">
        <button onClick={() => { setForm(initial()); setOpen(!open); }} className="btn-outline !py-1.5 !px-3 text-xs" data-testid="vital-limits-toggle">
          <SlidersHorizontal className="h-3.5 w-3.5" /> {open ? "Close" : "Set this patient's limits"}
        </button>
        {data.limits && (
          <>
            <span className="text-xs text-ink-soft" data-testid="vital-limits-owner">Custom limits by <bdi>{data.limits.set_by_name}</bdi></span>
            <button onClick={reset} className="text-xs text-terracotta underline inline-flex items-center gap-1" data-testid="vital-limits-reset"><RotateCcw className="h-3 w-3" /> Use standard limits</button>
          </>
        )}
      </div>
      {open && (
        <form onSubmit={save} className="mt-3 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {FIELDS.map(([m, label]) => (
              <div key={m} className="text-sm">
                <p className="text-xs uppercase tracking-[0.12em] text-ink-soft mb-1">{label}</p>
                <div className="flex items-center gap-2">
                  <input type="number" step="1" value={form[`${m}_min`]} onChange={(e) => setForm({ ...form, [`${m}_min`]: e.target.value })} className="w-full border border-line rounded-lg px-2 py-1.5" data-testid={`limit-${m}-min`} aria-label={`${label} low`} />
                  <span className="text-ink-soft">–</span>
                  <input type="number" step="1" value={form[`${m}_max`]} onChange={(e) => setForm({ ...form, [`${m}_max`]: e.target.value })} className="w-full border border-line rounded-lg px-2 py-1.5" data-testid={`limit-${m}-max`} aria-label={`${label} high`} />
                </div>
              </div>
            ))}
          </div>
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} placeholder="Why these limits (shown to colleagues)" className="w-full border border-line rounded-lg px-3 py-2 text-sm" data-testid="vital-limits-note" />
          <button type="submit" disabled={busy} className="btn-primary !py-2 text-sm" data-testid="vital-limits-save">{busy ? "Saving…" : "Save limits"}</button>
        </form>
      )}
    </div>
  );
}
