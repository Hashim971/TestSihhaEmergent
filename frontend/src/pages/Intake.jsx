import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { toast } from "sonner";
import YesNo from "../components/YesNo";
import { Check, ChevronLeft, ChevronRight, ClipboardList, Activity } from "lucide-react";

const isYesNo = (q) =>
  q.type === "single_choice" &&
  (q.options || []).length === 2 &&
  q.options.every((o) => ["yes", "no"].includes(o.trim().toLowerCase()));

const isAnswered = (a) => a !== undefined && a !== null && a !== "" && !(Array.isArray(a) && a.length === 0);

export default function Intake() {
  const { encounterId } = useParams();
  const navigate = useNavigate();
  const [form, setForm] = useState(null);
  const [answers, setAnswers] = useState({});
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get(`/intake/${encounterId}`)
      .then(({ data }) => {
        setForm(data);
        const existing = {};
        (data.responses || []).forEach((r) => { existing[r.question_id] = r.answer; });
        setAnswers(existing);
        const firstUnanswered = data.questions.findIndex((q) => !isAnswered(existing[q.question_id]));
        setStep(firstUnanswered === -1 ? data.questions.length - 1 : firstUnanswered);
        if (data.status === "complete") setDone(true);
      })
      .catch((e) => setError(e?.response?.data?.detail || "Could not load your questions"));
  }, [encounterId]);

  const persist = async (questionId) => {
    if (!isAnswered(answers[questionId])) return true;
    setSaving(true);
    try {
      const { data } = await api.post(`/intake/${encounterId}/responses`, {
        responses: [{ question_id: questionId, answer: answers[questionId] }],
      });
      setForm((f) => ({ ...f, status: data.status }));
      return true;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save that answer");
      return false;
    } finally {
      setSaving(false);
    }
  };

  if (error) {
    return (
      <div className="card p-10 text-center max-w-lg mx-auto fade-up" data-testid="intake-error">
        <p className="text-ink-soft">{error}</p>
      </div>
    );
  }
  if (!form) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="intake-loading">
        <Activity className="h-7 w-7 text-forest animate-pulse" />
      </div>
    );
  }

  if (done) {
    return (
      <div className="card p-10 text-center max-w-xl mx-auto fade-up" data-testid="intake-complete">
        <div className="h-14 w-14 rounded-full bg-forest mx-auto flex items-center justify-center mb-4">
          <Check className="h-7 w-7 text-sage" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight mb-2">Your answers are with your doctor</h1>
        <p className="text-ink-soft mb-6">
          They'll read them before your visit on {new Date(form.scheduled_at).toLocaleString()}, so you won't have to
          start from the beginning.
        </p>
        <button onClick={() => navigate("/dashboard")} data-testid="intake-back-to-dashboard-btn" className="btn-primary">
          Back to Dashboard
        </button>
      </div>
    );
  }

  const q = form.questions[step];
  const total = form.questions.length;
  const value = answers[q.question_id];
  const set = (v) => setAnswers((a) => ({ ...a, [q.question_id]: v }));
  const canAdvance = !q.required || isAnswered(value);

  const next = async () => {
    if (!(await persist(q.question_id))) return;
    if (step + 1 < total) return setStep(step + 1);
    const stillMissing = form.questions.filter((x) => x.required && !isAnswered(answers[x.question_id]));
    if (stillMissing.length) {
      toast.error("A few required questions still need an answer");
      return setStep(form.questions.indexOf(stillMissing[0]));
    }
    setDone(true);
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6 fade-up" data-testid="intake-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <ClipboardList className="h-6 w-6 text-forest" /> Pre-visit questions
        </h1>
        <p className="text-ink-soft text-sm mt-1">
          {form.reason_for_visit || "Upcoming visit"} · {new Date(form.scheduled_at).toLocaleDateString()}
        </p>
      </div>

      <div>
        <div className="flex items-center justify-between text-xs text-ink-soft mb-2">
          <span data-testid="intake-progress-label">Question {step + 1} of {total}</span>
          <span>{Math.round(((step + 1) / total) * 100)}%</span>
        </div>
        <div className="h-1.5 bg-sand rounded-full overflow-hidden" data-testid="intake-progress">
          <div className="h-full bg-forest" style={{ width: `${((step + 1) / total) * 100}%`, transition: "width 0.3s ease" }} />
        </div>
      </div>

      <div className="card p-8" key={q.question_id} data-testid={`intake-question-${q.question_id}`}>
        <p className="font-heading text-lg font-semibold mb-1">{q.text}</p>
        <p className="text-xs text-ink-soft mb-6">{q.required ? "Required" : "Optional — skip if you're not sure"}</p>

        {isYesNo(q) ? (
          <YesNo label="" value={value === "Yes" ? true : value === "No" ? false : undefined}
            onChange={(v) => set(v ? "Yes" : "No")} testid={`intake-yesno-${q.question_id}`} />
        ) : q.type === "single_choice" ? (
          <div className="space-y-2">
            {(q.options || []).map((opt) => (
              <button key={opt} onClick={() => set(opt)} data-testid={`intake-option-${q.question_id}-${opt}`}
                className={`w-full text-left px-4 py-3 rounded-xl border text-sm ${
                  value === opt ? "bg-forest text-white border-forest" : "bg-sand border-line hover:bg-white"
                }`} style={{ transition: "background-color 0.2s ease, color 0.2s ease" }}>
                {opt}
              </button>
            ))}
          </div>
        ) : q.type === "multi_choice" ? (
          <div className="space-y-2">
            {(q.options || []).map((opt) => {
              const list = Array.isArray(value) ? value : [];
              const on = list.includes(opt);
              return (
                <button key={opt} data-testid={`intake-option-${q.question_id}-${opt}`}
                  onClick={() => set(on ? list.filter((x) => x !== opt) : [...list, opt])}
                  className={`w-full text-left px-4 py-3 rounded-xl border text-sm flex items-center gap-3 ${
                    on ? "bg-forest text-white border-forest" : "bg-sand border-line hover:bg-white"
                  }`} style={{ transition: "background-color 0.2s ease, color 0.2s ease" }}>
                  <span className={`h-4 w-4 rounded border ${on ? "bg-sage border-sage" : "border-line"}`} />
                  {opt}
                </button>
              );
            })}
          </div>
        ) : q.type === "scale" ? (
          <div className="flex flex-wrap gap-2" data-testid={`intake-scale-${q.question_id}`}>
            {Array.from({ length: 11 }, (_, i) => String(i)).map((n) => (
              <button key={n} onClick={() => set(n)} data-testid={`intake-scale-${q.question_id}-${n}`}
                className={`h-11 w-11 rounded-full border text-sm font-medium ${
                  value === n ? "bg-forest text-white border-forest" : "bg-sand border-line hover:bg-white"
                }`} style={{ transition: "background-color 0.2s ease, color 0.2s ease" }}>
                {n}
              </button>
            ))}
          </div>
        ) : (
          <textarea value={value || ""} onChange={(e) => set(e.target.value)} rows={4}
            data-testid={`intake-text-${q.question_id}`} placeholder="Answer in your own words…"
            className="w-full border border-line rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
        )}

        <div className="flex items-center justify-between mt-8">
          {step > 0 ? (
            <button onClick={() => setStep(step - 1)} data-testid="intake-back-btn" className="btn-outline">
              <ChevronLeft className="h-4 w-4" /> Back
            </button>
          ) : <span />}
          <button onClick={next} disabled={saving || !canAdvance} data-testid="intake-next-btn" className="btn-primary">
            {step + 1 === total ? (saving ? "Saving…" : "Finish") : "Next"} <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      <p className="text-center text-xs text-ink-soft">
        Each answer is saved as you go — you can close this and come back later.
      </p>
    </div>
  );
}
