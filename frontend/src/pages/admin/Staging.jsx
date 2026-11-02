import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { FlaskConical, ExternalLink, RotateCcw, KeyRound, Palette, ToggleRight, Copy } from "lucide-react";
import { api } from "../../lib/api";
import { ConfirmDialog } from "../../components/ConfirmDialog";

export default function AdminStaging() {
  const [data, setData] = useState(null);
  const [confirm, setConfirm] = useState(false);
  const load = () => api.get("/admin/staging").then(({ data: d }) => setData(d));
  useEffect(() => { load(); }, []);
  if (!data) return <p className="text-sm text-ink-soft">Loading…</p>;
  const origin = window.location.origin;
  const copy = (text) => navigator.clipboard?.writeText(text).then(() => toast.success("Copied"));

  return (
    <div className="space-y-8 fade-up" data-testid="admin-staging-page">
      {confirm && <ConfirmDialog title="Reset the demo hospital?" text="Dar Al Shifa's demo people, vitals, medicines, visits and ratings are rebuilt from scratch." confirmLabel="Reset" testid="reset-demo-dialog"
        onConfirm={async () => { await api.post("/admin/staging/reset-demo"); toast.success("Demo hospital reset"); load(); }} onClose={() => setConfirm(false)} />}
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-3"><FlaskConical className="h-7 w-7 text-forest" /> Staging</h1>
        <p className="text-ink-soft mt-1">Try changes here before your customers see them.</p>
      </div>

      <div className={`card p-6 ${data.is_staging ? "border-amber-300 bg-amber-50" : ""}`} data-testid="staging-env-card">
        <p className="text-xs uppercase tracking-[0.15em] text-ink-soft">You are on</p>
        <p className="text-2xl font-bold mt-1" data-testid="staging-env-name">{data.is_staging ? "Staging (preview)" : "Production (live)"}</p>
        <p className="text-sm text-ink-soft mt-2">
          {data.is_staging
            ? "This preview link is your staging copy. White-label pages, demo data and branding tests only work here. Your published app is production."
            : "This is the live app. White-label previews and demo resets are switched off here — open your preview link to use staging."}
        </p>
        <button onClick={() => copy(origin)} className="btn-outline !py-1.5 !px-3 text-xs mt-3" data-testid="copy-staging-url"><Copy className="h-3.5 w-3.5" /> <bdi>{origin}</bdi></button>
      </div>

      <div className="card p-6" data-testid="white-label-pages">
        <h2 className="text-lg font-semibold flex items-center gap-2"><Palette className="h-4 w-4 text-forest" /> White-label sign-in pages</h2>
        <div className="divide-y divide-line mt-2">
          {data.white_label_accounts.map((a) => (
            <div key={a.account_id} className="py-3 flex flex-wrap items-center gap-3" data-testid={`wl-account-${a.account_id}`}>
              <p className="font-semibold min-w-[160px]">{a.name}</p>
              {a.slug ? (
                <a href={`/h/${a.slug}`} target="_blank" rel="noreferrer" className="text-sm text-forest underline inline-flex items-center gap-1" data-testid={`wl-link-${a.account_id}`}>
                  <bdi>/h/{a.slug}</bdi> <ExternalLink className="h-3.5 w-3.5" />
                </a>
              ) : <span className="text-xs text-ink-soft">No sign-in address yet — set one in the account's Branding tab</span>}
              <Link to={`/admin/accounts/${a.account_id}`} className="ms-auto text-xs underline text-ink-soft" data-testid={`wl-branding-${a.account_id}`}>Branding</Link>
              {a.demo_logins.length > 0 && (
                <div className="w-full text-xs text-ink-soft flex flex-wrap gap-2">
                  {a.demo_logins.map((d) => <span key={d.email} className="border border-line rounded-full px-2.5 py-1 bg-white">{d.label}: <bdi>{d.email}</bdi> / <bdi>{d.password}</bdi></span>)}
                </div>
              )}
            </div>
          ))}
        </div>
        {data.is_staging && (
          <button onClick={() => setConfirm(true)} className="btn-outline !py-1.5 !px-3 text-xs mt-3" data-testid="reset-demo-btn"><RotateCcw className="h-3.5 w-3.5" /> Reset demo hospital data</button>
        )}
      </div>

      {data.test_logins.length > 0 && (
        <div className="card p-6" data-testid="staging-test-logins">
          <h2 className="text-lg font-semibold flex items-center gap-2"><KeyRound className="h-4 w-4 text-forest" /> Test logins</h2>
          <p className="text-xs text-ink-soft mt-1">Passwords are in the team's credentials note.</p>
          <div className="divide-y divide-line mt-2 text-sm">
            {data.test_logins.map((l) => (
              <div key={l.email} className="py-2 flex flex-wrap gap-3"><span className="font-medium min-w-[180px]">{l.label}</span><bdi className="text-ink-soft">{l.email}</bdi><span className="ms-auto text-xs font-mono">{l.where}</span></div>
            ))}
          </div>
        </div>
      )}

      <Link to="/admin/flags" className="card p-5 flex items-center gap-3 hover:shadow-md" style={{ transition: "box-shadow 0.2s ease" }} data-testid="staging-flags-link">
        <ToggleRight className="h-5 w-5 text-forest" />
        <div><p className="font-semibold">Feature switches</p><p className="text-xs text-ink-soft">Turn modules on or off per hospital and check the result here first.</p></div>
      </Link>
    </div>
  );
}
