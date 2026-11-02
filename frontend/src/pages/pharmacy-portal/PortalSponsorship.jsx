import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Megaphone, Check, Eye, ShoppingBag, CalendarClock, AlertTriangle } from "lucide-react";
import { api } from "../../lib/api";

const STATUS = {
  awaiting_payment: "bg-amber-50 text-amber-700 border-amber-200",
  paid: "bg-emerald-50 text-emerald-700 border-emerald-200",
  declined: "bg-red-50 text-red-700 border-red-200",
  cancelled: "bg-sand text-ink-soft border-line",
};

export default function PortalSponsorship() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => api.get("/pharmacy-portal/sponsorship").then(({ data: d }) => setData(d)), []);
  useEffect(() => { load(); }, [load]);

  const act = async (fn, ok) => {
    setBusy(true);
    try { await fn(); toast.success(ok); load(); } catch (e) { toast.error(e?.response?.data?.detail || "Something went wrong"); } finally { setBusy(false); }
  };

  if (!data) return <p className="text-sm text-ink-soft">Loading…</p>;
  const open = data.requests.find((r) => r.status === "awaiting_payment");
  const cur = data.current;

  return (
    <div className="space-y-8 fade-up" data-testid="portal-sponsorship-page">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3"><Megaphone className="h-7 w-7 text-forest" /> Sponsored placement</h1>
        <p className="text-ink-soft mt-1">Sponsored pharmacies appear first in the marketplace for {data.tiers[0].days} days per purchase.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Stat icon={CalendarClock} label="Current plan" testid="sponsor-current"
          value={cur.active ? `${cur.tier[0].toUpperCase()}${cur.tier.slice(1)}` : "Not sponsored"}
          sub={cur.active && cur.active_until ? `Until ${new Date(cur.active_until).toLocaleDateString()}` : "Pick a plan below"} />
        <Stat icon={Eye} label="Times shown as sponsored" value={data.stats.impressions} testid="sponsor-impressions" />
        <Stat icon={ShoppingBag} label="Orders, last 30 days" value={data.stats.orders_30d} testid="sponsor-orders" />
      </div>

      {!data.payment_provider_connected && (
        <div className="card p-4 border-amber-200 bg-amber-50 text-sm flex gap-2" data-testid="sponsor-payment-notice">
          <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
          Online payment isn't connected yet. Pick a plan and our team sends you an invoice — your placement goes live as soon as it's paid.
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {data.tiers.map((t) => {
          const isCurrent = cur.active && cur.tier === t.key;
          return (
            <div key={t.key} className={`card p-6 flex flex-col ${t.key === "gold" ? "ring-2 ring-forest" : ""}`} data-testid={`sponsor-tier-${t.key}`}>
              <p className="text-[10px] uppercase tracking-[0.2em] text-terracotta font-semibold">{t.label}</p>
              <p className="text-3xl font-bold mt-2">{t.price_sar.toLocaleString()} <span className="text-sm font-medium text-ink-soft">SAR / {t.days} days</span></p>
              <ul className="mt-4 space-y-2 text-sm flex-1">
                {t.perks.map((p) => <li key={p} className="flex gap-2"><Check className="h-4 w-4 text-forest shrink-0 mt-0.5" /> {p}</li>)}
              </ul>
              <button disabled={busy || !!open} onClick={() => act(() => api.post("/pharmacy-portal/sponsorship/requests", { tier: t.key }), `${t.label} requested — invoice on its way`)}
                className={`mt-5 justify-center ${t.key === "gold" ? "btn-primary" : "btn-outline"} disabled:opacity-50`} data-testid={`sponsor-buy-${t.key}`}>
                {isCurrent ? "Extend 30 days" : `Choose ${t.label}`}
              </button>
            </div>
          );
        })}
      </div>

      <div className="card p-6">
        <h2 className="text-lg font-semibold mb-3">Requests and invoices</h2>
        {data.requests.length === 0 && <p className="text-sm text-ink-soft" data-testid="sponsor-requests-empty">No requests yet.</p>}
        <div className="divide-y divide-line">
          {data.requests.map((r) => (
            <div key={r.request_id} className="py-3 flex flex-wrap items-center gap-3 text-sm" data-testid={`sponsor-request-${r.request_id}`}>
              <span className="font-mono text-xs">{r.reference}</span>
              <span className="font-medium">{r.tier_label}</span>
              <span className="text-ink-soft">{r.amount_sar.toLocaleString()} SAR</span>
              <span className="text-xs text-ink-soft">{new Date(r.created_at).toLocaleDateString()}</span>
              <span className={`ms-auto text-[11px] font-semibold px-2 py-0.5 rounded-md border ${STATUS[r.status]}`} data-testid={`sponsor-request-status-${r.request_id}`}>{r.status.replace("_", " ")}</span>
              {r.status === "awaiting_payment" && (
                <button disabled={busy} onClick={() => act(() => api.post(`/pharmacy-portal/sponsorship/requests/${r.request_id}/cancel`), "Request cancelled")}
                  className="text-xs text-terracotta underline" data-testid={`sponsor-cancel-${r.request_id}`}>Cancel</button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const Stat = ({ icon: Icon, label, value, sub, testid }) => (
  <div className="card p-5" data-testid={testid}>
    <p className="text-xs text-ink-soft flex items-center gap-1.5"><Icon className="h-3.5 w-3.5 text-forest" /> {label}</p>
    <p className="text-2xl font-bold mt-1">{value}</p>
    {sub && <p className="text-xs text-ink-soft mt-0.5">{sub}</p>}
  </div>
);
