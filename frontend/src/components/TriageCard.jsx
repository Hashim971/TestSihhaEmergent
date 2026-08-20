import React from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, PhoneCall, CalendarPlus, ShieldCheck, Eye } from "lucide-react";

const STYLE = {
  emergency_now: { border: "border-terracotta", bg: "bg-terracotta/5", text: "text-terracotta" },
  urgent_24h: { border: "border-terracotta/60", bg: "bg-terracotta/5", text: "text-terracotta" },
  routine_2w: { border: "border-line", bg: "bg-sand", text: "text-forest" },
  self_care: { border: "border-line", bg: "bg-sand", text: "text-forest" },
};

export function TriageCard({ report, onRetriage }) {
  const navigate = useNavigate();
  const d = report?.disposition;

  if (!d) {
    return (
      <div className="card p-4 flex flex-wrap items-center justify-between gap-3" data-testid="triage-pending">
        <p className="text-sm text-ink-soft">
          This screening has not been checked for urgency yet.
        </p>
        {onRetriage && (
          <button onClick={onRetriage} className="btn-outline !py-1.5 !px-3 text-xs" data-testid="run-triage-btn">
            Check how soon I should be seen
          </button>
        )}
      </div>
    );
  }

  const style = STYLE[d.level] || STYLE.routine_2w;
  const emergency = d.level === "emergency_now";
  const urgent = d.level === "urgent_24h";

  return (
    <div className={`card p-6 border ${style.border} ${style.bg}`} data-testid="triage-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className={`text-[10px] uppercase tracking-[0.2em] font-semibold ${style.text}`}
            data-testid="triage-level">
            {d.timeframe}
          </p>
          <h3 className="text-lg font-semibold mt-1 max-w-2xl" data-testid="triage-headline">{d.headline}</h3>
        </div>
        {emergency ? (
          <a href={`tel:${d.emergency_number}`} data-testid="triage-emergency-call"
            className="btn-primary !bg-terracotta !border-terracotta">
            <PhoneCall className="h-4 w-4" /> Call {d.emergency_number}
          </a>
        ) : (
          <button
            onClick={() => navigate(`/book?report=${report.report_id}` +
              `&specialty=${encodeURIComponent(d.recommended_specialty || "")}` +
              `&reason=${encodeURIComponent(d.suggested_reason_for_visit || "")}`)}
            data-testid="triage-book-btn" className="btn-primary">
            <CalendarPlus className="h-4 w-4" /> Book a visit
          </button>
        )}
      </div>

      {(d.reasons || []).length > 0 && (
        <ul className="mt-4 space-y-1.5" data-testid="triage-reasons">
          {d.reasons.map((r, i) => (
            <li key={i} className="text-sm flex gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-forest shrink-0" />
              <span>{r.text}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        {(d.watch_for || []).length > 0 && (
          <div className="border border-terracotta/40 rounded-xl px-4 py-3 bg-white/60">
            <p className="text-xs font-semibold text-terracotta flex items-center gap-1.5 mb-2">
              <AlertTriangle className="h-3.5 w-3.5" /> Seek care right away if
            </p>
            <ul className="text-sm space-y-1" data-testid="triage-watch-for">
              {d.watch_for.map((w, i) => <li key={i}>• {w}</li>)}
            </ul>
          </div>
        )}
        {(d.self_care_advice || []).length > 0 && (
          <div className="border border-line rounded-xl px-4 py-3 bg-white/60">
            <p className="text-xs font-semibold text-forest mb-2">Until then</p>
            <ul className="text-sm space-y-1" data-testid="triage-self-care">
              {d.self_care_advice.map((a, i) => <li key={i}>• {a}</li>)}
            </ul>
          </div>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-ink-soft">
        {d.recommended_specialty && (
          <span data-testid="triage-specialty">Suggested: {d.recommended_specialty}</span>
        )}
        {d.escalated_by_rules && (
          <span className="flex items-center gap-1 text-terracotta" data-testid="triage-escalated">
            <ShieldCheck className="h-3.5 w-3.5" /> Urgency raised by Sihha's safety rules
          </span>
        )}
        {(d.red_flags || []).length > 0 && (
          <span className="flex items-center gap-1" data-testid="triage-red-flag-count">
            <Eye className="h-3.5 w-3.5" /> {d.red_flags.length} safety flag(s) detected
          </span>
        )}
        <span>This is not a diagnosis. It only tells you how soon to be seen.</span>
      </div>

      {(emergency || urgent) && (
        <p className="text-xs mt-3 text-terracotta" data-testid="triage-urgent-note">
          {emergency
            ? "Booking is disabled for this screening on purpose — this cannot wait for an appointment."
            : "Your doctor has been alerted. If you cannot get seen today, call the clinic."}
        </p>
      )}
    </div>
  );
}
