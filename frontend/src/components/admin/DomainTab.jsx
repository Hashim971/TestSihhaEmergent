import React, { useState } from "react";
import { Globe, ShieldCheck, Save, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { inputCls, labelCls, errorText } from "./ui";

export function DomainTab({ account, onSaved }) {
  const [lang, setLang] = useState(account.default_language || "ar");
  const [domain, setDomain] = useState(account.custom_domain || "");
  const [saving, setSaving] = useState(false);
  const [check, setCheck] = useState(null);

  const save = async () => {
    setSaving(true);
    try {
      onSaved((await api.patch(`/admin/accounts/${account.account_id}/branding`, { default_language: lang, custom_domain: domain.trim() || null })).data);
      toast.success("Saved");
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setSaving(false);
    }
  };

  const verify = async () => {
    try {
      const { data } = await api.post(`/admin/accounts/${account.account_id}/domain/verify`);
      setCheck(data);
      const fresh = await api.get(`/admin/accounts/${account.account_id}`);
      onSaved(fresh.data);
    } catch (e) {
      toast.error(errorText(e));
    }
  };

  const appHost = window.location.hostname;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" data-testid="account-domain-tab">
      <div className="card p-6 space-y-5">
        <div>
          <p className={labelCls}>Default language</p>
          <div className="flex gap-2">
            {[["ar", "العربية · Arabic"], ["en", "English"]].map(([v, label]) => (
              <button key={v} onClick={() => setLang(v)} data-testid={`language-option-${v}`}
                className={`flex-1 rounded-lg border px-4 py-3 text-sm font-medium ${lang === v ? "border-forest bg-forest text-white" : "border-line bg-white hover:bg-sand"}`}>{label}</button>
            ))}
          </div>
          <p className="text-xs text-ink-soft mt-2">Used first for AI visit summaries and patient-facing text for this hospital.</p>
        </div>
        <div>
          <label className={labelCls}>Hospital web address</label>
          <div className="relative">
            <Globe className="h-4 w-4 text-ink-soft absolute left-3 top-1/2 -translate-y-1/2" />
            <input value={domain} onChange={(e) => setDomain(e.target.value.toLowerCase())} placeholder="care.yourhospital.sa" data-testid="domain-input" className={`${inputCls} pl-9 font-mono`} />
          </div>
        </div>
        <button onClick={save} disabled={saving} data-testid="domain-save-btn" className="btn-primary"><Save className="h-4 w-4" /> {saving ? "Saving…" : "Save"}</button>
      </div>
      <div className="card p-6 space-y-4" data-testid="domain-instructions">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Connect the address</h3>
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-md border ${account.domain_verified ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-amber-50 text-amber-700 border-amber-200"}`} data-testid="domain-status">
            {account.domain_verified ? "Connected" : "Not connected"}
          </span>
        </div>
        <ol className="text-sm text-ink-soft space-y-2 list-decimal pl-5">
          <li>The hospital's IT team adds this record at their domain provider:</li>
        </ol>
        <div className="font-mono text-xs bg-sand border border-line rounded-md p-3 overflow-x-auto">
          <div>Type: CNAME</div><div>Name: {account.custom_domain || "care.yourhospital.sa"}</div><div>Value: {appHost}</div>
        </div>
        <ol start={2} className="text-sm text-ink-soft space-y-2 list-decimal pl-5">
          <li>The address is also linked to the live deployment (custom domain setting), which issues the HTTPS certificate.</li>
          <li>Press “Check connection”. When it passes, patients visiting that address see this hospital's branding.</li>
        </ol>
        <button onClick={verify} disabled={!account.custom_domain} data-testid="domain-verify-btn" className="btn-outline"><RefreshCw className="h-4 w-4" /> Check connection</button>
        {check && (
          <p className={`text-xs flex items-center gap-2 ${check.verified ? "text-forest" : "text-terracotta"}`} data-testid="domain-check-result">
            <ShieldCheck className="h-4 w-4" />
            {check.verified ? `${check.domain} points to ${check.points_to}.` : check.resolves ? `${check.domain} doesn't point to ${check.points_to} yet.` : `${check.domain} can't be found yet. DNS changes can take up to a few hours.`}
          </p>
        )}
      </div>
    </div>
  );
}
