import React, { useState } from "react";
import { ShieldCheck, X } from "lucide-react";

export function ShareConsentDialog({ doctor, slot, hospitalName, busy, onConfirm, onClose }) {
  const [share, setShare] = useState(null);
  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4" data-testid="share-consent-dialog">
      <div className="card p-6 max-w-md w-full fade-up">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-ink-soft">Confirm your visit</p>
            <h2 className="text-lg font-semibold mt-1">{doctor.name} · {slot.label}</h2>
            {hospitalName && <p className="text-xs text-ink-soft mt-0.5">{hospitalName}</p>}
          </div>
          <button onClick={onClose} className="p-1.5 rounded-full hover:bg-sand" data-testid="share-consent-close"><X className="h-4 w-4" /></button>
        </div>
        <p className="text-sm mt-4 flex gap-2"><ShieldCheck className="h-4 w-4 text-forest shrink-0 mt-0.5" />
          Do you want {doctor.name} to see your health record — vitals, medications and screening reports — before the visit?</p>
        <div className="mt-4 space-y-2">
          <Choice active={share === true} onClick={() => setShare(true)} testid="share-record-yes" title="Yes, share my record"
            text={hospitalName ? `${hospitalName} becomes your hospital. Doctors at any other hospital lose access.` : "This doctor can read your record for this visit."} />
          <Choice active={share === false} onClick={() => setShare(false)} testid="share-record-no" title="No, just book the time"
            text="The doctor only sees your name, the time and the reason for the visit." />
        </div>
        <button disabled={share === null || busy} onClick={() => onConfirm(share)} data-testid="confirm-booking-btn"
          className="btn-primary w-full justify-center mt-5 disabled:opacity-50">{busy ? "Booking…" : "Confirm booking"}</button>
      </div>
    </div>
  );
}

const Choice = ({ active, onClick, title, text, testid }) => (
  <button onClick={onClick} data-testid={testid}
    className={`w-full text-start rounded-xl border px-4 py-3 ${active ? "border-forest bg-forest/5 ring-1 ring-forest" : "border-line hover:bg-sand"}`}
    style={{ transition: "background-color 0.2s ease" }}>
    <p className="text-sm font-semibold">{title}</p>
    <p className="text-xs text-ink-soft mt-0.5">{text}</p>
  </button>
);
