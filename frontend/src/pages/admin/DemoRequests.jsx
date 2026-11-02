import React, { useEffect, useState } from "react";
import { Bell, Save, Inbox } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { inputCls, labelCls, errorText } from "../../components/admin/ui";

const STATUSES = [
  ["new", "New", "bg-sky-50 text-sky-700 border-sky-200"],
  ["contacted", "Contacted", "bg-amber-50 text-amber-700 border-amber-200"],
  ["demo_booked", "Demo booked", "bg-violet-50 text-violet-700 border-violet-200"],
  ["won", "Won", "bg-emerald-50 text-emerald-700 border-emerald-200"],
  ["lost", "Lost", "bg-red-50 text-red-700 border-red-200"],
];

export default function DemoRequests() {
  const [items, setItems] = useState(null);
  const [filter, setFilter] = useState("");
  const [alertEmail, setAlertEmail] = useState("");

  useEffect(() => {
    api.get("/admin/demo-requests").then(({ data }) => setItems(data)).catch(() => setItems([]));
    api.get("/admin/settings/demo-alert").then(({ data }) => setAlertEmail(data.email || "")).catch(() => {});
  }, []);

  const update = async (id, patch) => {
    try {
      const { data } = await api.patch(`/admin/demo-requests/${id}`, patch);
      setItems((list) => list.map((r) => (r.request_id === id ? data : r)));
      toast.success("Saved");
    } catch (e) {
      toast.error(errorText(e));
    }
  };

  const saveAlert = async () => {
    try {
      const { data } = await api.put("/admin/settings/demo-alert", { email: alertEmail || null });
      toast.success(data.email ? `Alerts go to ${data.email}` : "Email alerts turned off");
    } catch (e) {
      toast.error(errorText(e));
    }
  };

  if (!items) return <p className="text-sm text-ink-soft">Loading…</p>;
  const counts = Object.fromEntries(STATUSES.map(([k]) => [k, items.filter((r) => (r.status || "new") === k).length]));
  const shown = items.filter((r) => !filter || (r.status || "new") === filter);

  return (
    <div className="fade-up" data-testid="demo-requests-page">
      <div className="flex flex-wrap items-end gap-4 mb-8">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight mr-auto">Demo requests</h1>
        <div className="flex items-end gap-2" data-testid="demo-alert-settings">
          <div>
            <label className={labelCls}><Bell className="inline h-3 w-3 mr-1" />Email me new requests</label>
            <input type="email" value={alertEmail} onChange={(e) => setAlertEmail(e.target.value)} placeholder="you@company.com" data-testid="demo-alert-email-input" className={`${inputCls} w-64`} />
          </div>
          <button onClick={saveAlert} data-testid="demo-alert-save-btn" className="btn-outline"><Save className="h-4 w-4" /> Save</button>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 mb-5">
        <button onClick={() => setFilter("")} data-testid="demo-filter-all" className={`px-3 py-1.5 rounded-full text-xs font-semibold border ${!filter ? "bg-ink text-white border-ink" : "bg-white border-line"}`}>All · {items.length}</button>
        {STATUSES.map(([k, label]) => (
          <button key={k} onClick={() => setFilter(k)} data-testid={`demo-filter-${k}`} className={`px-3 py-1.5 rounded-full text-xs font-semibold border ${filter === k ? "bg-ink text-white border-ink" : "bg-white border-line"}`}>{label} · {counts[k]}</button>
        ))}
      </div>
      {shown.length === 0 && (
        <div className="card p-12 text-center text-sm text-ink-soft" data-testid="demo-requests-empty"><Inbox className="h-8 w-8 mx-auto mb-3 text-line" />No requests here yet.</div>
      )}
      <div className="space-y-3">
        {shown.map((r) => <RequestRow key={r.request_id} r={r} onUpdate={update} />)}
      </div>
    </div>
  );
}

function RequestRow({ r, onUpdate }) {
  const [notes, setNotes] = useState(r.notes || "");
  const status = STATUSES.find(([k]) => k === (r.status || "new"));
  return (
    <div className="card p-5 grid grid-cols-1 lg:grid-cols-12 gap-4" data-testid={`demo-request-${r.request_id}`}>
      <div className="lg:col-span-4 min-w-0">
        <div className="flex items-center gap-2">
          <p className="font-semibold truncate">{r.organization}</p>
          <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-md border ${status[2]}`} data-testid={`demo-status-badge-${r.request_id}`}>{status[1]}</span>
        </div>
        <p className="text-sm mt-1">{r.name}{r.role ? ` · ${r.role}` : ""}</p>
        <a href={`mailto:${r.email}`} className="text-sm text-forest underline" data-no-translate>{r.email}</a>
        <p className="text-xs text-ink-soft mt-1">{new Date(r.created_at).toLocaleString()}</p>
      </div>
      <p className="lg:col-span-3 text-sm text-ink-soft whitespace-pre-wrap">{r.message || "—"}</p>
      <div className="lg:col-span-5 flex flex-col gap-2">
        <select value={r.status || "new"} onChange={(e) => onUpdate(r.request_id, { status: e.target.value })} data-testid={`demo-status-select-${r.request_id}`} className={inputCls}>
          {STATUSES.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
        </select>
        <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Notes — call outcome, next step…" data-testid={`demo-notes-${r.request_id}`} className={inputCls} />
        {notes !== (r.notes || "") && (
          <button onClick={() => onUpdate(r.request_id, { notes })} data-testid={`demo-notes-save-${r.request_id}`} className="btn-primary self-start"><Save className="h-4 w-4" /> Save notes</button>
        )}
      </div>
    </div>
  );
}
