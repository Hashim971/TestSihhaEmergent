import React from "react";
import { Check } from "lucide-react";

const STEPS = ["Your symptom", "Timing", "Severity", "Other details", "Summary"];
const DONE_MARKERS = ["Download Report", "تنزيل التقرير"];

export function screeningStepIndex(messages, completed) {
  const replies = messages.filter((m) => m.role === "assistant" && !m.streaming);
  const last = replies[replies.length - 1]?.content || "";
  if (completed || replies.length > 6 || DONE_MARKERS.some((k) => last.includes(k))) return STEPS.length;
  if (replies.length >= 5) return STEPS.length - 1;
  return Math.min(Math.max(replies.length - 1, 0), STEPS.length - 2);
}

export function ScreeningSteps({ messages, completed }) {
  const current = screeningStepIndex(messages, completed);
  return (
    <ol className="flex items-center gap-1.5 overflow-x-auto whitespace-nowrap px-4 sm:px-6 py-2.5 border-b border-line bg-sand/40" data-testid="screening-steps">
      {STEPS.map((label, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li key={label} className="flex items-center gap-1.5 shrink-0" data-testid={`screening-step-${i}`} data-state={done ? "done" : active ? "active" : "todo"}>
            <span className={`h-5 w-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
              done ? "bg-forest text-white" : active ? "bg-terracotta text-white" : "bg-white border border-line text-ink-soft"}`}
              style={{ transition: "background-color 0.3s ease" }}>
              {done ? <Check className="h-3 w-3" /> : i + 1}
            </span>
            <span className={`text-xs ${active ? "font-semibold text-ink" : done ? "text-forest" : "text-ink-soft"}`}>{label}</span>
            {i < STEPS.length - 1 && <span className={`h-px w-4 sm:w-6 ${done ? "bg-forest" : "bg-line"}`} />}
          </li>
        );
      })}
    </ol>
  );
}
