import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { MessageSquare, Pill, ScanLine, Building2, Check, ArrowRight, X } from "lucide-react";
import { api } from "../lib/api";
import { usePlatform } from "../context/PlatformContext";
import { GuidedTour } from "./GuidedTour";

export const GETTING_STARTED_STEPS = [
  { key: "chat", to: "/chat", icon: MessageSquare, flag: "health_chat", title: "Tell us what's bothering you",
    body: "Start a health chat — a few short questions, then a report and advice on where to go." },
  { key: "medications", to: "/medications", icon: Pill, title: "Add your medicines",
    body: "Type them in or photograph a prescription, and get a reminder at each dose." },
  { key: "pill_id", to: "/pill-id", icon: ScanLine, flag: "pill_id", title: "Identify a pill",
    body: "Not sure what a tablet is? Take a photo and add it to your medicines." },
  { key: "find_care", to: "/find-care", icon: Building2, flag: "booking", title: "Find care near you",
    body: "Browse hospitals and clinics, read ratings and book a visit." },
];

export function GettingStarted() {
  const { isOn } = usePlatform();
  const [gs, setGs] = useState(null);
  const steps = GETTING_STARTED_STEPS.filter((s) => !s.flag || isOn(s.flag));

  const load = useCallback(() => api.get("/getting-started").then(({ data }) => setGs(data)).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);
  const save = (body) => api.post("/getting-started", body).then(({ data }) => setGs(data)).catch(() => {});

  if (!gs || gs.dismissed) return null;
  const done = steps.filter((s) => gs.steps[s.key]).length;
  const next = steps.find((s) => !gs.steps[s.key]);
  if (!next && gs.tour_done) return null;

  return (
    <section className="card p-5 sm:p-6 space-y-4" data-testid="getting-started">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-terracotta font-semibold">Start here</p>
          <h2 className="text-xl font-semibold mt-1">Your first steps with Sihha</h2>
          <p className="text-sm text-ink-soft mt-1" data-testid="getting-started-progress">{done} of {steps.length} done</p>
        </div>
        <button onClick={() => save({ dismissed: true })} className="p-2 rounded-full hover:bg-sand" aria-label="Hide checklist" data-testid="getting-started-dismiss-btn">
          <X className="h-4 w-4 text-ink-soft" />
        </button>
      </div>
      <div className="h-1.5 rounded-full bg-sand overflow-hidden">
        <div className="h-full bg-forest rounded-full" style={{ width: `${(done / steps.length) * 100}%`, transition: "width 0.4s ease" }} />
      </div>
      <ol className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {steps.map((s, i) => <Step key={s.key} step={s} n={i + 1} done={gs.steps[s.key]} isNext={next?.key === s.key} />)}
      </ol>
      {!gs.tour_done && <GuidedTour steps={steps} onDone={() => save({ tour_done: true })} />}
    </section>
  );
}

function Step({ step, n, done, isNext }) {
  const Icon = step.icon;
  return (
    <li>
      <Link to={step.to} data-testid={`getting-started-step-${step.key}`}
        className={`flex gap-3 rounded-xl border p-4 h-full hover:border-forest/40 ${isNext ? "border-forest bg-sage/15" : "border-line"}`}
        style={{ transition: "border-color 0.2s ease" }}>
        <span className={`h-9 w-9 shrink-0 rounded-full flex items-center justify-center ${done ? "bg-forest text-white" : "bg-sand text-forest"}`}>
          {done ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
        </span>
        <span className="min-w-0 flex-1">
          <span className={`block font-medium text-sm ${done ? "line-through text-ink-soft" : ""}`}>{n}. {step.title}</span>
          <span className="block text-xs text-ink-soft mt-0.5">{step.body}</span>
          {isNext && <span className="inline-flex items-center gap-1 text-xs font-semibold text-forest mt-2">Start <ArrowRight className="h-3 w-3" /></span>}
        </span>
      </Link>
    </li>
  );
}
