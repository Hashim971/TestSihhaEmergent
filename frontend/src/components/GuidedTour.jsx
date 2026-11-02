import React, { useEffect, useLayoutEffect, useState } from "react";
import { createPortal } from "react-dom";

const TOUR_TEXT = {
  chat: "Start here. Describe how you feel and the assistant asks a few short questions, then gives you a report.",
  medications: "Keep your medicines here. Add them yourself or upload a prescription photo, and we'll remind you at each dose.",
  pill_id: "Found a tablet you don't recognise? Photograph it and add it to your medicines in one tap.",
  find_care: "When you need a doctor, find a hospital or clinic nearby and book a visit.",
};

export function GuidedTour({ steps, onDone }) {
  const [i, setI] = useState(0);
  const [rect, setRect] = useState(null);
  const step = steps[i];

  useEffect(() => {
    const el = step && document.querySelector(`[data-testid="getting-started-step-${step.key}"]`);
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [step]);

  useLayoutEffect(() => {
    if (!step) return undefined;
    const measure = () => {
      const el = document.querySelector(`[data-testid="getting-started-step-${step.key}"]`);
      if (el) setRect(el.getBoundingClientRect());
    };
    measure();
    const id = setInterval(measure, 250);
    window.addEventListener("resize", measure);
    return () => { clearInterval(id); window.removeEventListener("resize", measure); };
  }, [step]);

  if (!step || !rect) return null;
  const last = i === steps.length - 1;
  const below = rect.bottom + 190 < window.innerHeight;
  const left = Math.min(Math.max(12, rect.left), window.innerWidth - 332);

  return createPortal(
    <div className="fixed inset-0 z-[60]" data-testid="guided-tour">
      <div className="absolute rounded-xl pointer-events-none"
        style={{ top: rect.top - 6, left: rect.left - 6, width: rect.width + 12, height: rect.height + 12,
          boxShadow: "0 0 0 9999px rgba(20, 30, 24, 0.55)", transition: "top 0.25s ease, left 0.25s ease, width 0.25s ease, height 0.25s ease" }} />
      <div className="absolute card p-4 w-[320px] max-w-[calc(100vw-24px)] fade-up" data-testid={`guided-tour-step-${step.key}`}
        style={{ left, top: below ? rect.bottom + 14 : Math.max(12, rect.top - 190) }}>
        <p className="text-[11px] uppercase tracking-[0.2em] text-ink-soft">Step {i + 1} of {steps.length}</p>
        <p className="text-sm mt-1.5">{TOUR_TEXT[step.key]}</p>
        <div className="flex items-center justify-between mt-4">
          <button onClick={onDone} className="text-xs text-ink-soft underline" data-testid="guided-tour-skip-btn">Skip tour</button>
          <button onClick={() => (last ? onDone() : setI(i + 1))} className="btn-primary !py-1.5 !px-4 text-xs" data-testid="guided-tour-next-btn">
            {last ? "Got it" : "Next"}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
