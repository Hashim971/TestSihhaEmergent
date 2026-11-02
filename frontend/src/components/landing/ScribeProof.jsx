import React, { useEffect, useState } from "react";
import { Mic, FileText } from "lucide-react";

const LINES = [
  { t: "00:04", text: "دكتور، عندي صداع من ثلاثة أيام" },
  { t: "00:11", text: "وضغطي كان مرتفع اليوم الصباح" },
  { t: "00:19", text: "آخذ كونكور خمسة ملغ مرة يومياً" },
  { t: "00:27", text: "ما عندي حساسية من أي دواء" },
];

const SOAP = [
  ["S", "Headache × 3 days; elevated home BP this morning."],
  ["O", "BP to be re-measured in clinic."],
  ["A", "Headache with suspected uncontrolled hypertension."],
  ["P", "Review bisoprolol 5 mg; home BP log; red-flag advice."],
];

export function ScribeProof() {
  const [shown, setShown] = useState(1);
  useEffect(() => {
    const id = setInterval(() => setShown((n) => (n >= LINES.length + 2 ? 1 : n + 1)), 1600);
    return () => clearInterval(id);
  }, []);
  const lines = LINES.slice(0, Math.min(shown, LINES.length));
  const noteReady = shown > LINES.length;

  return (
    <div className="max-w-7xl mx-auto px-6 py-24 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center" data-testid="scribe-proof">
      <div className="lg:col-span-5">
        <p className="text-xs uppercase tracking-[0.2em] text-sage font-semibold">The clinical scribe</p>
        <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mt-3">Speak Arabic. Get a signed note.</h2>
        <p className="text-white/70 mt-5 leading-relaxed">With the patient's consent, Sihha listens to the consultation, shows the transcript as it happens, and drafts a structured SOAP note the doctor edits and signs. Uncertain words are highlighted, never guessed silently.</p>
      </div>
      <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="rounded-2xl bg-white/5 border border-white/15 p-5 min-h-[260px]">
          <p className="text-[10px] uppercase tracking-[0.15em] text-sage font-semibold flex items-center gap-2"><Mic className="h-3.5 w-3.5" /> Live transcript</p>
          <ul className="mt-4 space-y-3">
            {lines.map((l) => (
              <li key={l.t} className="flex gap-3 fade-up"><span className="text-[10px] text-white/40 tabular-nums pt-1">{l.t}</span><span dir="rtl" className="text-sm">{l.text}</span></li>
            ))}
          </ul>
        </div>
        <div className={`rounded-2xl p-5 min-h-[260px] ${noteReady ? "bg-white text-ink" : "bg-white/5 border border-white/15 text-white/40"}`} style={{ transition: "background-color 0.4s ease, color 0.4s ease" }}>
          <p className="text-[10px] uppercase tracking-[0.15em] font-semibold flex items-center gap-2"><FileText className="h-3.5 w-3.5" /> SOAP draft</p>
          {noteReady ? (
            <ul className="mt-4 space-y-3 fade-up">
              {SOAP.map(([k, v]) => <li key={k} className="text-sm flex gap-3"><b className="text-forest w-4">{k}</b><span className="text-ink-soft">{v}</span></li>)}
            </ul>
          ) : <p className="mt-4 text-sm">Drafting when the visit ends…</p>}
        </div>
      </div>
    </div>
  );
}
