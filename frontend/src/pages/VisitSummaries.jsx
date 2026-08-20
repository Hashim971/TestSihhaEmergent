import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { FileHeart, AlertTriangle, Languages, Stethoscope } from "lucide-react";

const LANGS = [
  { code: "ar", label: "العربية" },
  { code: "en", label: "English" },
];

export default function VisitSummaries() {
  const [rows, setRows] = useState(null);
  const [lang, setLang] = useState("ar");

  useEffect(() => {
    api.get("/patient/visit-summaries").then(({ data }) => setRows(data)).catch(() => setRows([]));
  }, []);

  const rtl = lang === "ar";

  return (
    <div className="space-y-8 fade-up max-w-4xl" data-testid="visit-summaries-page">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Visit Summaries</h1>
          <p className="text-ink-soft mt-1">
            What your doctor wants you to remember after each visit, in plain language.
          </p>
        </div>
        <div className="flex items-center rounded-full border border-line overflow-hidden" data-testid="visit-lang-toggle">
          <Languages className="h-3.5 w-3.5 mx-2 text-ink-soft" />
          {LANGS.map((l) => (
            <button key={l.code} onClick={() => setLang(l.code)} data-testid={`visit-lang-${l.code}`}
              className={`px-3 py-1.5 text-xs font-semibold transition-colors ${
                lang === l.code ? "bg-forest text-white" : "text-ink-soft hover:bg-sand"}`}>
              {l.label}
            </button>
          ))}
        </div>
      </div>

      {rows === null && <div className="card p-6 text-sm text-ink-soft">Loading your summaries…</div>}

      {rows?.length === 0 && (
        <div className="card p-10 text-center" data-testid="visit-summaries-empty">
          <FileHeart className="h-8 w-8 text-forest mx-auto" />
          <p className="mt-3 font-semibold">No visit summaries yet</p>
          <p className="text-sm text-ink-soft mt-1">
            After a consultation, your doctor can send you a plain-language summary. It will appear here.
          </p>
        </div>
      )}

      {(rows || []).map((row) => {
        const body = (row.edited_content || row.content || {})[lang] || {};
        return (
          <div key={row.artifact_id} className="card p-6" data-testid={`visit-summary-${row.artifact_id}`}>
            <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-line">
              <div>
                <p className="font-semibold">{row.reason_for_visit || "Consultation"}</p>
                <p className="text-xs text-ink-soft mt-0.5 flex items-center gap-1.5">
                  <Stethoscope className="h-3 w-3" /> {row.doctor_name || "Your doctor"} ·{" "}
                  {new Date(row.published_at).toLocaleDateString()}
                </p>
              </div>
            </div>

            <div className={`mt-4 space-y-4 ${rtl ? "text-right" : ""}`} dir={rtl ? "rtl" : "ltr"}>
              <Section label={rtl ? "ما تحدثنا عنه" : "What we discussed"} text={body.what_we_discussed} />
              <Section label={rtl ? "الحالة بكلمات بسيطة" : "In plain words"} text={body.diagnosis_plain} />

              {(body.medications || []).length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-[0.15em] text-ink-soft mb-1">
                    {rtl ? "الأدوية" : "Medications"}
                  </p>
                  <div className="space-y-1.5">
                    {body.medications.map((m, i) => (
                      <div key={i} className="text-sm border border-line rounded-lg px-3 py-2">
                        <span className="font-medium">{m.name}</span>
                        {m.instructions && <span className="text-ink-soft"> — {m.instructions}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {(body.next_steps || []).length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-[0.15em] text-ink-soft mb-1">
                    {rtl ? "الخطوات القادمة" : "Next steps"}
                  </p>
                  <ul className="text-sm space-y-1">
                    {body.next_steps.map((s, i) => <li key={i}>• {s}</li>)}
                  </ul>
                </div>
              )}

              {(body.red_flags || []).length > 0 && (
                <div className="border border-terracotta/40 bg-terracotta/5 rounded-xl px-4 py-3">
                  <p className="text-xs font-semibold text-terracotta flex items-center gap-1.5 mb-2">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    {rtl ? "راجع الطبيب فوراً إذا" : "Seek care right away if"}
                  </p>
                  <ul className="text-sm space-y-1">
                    {body.red_flags.map((s, i) => <li key={i}>• {s}</li>)}
                  </ul>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

const Section = ({ label, text }) =>
  text ? (
    <div>
      <p className="text-[10px] uppercase tracking-[0.15em] text-ink-soft mb-1">{label}</p>
      <p className="text-sm leading-relaxed">{text}</p>
    </div>
  ) : null;
