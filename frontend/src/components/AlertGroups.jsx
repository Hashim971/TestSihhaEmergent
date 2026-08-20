import React, { useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Bell, CheckCheck } from "lucide-react";

const LABELS = {
  intake: (n) => `${n} pre-visit intake${n === 1 ? "" : "s"} completed`,
  vitals: (n) => `${n} out-of-range vital reading${n === 1 ? "" : "s"}`,
  adherence: (n) => `${n} missed dose${n === 1 ? "" : "s"}`,
  medication: (n) => `${n} medication alert${n === 1 ? "" : "s"}`,
  triage: (n) => `${n} screening${n === 1 ? "" : "s"} needing attention`,
  appointment: (n) => `${n} appointment update${n === 1 ? "" : "s"}`,
};

export function AlertGroups({ groups, onCleared }) {
  const [open, setOpen] = useState(null);
  const [clearing, setClearing] = useState(null);

  const clearGroup = async (group) => {
    const key = `${group.type}-${group.severity}`;
    setClearing(key);
    try {
      const { data } = await api.post("/alerts/read-group", { type: group.type, severity: group.severity });
      toast.success(`Cleared ${data.cleared} alert${data.cleared === 1 ? "" : "s"}`);
      onCleared?.();
    } catch {
      toast.error("Could not clear that group");
    } finally {
      setClearing(null);
    }
  };

  return (
    <div className="card p-6" data-testid="dash-alerts">
      <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <Bell className="h-4 w-4 text-forest" /> Unread alerts
      </h2>
      {groups.length === 0 && <p className="text-sm text-ink-soft">Nothing new.</p>}
      <div className="space-y-2">
        {groups.map((g) => {
          const key = `${g.type}-${g.severity}`;
          const label = (LABELS[g.type] || ((n) => `${n} ${g.type} alert${n === 1 ? "" : "s"}`))(g.count);
          return (
            <div key={key} data-testid={`alert-group-${key}`}
              className={`border rounded-xl px-3 py-2.5 ${
                g.severity === "critical" ? "border-terracotta/40 bg-terracotta/5"
                  : g.severity === "warning" ? "border-terracotta/25 bg-terracotta/[0.03]"
                  : g.severity === "info" ? "border-sage/50 bg-sage/10" : "border-line"}`}>
              <div className="flex items-start justify-between gap-2">
                <button onClick={() => setOpen(open === key ? null : key)} data-testid={`alert-group-toggle-${key}`}
                  className="flex-1 text-left">
                  <span className={`text-[10px] uppercase tracking-wider font-bold ${
                    g.severity === "info" ? "text-forest" : "text-terracotta"}`}>
                    {g.type} · {g.severity}
                  </span>
                  <p className="text-sm font-medium mt-0.5">{label}</p>
                  <p className="text-xs text-ink-soft">
                    {g.patients.slice(0, 3).join(", ")}
                    {g.patients.length > 3 ? ` +${g.patients.length - 3} more` : ""}
                    {g.patients.length ? " · " : ""}
                    latest {new Date(g.latest_at).toLocaleDateString()}
                  </p>
                </button>
                <button onClick={() => clearGroup(g)} disabled={clearing === key}
                  data-testid={`alert-group-clear-${key}`}
                  className="text-[11px] font-semibold text-ink-soft hover:text-forest flex items-center gap-1 shrink-0 px-2 py-1 rounded-full hover:bg-white/70 transition-colors">
                  <CheckCheck className="h-3.5 w-3.5" /> {clearing === key ? "Clearing…" : "Clear all"}
                </button>
              </div>
              {open === key && (
                <div className="mt-2 space-y-1 border-l-2 border-line pl-3" data-testid={`alert-group-items-${key}`}>
                  {g.items.map((it) => (
                    <p key={it.alert_id} className="text-xs text-ink-soft">
                      {it.message}
                      <span className="block text-[10px]">
                        {new Date(it.created_at).toLocaleString()}
                      </span>
                    </p>
                  ))}
                  {g.count > g.items.length && (
                    <p className="text-[10px] text-ink-soft">+{g.count - g.items.length} more like this</p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
