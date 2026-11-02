import React, { useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

export function Modal({ children, onClose, testid }) {
  return createPortal(
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4" data-testid={testid}
      onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="card p-6 max-w-md w-full max-h-[90vh] overflow-y-auto fade-up relative">
        <button onClick={onClose} className="absolute top-4 end-4 p-1.5 rounded-full hover:bg-sand" data-testid={`${testid}-close`}><X className="h-4 w-4" /></button>
        {children}
      </div>
    </div>,
    document.body,
  );
}

// Replaces window.confirm / window.prompt. With `input`, onConfirm receives the typed text.
export function ConfirmDialog({ title, text, input, confirmLabel = "Confirm", danger, onConfirm, onClose, testid = "confirm-dialog" }) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try { await onConfirm(value); onClose(); } finally { setBusy(false); }
  };
  return (
    <Modal onClose={onClose} testid={testid}>
      <h2 className="text-lg font-semibold pe-8">{title}</h2>
      {text && <p className="text-sm text-ink-soft mt-2">{text}</p>}
      {input && (
        <input autoFocus value={value} onChange={(e) => setValue(e.target.value)} placeholder={input} maxLength={500}
          className="mt-4 w-full border border-line rounded-lg px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-forest" data-testid={`${testid}-input`} />
      )}
      <div className="flex justify-end gap-2 mt-5">
        <button onClick={onClose} className="btn-outline !py-2 !px-4 text-sm" data-testid={`${testid}-cancel`}>Cancel</button>
        <button onClick={go} disabled={busy} data-testid={`${testid}-confirm`}
          className={`btn-primary !py-2 !px-4 text-sm disabled:opacity-50 ${danger ? "!bg-terracotta !border-terracotta" : ""}`}>{busy ? "Please wait…" : confirmLabel}</button>
      </div>
    </Modal>
  );
}
