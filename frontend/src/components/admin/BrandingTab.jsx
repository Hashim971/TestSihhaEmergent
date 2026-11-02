import React, { useState } from "react";
import { Upload, ExternalLink, Save, Leaf } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { inputCls, labelCls, errorText } from "./ui";

const API_ORIGIN = process.env.REACT_APP_BACKEND_URL;

export function BrandingTab({ account, onSaved }) {
  const b = account.branding || {};
  const [form, setForm] = useState({ display_name: b.display_name || account.name, primary_color: b.primary_color || "#1E3F2A", accent_color: b.accent_color || "#B1D8B7" });
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      onSaved((await api.patch(`/admin/accounts/${account.account_id}/branding`, form)).data);
      toast.success("Branding saved");
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setSaving(false);
    }
  };

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    setUploading(true);
    try {
      onSaved((await api.post(`/admin/accounts/${account.account_id}/logo`, body)).data);
      toast.success("Logo uploaded");
    } catch (err) {
      toast.error(errorText(err, "Upload failed"));
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const logo = account.logo_url ? `${API_ORIGIN}${account.logo_url}?v=${account.updated_at || ""}` : null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" data-testid="account-branding-tab">
      <div className="card p-6 space-y-5">
        <div><label className={labelCls}>Name patients see</label>
          <input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} data-testid="branding-name-input" className={inputCls} /></div>
        <div className="grid grid-cols-2 gap-4">
          {[["primary_color", "Main colour"], ["accent_color", "Accent colour"]].map(([k, label]) => (
            <div key={k}><label className={labelCls}>{label}</label>
              <div className="flex items-center gap-2">
                <input type="color" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value.toUpperCase() })} data-testid={`branding-${k}-picker`} className="h-10 w-12 rounded border border-line cursor-pointer" />
                <input value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} data-testid={`branding-${k}-input`} className={`${inputCls} font-mono`} />
              </div></div>
          ))}
        </div>
        <div><label className={labelCls}>Logo</label>
          <label className="flex items-center gap-3 border border-dashed border-line rounded-lg p-4 cursor-pointer hover:bg-sand" data-testid="branding-logo-dropzone">
            {logo ? <img src={logo} alt="Logo" className="h-12 w-12 object-contain rounded bg-white border border-line" data-testid="branding-logo-preview" /> : <Upload className="h-5 w-5 text-ink-soft" />}
            <span className="text-sm text-ink-soft">{uploading ? "Uploading…" : "PNG, JPG, WEBP or SVG · under 2 MB"}</span>
            <input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" onChange={upload} className="hidden" data-testid="branding-logo-input" />
          </label></div>
        <div className="flex flex-wrap gap-3">
          <button onClick={save} disabled={saving} data-testid="branding-save-btn" className="btn-primary"><Save className="h-4 w-4" /> {saving ? "Saving…" : "Save branding"}</button>
          <a href={`/auth?tenant=${account.account_id}`} target="_blank" rel="noreferrer" data-testid="branding-preview-link" className="btn-outline">
            <ExternalLink className="h-4 w-4" /> Preview patient sign-in
          </a>
        </div>
        {!account.effective_flags?.white_label && (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-3" data-testid="branding-flag-off-note">
            White-label is switched off for this account, so patients still see Sihha AI. Turn it on in the Features tab.
          </p>
        )}
      </div>
      <div className="card p-6" data-testid="branding-live-preview">
        <p className={labelCls}>Live preview</p>
        <div className="rounded-xl border border-line overflow-hidden mt-2" style={{ background: "#FBFBF9" }}>
          <div className="flex items-center gap-2 px-4 py-3 bg-white border-b border-line">
            {logo ? <img src={logo} alt="" className="h-8 w-8 rounded-full object-contain border border-line" /> : (
              <span className="h-8 w-8 rounded-full flex items-center justify-center" style={{ background: form.primary_color }}><Leaf className="h-4 w-4" style={{ color: form.accent_color }} /></span>
            )}
            <span className="font-heading font-bold" style={{ color: form.primary_color }}>{form.display_name}</span>
          </div>
          <div className="p-5 space-y-3">
            <p className="text-lg font-semibold">Good morning, Omar</p>
            <div className="rounded-lg p-4 text-white text-sm" style={{ background: form.primary_color }}>Your next visit is tomorrow at 10:00</div>
            <div className="flex gap-2">
              <span className="rounded-full px-4 py-2 text-sm font-medium text-white" style={{ background: form.primary_color }}>Book a visit</span>
              <span className="rounded-full px-4 py-2 text-sm font-medium" style={{ background: form.accent_color, color: form.primary_color }}>Health chat</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
