import React, { useState, useRef, useEffect } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Send, Languages, Sparkles, CheckCircle2, AlertTriangle } from "lucide-react";

const LANGS = [
  { code: "ar", label: "العربية" },
  { code: "en", label: "English" },
];

export function PatientSummaryPanel({ noteArtifactId, summary, onChange }) {
  const [lang, setLang] = useState("ar");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState(summary ? summary.edited_content || summary.content : null);
  const saveTimer = useRef(null);

  useEffect(() => {
    setDraft(summary ? summary.edited_content || summary.content : null);
  }, [summary]);

  const published = summary?.status === "published";
  const body = draft?.[lang] || {};
  const rtl = lang === "ar";

  const generate = async () => {
    setBusy(true);
    try {
      await api.post(`/artifacts/${noteArtifactId}/patient-summary`);
      toast.success("Patient summary drafted");
      await onChange();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not draft the summary");
    } finally {
      setBusy(false);
    }
  };

  const edit = (field, value) => {
    const next = { ...draft, [lang]: { ...body, [field]: value } };
    setDraft(next);
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      const clean = { ...next, [lang]: { ...next[lang] } };
      ["next_steps", "red_flags"].forEach((k) => {
        if (Array.isArray(clean[lang][k])) clean[lang][k] = clean[lang][k].filter((l) => l.trim() !== "");
      });
      api.patch(`/artifacts/${summary.artifact_id}`, { edited_content: clean })
        .then(onChange)
        .catch(() => toast.error("Could not save edits"));
    }, 800);
  };

  const publish = async () => {
    if (!window.confirm("Send this summary to the patient? They will be able to read it in their portal.")) return;
    setBusy(true);
    try {
      await api.post(`/artifacts/${summary.artifact_id}/publish`);
      toast.success("Summary sent to the patient");
      await onChange();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not send the summary");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-6 border-t border-line pt-5" data-testid="patient-summary-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-forest" /> Note to the patient
          </p>
          <p className="text-xs text-ink-soft mt-0.5">
            A plain-language version of this visit. Review it, then send it to the patient.
          </p>
        </div>
        {!summary ? (
          <button onClick={generate} disabled={busy} data-testid="generate-patient-summary-btn"
            className={`btn-primary ${busy ? "opacity-50" : ""}`}>
            {busy ? "Drafting…" : "Draft Patient Summary"}
          </button>
        ) : (
          <div className="flex items-center gap-2">
            <div className="flex items-center rounded-full border border-line overflow-hidden" data-testid="summary-lang-toggle">
              <Languages className="h-3.5 w-3.5 mx-2 text-ink-soft" />
              {LANGS.map((l) => (
                <button key={l.code} onClick={() => setLang(l.code)} data-testid={`summary-lang-${l.code}`}
                  className={`px-3 py-1.5 text-xs font-semibold transition-colors ${
                    lang === l.code ? "bg-forest text-white" : "text-ink-soft hover:bg-sand"}`}>
                  {l.label}
                </button>
              ))}
            </div>
            {!published && (
              <button onClick={generate} disabled={busy} data-testid="regenerate-patient-summary-btn"
                className="btn-outline !py-1.5 !px-3 text-xs">Redraft</button>
            )}
          </div>
        )}
      </div>

      {summary && draft && (
        <div className={`mt-4 space-y-4 ${rtl ? "text-right" : ""}`} dir={rtl ? "rtl" : "ltr"}
          data-testid="patient-summary-body">
          <SummaryField label={rtl ? "ما تحدثنا عنه" : "What we discussed"} value={body.what_we_discussed}
            readOnly={published} testid="summary-discussed"
            onChange={(v) => edit("what_we_discussed", v)} />
          <SummaryField label={rtl ? "الحالة بكلمات بسيطة" : "In plain words"} value={body.diagnosis_plain}
            readOnly={published} testid="summary-diagnosis"
            onChange={(v) => edit("diagnosis_plain", v)} />

          {(body.medications || []).length > 0 && (
            <div>
              <p className="text-[10px] uppercase tracking-[0.15em] text-ink-soft mb-1">
                {rtl ? "الأدوية" : "Medications"}
              </p>
              <div className="space-y-1.5" data-testid="summary-medications">
                {body.medications.map((m, i) => (
                  <div key={i} className="text-sm border border-line rounded-lg px-3 py-2">
                    <span className="font-medium">{m.name}</span>
                    {m.instructions && <span className="text-ink-soft"> — {m.instructions}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          <ListField label={rtl ? "الخطوات القادمة" : "Next steps"} items={body.next_steps}
            readOnly={published} testid="summary-next-steps"
            onChange={(v) => edit("next_steps", v)} />

          <div className="border border-terracotta/40 bg-terracotta/5 rounded-xl px-4 py-3">
            <p className="text-xs font-semibold text-terracotta flex items-center gap-1.5 mb-2">
              <AlertTriangle className="h-3.5 w-3.5" /> {rtl ? "راجع الطبيب فوراً إذا" : "Seek care right away if"}
            </p>
            <ListField items={body.red_flags} readOnly={published} testid="summary-red-flags"
              onChange={(v) => edit("red_flags", v)} />
          </div>

          {published ? (
            <div className="flex items-center gap-2 text-sm" dir="ltr" data-testid="summary-published-line">
              <CheckCircle2 className="h-4 w-4 text-forest" />
              Sent to the patient {new Date(summary.published_at).toLocaleString()}
            </div>
          ) : (
            <button onClick={publish} disabled={busy} dir="ltr" data-testid="send-patient-summary-btn"
              className={`btn-primary ${busy ? "opacity-50" : ""}`}>
              <Send className="h-4 w-4" /> Send to Patient
            </button>
          )}
        </div>
      )}
    </div>
  );
}

const SummaryField = ({ label, value, onChange, readOnly, testid }) => (
  <div>
    <p className="text-[10px] uppercase tracking-[0.15em] text-ink-soft mb-1">{label}</p>
    {readOnly ? (
      <p className="text-sm" data-testid={testid}>{value || <span className="text-ink-soft">—</span>}</p>
    ) : (
      <textarea value={value || ""} rows={3} data-testid={testid} onChange={(e) => onChange(e.target.value)}
        className="w-full text-sm border border-line rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-forest" />
    )}
  </div>
);

const ListField = ({ label, items, onChange, readOnly, testid }) => (
  <div>
    {label && <p className="text-[10px] uppercase tracking-[0.15em] text-ink-soft mb-1">{label}</p>}
    {readOnly ? (
      <ul className="text-sm space-y-1" data-testid={testid}>
        {(items || []).map((it, i) => <li key={i}>• {it}</li>)}
      </ul>
    ) : (
      <textarea value={(items || []).join("\n")} rows={Math.max(2, (items || []).length)} data-testid={testid}
        onChange={(e) => onChange(e.target.value.split("\n"))}
        className="w-full text-sm border border-line rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-forest" />
    )}
  </div>
);
