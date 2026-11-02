import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Store, UserPlus, Check, X, Megaphone, Trash2 } from "lucide-react";
import { api } from "../../lib/api";
import { StatusBadge, errorText } from "../../components/admin/ui";
import { ConfirmDialog } from "../../components/ConfirmDialog";

export default function AdminPharmacies() {
  const [apps, setApps] = useState([]);
  const [pharmacies, setPharmacies] = useState([]);
  const [requests, setRequests] = useState([]);
  const [dialog, setDialog] = useState(null);

  const load = useCallback(() => Promise.all([
    api.get("/admin/pharmacy-applications").then(({ data }) => setApps(data)),
    api.get("/admin/pharmacies").then(({ data }) => setPharmacies(data)),
    api.get("/admin/sponsorship-requests").then(({ data }) => setRequests(data)),
  ]).catch(() => toast.error("Could not load pharmacies")), []);
  useEffect(() => { load(); }, [load]);

  const act = async (fn, ok) => {
    try { await fn(); toast.success(ok); load(); } catch (e) { toast.error(errorText(e)); }
  };

  return (
    <div className="space-y-8 fade-up" data-testid="admin-pharmacies-page">
      {dialog && <ConfirmDialog {...dialog} onClose={() => setDialog(null)} />}
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-3"><Store className="h-7 w-7 text-forest" /> Pharmacies</h1>
        <p className="text-ink-soft mt-1">Approve new pharmacies, invite their staff and switch on paid sponsorships.</p>
      </div>

      <Section title="Applications waiting for approval" count={apps.length} testid="pharmacy-applications">
        {apps.length === 0 && <Empty>No pending applications.</Empty>}
        {apps.map((a) => (
          <div key={a.application_id} className="py-3 flex flex-wrap items-center gap-3" data-testid={`application-${a.application_id}`}>
            <div className="min-w-0 flex-1">
              <p className="font-semibold">{a.pharmacy_name} <span className="text-xs text-ink-soft font-normal">· {a.city}</span></p>
              <p className="text-xs text-ink-soft">{a.contact_name} · {a.email}{a.phone ? ` · ${a.phone}` : ""} · SFDA {a.sfda_license}</p>
            </div>
            <button onClick={() => act(() => api.post(`/admin/pharmacy-applications/${a.application_id}/approve`), `${a.pharmacy_name} approved`)} className="btn-primary !py-1.5 !px-3 text-xs" data-testid={`approve-application-${a.application_id}`}><Check className="h-3.5 w-3.5" /> Approve</button>
            <button onClick={() => setDialog({ title: `Reject ${a.pharmacy_name}?`, text: "The reason is shown to the pharmacy.", input: "Reason", confirmLabel: "Reject", danger: true, testid: "reject-application-dialog",
              onConfirm: (reason) => act(() => api.post(`/admin/pharmacy-applications/${a.application_id}/reject`, { reason }), "Application rejected") })}
              className="btn-outline !py-1.5 !px-3 text-xs !text-terracotta !border-terracotta" data-testid={`reject-application-${a.application_id}`}><X className="h-3.5 w-3.5" /> Reject</button>
          </div>
        ))}
      </Section>

      <Section title="Sponsorships waiting for payment" count={requests.length} icon={Megaphone} testid="sponsorship-requests">
        <p className="text-xs text-ink-soft pb-2">No payment provider is connected yet. Mark a request paid once the invoice is settled — the placement starts straight away.</p>
        {requests.length === 0 && <Empty>Nothing waiting.</Empty>}
        {requests.map((r) => (
          <div key={r.request_id} className="py-3 flex flex-wrap items-center gap-3 text-sm" data-testid={`admin-sponsor-request-${r.request_id}`}>
            <span className="font-mono text-xs">{r.reference}</span>
            <span className="font-semibold">{r.pharmacy_name}</span>
            <span>{r.tier_label} · {r.amount_sar.toLocaleString()} SAR</span>
            <span className="text-xs text-ink-soft">by {r.requested_by_name}</span>
            <span className="ms-auto flex gap-2">
              <button onClick={() => setDialog({ title: `Mark ${r.reference} as paid?`, text: `${r.pharmacy_name} · ${r.tier_label} · ${r.amount_sar.toLocaleString()} SAR. The placement starts straight away.`, input: "Payment reference (optional)", confirmLabel: "Mark paid", testid: "mark-paid-dialog",
                onConfirm: (reference) => act(() => api.post(`/admin/sponsorship-requests/${r.request_id}/mark-paid`, { reference }), "Sponsorship is live") })}
                className="btn-primary !py-1.5 !px-3 text-xs" data-testid={`mark-paid-${r.request_id}`}>Mark paid</button>
              <button onClick={() => act(() => api.post(`/admin/sponsorship-requests/${r.request_id}/decline`, { reason: "" }), "Request declined")}
                className="btn-outline !py-1.5 !px-3 text-xs" data-testid={`decline-sponsor-${r.request_id}`}>Decline</button>
            </span>
          </div>
        ))}
      </Section>

      <Section title="Partner pharmacies" count={pharmacies.length} testid="partner-pharmacies">
        {pharmacies.map((p) => <PharmacyRow key={p.pharmacy_id} p={p} act={act} setDialog={setDialog} />)}
      </Section>
    </div>
  );
}

function PharmacyRow({ p, act, setDialog }) {
  const [form, setForm] = useState({ name: "", email: "" });
  const invite = (e) => {
    e.preventDefault();
    act(() => api.post(`/admin/pharmacies/${p.pharmacy_id}/staff`, form), `Invite sent to ${form.email}`).then(() => setForm({ name: "", email: "" }));
  };
  const sp = p.sponsorship || {};
  return (
    <div className="py-4" data-testid={`admin-pharmacy-${p.pharmacy_id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-semibold">{p.name_en}</p>
        <span className="text-xs text-ink-soft">{p.fulfilment_mode === "in_app" ? "Orders in app" : "Hands off to its own site"}</span>
        {p.sponsored && <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md border bg-emerald-50 text-emerald-700 border-emerald-200 capitalize" data-testid={`admin-pharmacy-sponsor-${p.pharmacy_id}`}>{sp.tier} · {sp.active_until ? `until ${new Date(sp.active_until).toLocaleDateString()}` : "no end date"}</span>}
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        {p.staff.length === 0 && <span className="text-xs text-ink-soft">No staff accounts yet.</span>}
        {p.staff.map((s) => (
          <span key={s.user_id} className="inline-flex items-center gap-2 text-xs border border-line rounded-full ps-3 pe-1 py-1 bg-white">
            {s.name} · {s.email} <StatusBadge status={s.status} />
            <button onClick={() => setDialog({ title: `Remove ${s.name}?`, text: "They lose access to this pharmacy's orders.", confirmLabel: "Remove", danger: true, testid: "remove-staff-dialog",
              onConfirm: () => act(() => api.delete(`/admin/pharmacies/${p.pharmacy_id}/staff/${s.user_id}`), "Removed") })} className="p-1 rounded-full hover:bg-sand" data-testid={`remove-staff-${s.user_id}`}><Trash2 className="h-3 w-3 text-ink-soft" /></button>
          </span>
        ))}
      </div>
      <form onSubmit={invite} className="mt-3 flex flex-wrap gap-2">
        <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Staff name" className="border border-line rounded-md px-3 py-1.5 text-sm" data-testid={`invite-name-${p.pharmacy_id}`} />
        <input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="Email" className="border border-line rounded-md px-3 py-1.5 text-sm" data-testid={`invite-email-${p.pharmacy_id}`} />
        <button type="submit" className="btn-outline !py-1.5 !px-3 text-xs" data-testid={`invite-staff-${p.pharmacy_id}`}><UserPlus className="h-3.5 w-3.5" /> Invite</button>
      </form>
    </div>
  );
}

const Section = ({ title, count, children, testid, icon: Icon = Store }) => (
  <div className="card p-6" data-testid={testid}>
    <h2 className="text-lg font-semibold flex items-center gap-2"><Icon className="h-4 w-4 text-forest" /> {title} <span className="text-xs text-ink-soft font-normal">({count})</span></h2>
    <div className="divide-y divide-line mt-2">{children}</div>
  </div>
);
const Empty = ({ children }) => <p className="text-sm text-ink-soft py-3">{children}</p>;
