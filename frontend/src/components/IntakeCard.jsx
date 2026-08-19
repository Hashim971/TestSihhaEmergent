import React from "react";
import { ClipboardList, Check } from "lucide-react";

const STATUS = {
  not_generated: { label: "Not generated", note: "Generate a questionnaire tailored to this patient's record." },
  pending: { label: "Sent to patient", note: "Waiting for the patient to answer." },
  partial: { label: "In progress", note: "The patient has answered some questions." },
  complete: { label: "Complete", note: "All required questions answered." },
};

export function IntakeCard({ intake, onGenerate, generating }) {
  const status = intake?.status || "not_generated";
  const meta = STATUS[status] || STATUS.not_generated;
  const answers = Object.fromEntries((intake?.responses || []).map((r) => [r.question_id, r.answer]));

  return (
    <div className="card p-6" id="sect-intake_forms" data-testid="intake-section">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <ClipboardList className="h-4 w-4 text-forest" /> Pre-Visit Intake
          </h3>
          <p className="text-xs text-ink-soft mt-1">{meta.note}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-[10px] uppercase tracking-wider font-bold px-2.5 py-1 rounded-full ${
            status === "complete" ? "bg-forest text-white" : "bg-sand text-ink-soft"}`}
            data-testid="intake-status-badge">
            {meta.label}
          </span>
          {status === "not_generated" && (
            <button onClick={onGenerate} disabled={generating} data-testid="generate-intake-btn" className="btn-outline">
              {generating ? "Writing questions…" : "Generate Intake"}
            </button>
          )}
        </div>
      </div>

      {(intake?.questions || []).length > 0 && (
        <div className="mt-5 space-y-3" data-testid="intake-answers">
          {intake.questions.map((q, i) => {
            const a = answers[q.question_id];
            const answered = a !== undefined && a !== null && a !== "" && !(Array.isArray(a) && a.length === 0);
            return (
              <div key={q.question_id} className="border border-line rounded-xl px-4 py-3"
                data-testid={`intake-qa-${q.question_id}`}>
                <p className="text-sm font-medium">{i + 1}. {q.text}</p>
                {answered ? (
                  <p className="text-sm text-forest mt-1 flex items-start gap-1.5">
                    <Check className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                    {Array.isArray(a) ? a.join(", ") : String(a)}
                  </p>
                ) : (
                  <p className="text-xs text-ink-soft mt-1">Not answered yet</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
