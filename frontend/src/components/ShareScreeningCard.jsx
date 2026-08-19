import React, { useState, useEffect } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Share2, Check } from "lucide-react";

export function ShareScreeningCard({ report }) {
  const [visits, setVisits] = useState([]);
  const [selected, setSelected] = useState("");
  const [shared, setShared] = useState(report?.shared_encounter_id || "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setShared(report?.shared_encounter_id || "");
    setSelected("");
  }, [report?.report_id, report?.shared_encounter_id]);

  useEffect(() => {
    api.get("/encounters")
      .then(({ data }) => {
        const now = Date.now();
        setVisits(data.filter((e) => ["scheduled", "in_progress"].includes(e.status) &&
          new Date(e.scheduled_at).getTime() > now - 86400000));
      })
      .catch(() => {});
  }, []);

  const share = async () => {
    setSaving(true);
    try {
      await api.put(`/reports/${report.report_id}/share`, { encounter_id: selected });
      setShared(selected);
      toast.success("Your doctor will see this screening for that visit.");
    } catch {
      toast.error("Could not share this screening");
    } finally {
      setSaving(false);
    }
  };

  if (visits.length === 0) return null;

  if (shared) {
    const v = visits.find((x) => x.encounter_id === shared);
    return (
      <div className="card p-4 flex items-center gap-3" data-testid="screening-shared-confirmation">
        <Check className="h-4 w-4 text-forest" />
        <p className="text-sm text-ink-soft">
          Shared with {v?.doctor_name || "your doctor"} for the visit on{" "}
          {v ? new Date(v.scheduled_at).toLocaleDateString() : "your next appointment"}.
        </p>
      </div>
    );
  }

  return (
    <div className="card p-4 space-y-3" data-testid="share-screening-card">
      <p className="text-sm font-medium flex items-center gap-2">
        <Share2 className="h-4 w-4 text-forest" /> Share this screening with your doctor
      </p>
      <p className="text-xs text-ink-soft">
        Pick the visit it relates to and your doctor will read it before you arrive.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <select value={selected} onChange={(e) => setSelected(e.target.value)} data-testid="share-visit-select"
          className="border border-line rounded-lg px-3 py-2 text-sm bg-white">
          <option value="">Choose a visit…</option>
          {visits.map((v) => (
            <option key={v.encounter_id} value={v.encounter_id}>
              {new Date(v.scheduled_at).toLocaleDateString()} — {v.doctor_name}
              {v.reason_for_visit ? ` · ${v.reason_for_visit}` : ""}
            </option>
          ))}
        </select>
        <button onClick={share} disabled={!selected || saving} data-testid="share-screening-btn" className="btn-primary">
          {saving ? "Sharing…" : "Share"}
        </button>
      </div>
    </div>
  );
}
