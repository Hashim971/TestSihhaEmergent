import React, { useState } from "react";
import { createPortal } from "react-dom";
import { Copy, Check, X } from "lucide-react";
import { toast } from "sonner";

const STATUS_STYLES = {
  subscribed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  trial: "bg-amber-50 text-amber-700 border-amber-200",
  suspended: "bg-red-50 text-red-700 border-red-200",
  active: "bg-emerald-50 text-emerald-700 border-emerald-200",
  invited: "bg-amber-50 text-amber-700 border-amber-200",
};
const TYPE_LABELS = { hospital: "Hospital", clinic: "Clinic", pharmacy_group: "Pharmacy group" };

export const StatusBadge = ({ status, testid }) => (
  <span data-testid={testid} className={`text-[11px] font-semibold px-2 py-0.5 rounded-md border capitalize ${STATUS_STYLES[status] || "bg-sand border-line text-ink-soft"}`}>
    {status}
  </span>
);

export const TypeBadge = ({ type }) => (
  <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md border bg-violet-50 text-violet-700 border-violet-200">
    {TYPE_LABELS[type] || type}
  </span>
);

export function IdChip({ id, testid = "id-chip", large = false }) {
  const [copied, setCopied] = useState(false);
  const copy = async (e) => {
    e.stopPropagation();
    await navigator.clipboard?.writeText(id).catch(() => {});
    setCopied(true);
    toast.success(`Copied ${id}`);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button onClick={copy} data-testid={testid} title="Copy account ID"
      className={`inline-flex items-center gap-2 font-mono border border-line bg-white rounded-md hover:bg-sand ${large ? "px-3 py-2 text-sm" : "px-2 py-1 text-xs"}`}
      style={{ transition: "background-color 0.2s ease" }}>
      {id}
      {copied ? <Check className="h-3.5 w-3.5 text-forest" /> : <Copy className="h-3.5 w-3.5 text-ink-soft" />}
    </button>
  );
}

export function Toggle({ checked, onChange, testid, disabled }) {
  return (
    <button type="button" role="switch" aria-checked={checked} disabled={disabled} onClick={() => onChange(!checked)} data-testid={testid}
      className={`relative h-6 w-11 rounded-full shrink-0 disabled:opacity-40 ${checked ? "bg-forest" : "bg-line"}`}
      style={{ transition: "background-color 0.2s ease" }}>
      <span className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow ${checked ? "translate-x-5" : ""}`}
        style={{ transition: "transform 0.2s ease" }} />
    </button>
  );
}

export function Modal({ title, onClose, children, testid }) {
  return createPortal(
    <div className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div className="card w-full max-w-md p-6 fade-up max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid={testid}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button onClick={onClose} data-testid={`${testid}-close`} className="p-1.5 rounded-full hover:bg-sand"><X className="h-4 w-4" /></button>
        </div>
        {children}
      </div>
    </div>,
    document.body
  );
}

export const inputCls = "w-full border border-line rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-sage focus:border-forest";
export const labelCls = "block text-xs font-semibold uppercase tracking-wider text-ink-soft mb-1.5";

export const errorText = (e, fallback = "Something went wrong") => {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x.msg).join(" ");
  return fallback;
};
