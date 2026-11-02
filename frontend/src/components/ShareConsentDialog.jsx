import React, { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { Modal } from "./ConfirmDialog";

export function ShareConsentDialog({ doctor, slot, hospitalName, busy, onConfirm, onClose }) {
  const [share, setShare] = useState(null);
  return (
    <Modal onClose={onClose} testid="share-consent-dialog">
      <p className="text-[10px] uppercase tracking-[0.2em] text-ink-soft">Confirm your visit</p>
      <h2 className="text-lg font-semibold mt-1 pe-8"><bdi>{doctor.name}</bdi> · <bdi>{slot.label}</bdi></h2>
      {hospitalName && <p className="text-xs text-ink-soft mt-0.5">{hospitalName}</p>}
      <div className="text-sm mt-4 flex gap-2"><ShieldCheck className="h-4 w-4 text-forest shrink-0 mt-0.5" />
        <div><p>Share your health record with this doctor before the visit?</p>
          <p className="text-xs text-ink-soft mt-0.5">Your record includes vitals, medications and screening reports.</p></div></div>
      <div className="mt-4 space-y-2">
        <Choice active={share === true} onClick={() => setShare(true)} testid="share-record-yes" title="Yes, share my record"
          text={hospitalName ? "This hospital becomes your hospital. Doctors at any other hospital lose access." : "This doctor can read your record for this visit."} />
        <Choice active={share === false} onClick={() => setShare(false)} testid="share-record-no" title="No, just book the time"
          text="The doctor only sees your name, the time and the reason for the visit." />
      </div>
      <button disabled={share === null || busy} onClick={() => onConfirm(share)} data-testid="confirm-booking-btn"
        className="btn-primary w-full justify-center mt-5 disabled:opacity-50">{busy ? "Booking…" : "Confirm booking"}</button>
    </Modal>
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
