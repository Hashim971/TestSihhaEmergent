import React from "react";
import { CalendarClock } from "lucide-react";

const BADGE = {
  signed: { label: "Signed", cls: "bg-forest text-white" },
  reviewed: { label: "Draft", cls: "bg-sage/40 text-forest" },
  draft: { label: "Draft", cls: "bg-sage/40 text-forest" },
};

export function DayView({ visits, onOpen, action }) {
  const hours = visits.length
    ? (() => {
        const h = visits.map((v) => new Date(v.scheduled_at).getHours());
        const start = Math.max(0, Math.min(...h) - 1);
        const end = Math.min(23, Math.max(...h) + 1);
        return Array.from({ length: end - start + 1 }, (_, i) => start + i);
      })()
    : Array.from({ length: 10 }, (_, i) => 8 + i);

  const nowHour = new Date().getHours();

  return (
    <div className="card p-6" data-testid="dash-day-view">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <CalendarClock className="h-4 w-4 text-forest" /> Today,{" "}
          {new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}
        </h2>
        {action}
      </div>

      {visits.length === 0 ? (
        <p className="text-sm text-ink-soft" data-testid="day-view-empty">
          Nothing booked today. Your upcoming week is below.
        </p>
      ) : (
        <div className="divide-y divide-line">
          {hours.map((hour) => {
            const slot = visits.filter((v) => new Date(v.scheduled_at).getHours() === hour);
            const isNow = hour === nowHour;
            return (
              <div key={hour} className="flex gap-4 py-2 items-start" data-testid={`day-hour-${hour}`}>
                <span className={`w-16 shrink-0 text-xs pt-2 ${isNow ? "text-forest font-bold" : "text-ink-soft"}`}>
                  {String(hour).padStart(2, "0")}:00
                </span>
                <div className="flex-1 space-y-2 min-h-[2.25rem]">
                  {slot.length === 0 ? (
                    <div className={`h-9 rounded-lg border border-dashed ${isNow ? "border-sage bg-sage/10" : "border-line"}`} />
                  ) : (
                    slot.map((v) => {
                      const badge = v.briefing_status
                        ? BADGE[v.briefing_status]
                        : { label: "No briefing", cls: "bg-terracotta/10 text-terracotta" };
                      return (
                        <button key={v.encounter_id} onClick={() => onOpen(v.encounter_id)}
                          data-testid={`day-visit-${v.encounter_id}`}
                          className="w-full text-left px-4 py-2.5 rounded-lg bg-sand border border-line flex items-center gap-3 hover:bg-white"
                          style={{ transition: "background-color 0.2s ease" }}>
                          <span className="text-xs font-semibold w-14 shrink-0">
                            {new Date(v.scheduled_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
                          </span>
                          <span className="flex-1 min-w-0">
                            <span className="block text-sm font-medium truncate">{v.patient_name}</span>
                            <span className="block text-xs text-ink-soft truncate">
                              {v.reason_for_visit || "No reason recorded"}
                            </span>
                          </span>
                          {v.intake_status && v.intake_status !== "complete" && (
                            <span className="text-[10px] uppercase tracking-wider font-bold text-ink-soft">
                              intake {v.intake_status}
                            </span>
                          )}
                          <span className={`text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full ${badge.cls}`}>
                            {badge.label}
                          </span>
                        </button>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
