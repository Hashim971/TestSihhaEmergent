import React, { useState } from "react";
import { Stethoscope, ChevronDown, RefreshCw, Share2, Clock, MessageSquare } from "lucide-react";

const SEVERITY = { severe: "text-terracotta", moderate: "text-ink", mild: "text-ink-soft", unclear: "text-ink-soft" };

export function ScreeningCard({ screening, excerpts, onRestructure, restructuring, onAsk }) {
  const [openReport, setOpenReport] = useState(null);
  const [openFinding, setOpenFinding] = useState(null);
  const reports = screening?.reports || [];
  const timeline = (screening?.symptom_timeline || []).filter((s) => s.times_reported > 1);

  if (reports.length === 0) {
    return (
      <div className="card p-6" id="sect-health_reports" data-testid="screening-section">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Stethoscope className="h-4 w-4 text-forest" /> AI Screenings
        </h3>
        <p className="text-sm text-ink-soft mt-2">This patient has not completed an AI health screening.</p>
      </div>
    );
  }

  return (
    <div className="card p-6" id="sect-health_reports" data-testid="screening-section">
      <h3 className="text-lg font-semibold flex items-center gap-2">
        <Stethoscope className="h-4 w-4 text-forest" /> AI Screenings
      </h3>
      <p className="text-xs text-ink-soft mt-1">
        The patient's own words, structured. Anything older than {screening.stale_after_days} days is marked stale.
      </p>

      {timeline.length > 0 && (
        <div className="mt-4 border border-line rounded-xl px-4 py-3" data-testid="symptom-timeline">
          <p className="text-[10px] uppercase tracking-wider font-bold text-ink-soft mb-2">Reported more than once</p>
          {timeline.map((s) => (
            <p key={s.symptom} className="text-sm" data-testid={`timeline-${s.symptom.replace(/\s+/g, "-")}`}>
              <span className="font-medium">{s.symptom}</span>
              <span className="text-ink-soft">
                {" "}— {s.times_reported} times, {new Date(s.first_reported_at).toLocaleDateString()} to{" "}
                {new Date(s.last_reported_at).toLocaleDateString()}
              </span>
            </p>
          ))}
        </div>
      )}

      <div className="mt-4 space-y-3">
        {reports.map((r) => (
          <div key={r.report_id} className="border border-line rounded-xl" data-testid={`screening-report-${r.report_id}`}>
            <div className="px-4 py-3 flex items-center gap-3 flex-wrap">
              <button onClick={() => setOpenReport(openReport === r.report_id ? null : r.report_id)}
                data-testid={`toggle-report-${r.report_id}`} className="flex items-center gap-2 text-sm font-medium">
                <ChevronDown className={`h-4 w-4 ${openReport === r.report_id ? "rotate-180" : ""}`}
                  style={{ transition: "transform 0.2s ease" }} />
                {new Date(r.generated_at).toLocaleDateString()}
              </button>
              {r.shared_for_this_visit && (
                <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full bg-forest text-white flex items-center gap-1"
                  data-testid={`shared-badge-${r.report_id}`}>
                  <Share2 className="h-3 w-3" /> Shared for this visit
                </span>
              )}
              {r.stale && (
                <span className="text-[10px] uppercase tracking-wider font-bold text-terracotta flex items-center gap-1"
                  data-testid={`stale-badge-${r.report_id}`}>
                  <Clock className="h-3 w-3" /> Stale · {r.age_days} days old
                </span>
              )}
              <span className="text-xs text-ink-soft ml-auto">{r.findings.length} findings</span>
              {!r.findings_extracted_at && (
                <button onClick={() => onRestructure(r.report_id)} disabled={restructuring === r.report_id}
                  data-testid={`restructure-${r.report_id}`} className="btn-outline !py-1 !px-3 text-xs">
                  <RefreshCw className="h-3 w-3" /> {restructuring === r.report_id ? "Reading…" : "Structure findings"}
                </button>
              )}
            </div>

            {openReport === r.report_id && (
              <div className="px-4 pb-4 space-y-2" data-testid={`report-findings-${r.report_id}`}>
                {r.findings.length === 0 && (
                  <p className="text-xs text-ink-soft">No structured findings — the raw report text is all there is.</p>
                )}
                {r.findings.map((f) => (
                  <div key={f.finding_id} id={`cite-health_reports-${f.finding_id}`}
                    className="border border-line rounded-lg px-3 py-2.5" data-testid={`finding-${f.finding_id}`}>
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-medium">{f.symptom}</p>
                      <span className={`text-[10px] uppercase tracking-wider font-bold ${SEVERITY[f.severity] || "text-ink-soft"}`}>
                        {f.severity}
                      </span>
                      {f.onset && <span className="text-xs text-ink-soft">started {f.onset}</span>}
                      {f.duration && <span className="text-xs text-ink-soft">· {f.duration}</span>}
                    </div>
                    <p className="text-xs text-ink mt-1">“{f.patient_words}”</p>
                    <div className="flex items-center gap-3 mt-2">
                      {(f.source_message_ids || []).length > 0 && (
                        <button onClick={() => setOpenFinding(openFinding === f.finding_id ? null : f.finding_id)}
                          data-testid={`toggle-excerpt-${f.finding_id}`} className="text-[10px] uppercase tracking-wider font-bold text-forest">
                          {openFinding === f.finding_id ? "Hide transcript" : "Show transcript"}
                        </button>
                      )}
                      <button onClick={() => onAsk(`What did the screening say about ${f.symptom}?`)}
                        data-testid={`ask-about-${f.finding_id}`}
                        className="text-[10px] uppercase tracking-wider font-bold text-forest flex items-center gap-1">
                        <MessageSquare className="h-3 w-3" /> Ask about this
                      </button>
                    </div>
                    {openFinding === f.finding_id && (
                      <div className="mt-2 space-y-1.5 border-l-2 border-sage pl-3" data-testid={`excerpt-${f.finding_id}`}>
                        {(f.source_message_ids || []).map((mid) => (
                          <p key={mid} className="text-xs text-ink-soft">
                            <span className="font-semibold">{excerpts?.[mid]?.role === "user" ? "Patient" : "Assistant"}: </span>
                            {excerpts?.[mid]?.content || "Message no longer available"}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
