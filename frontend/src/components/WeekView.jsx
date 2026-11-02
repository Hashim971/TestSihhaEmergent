import React, { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "../lib/api";

const DAY = 86400000;
const NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const pad = (n) => String(n).padStart(2, "0");

// Everything is shown in clinic time (the availability's tz offset), so slots and visits line up.
export function WeekView({ encounters, onOpen }) {
  const [availability, setAvailability] = useState(null);
  const [weekOffset, setWeekOffset] = useState(0);

  useEffect(() => { api.get("/doctor/availability").then(({ data }) => setAvailability(data)).catch(() => setAvailability({ weekly: [], tz_offset_minutes: 180 })); }, []);

  const offset = (availability?.tz_offset_minutes ?? 180) * 60000;
  const toClinic = (iso) => new Date(new Date(iso).getTime() + offset);
  const today = toClinic(new Date().toISOString());
  const monday = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()) - ((today.getUTCDay() + 6) % 7) * DAY + weekOffset * 7 * DAY);
  const days = Array.from({ length: 7 }, (_, i) => new Date(monday.getTime() + i * DAY));

  const visits = encounters.filter((e) => e.scheduled_at).map((e) => ({ ...e, local: toClinic(e.scheduled_at) }))
    .filter((e) => e.local >= monday && e.local < new Date(monday.getTime() + 7 * DAY));

  const blocks = availability?.weekly || [];
  if (!availability) return <div className="card p-6 text-sm text-ink-soft" data-testid="week-view-loading">Loading your week…</div>;
  const blocked = new Set(availability?.blocked_dates || []);
  const hoursUsed = [...blocks.flatMap((b) => [parseInt(b.start, 10), parseInt(b.end, 10)]), ...visits.map((v) => v.local.getUTCHours())];
  const startH = hoursUsed.length ? Math.max(0, Math.min(...hoursUsed) - 1) : 8;
  const endH = hoursUsed.length ? Math.min(24, Math.max(...hoursUsed) + 1) : 18;
  const hours = Array.from({ length: endH - startH }, (_, i) => startH + i);
  const isOpen = (weekday, h) => blocks.some((b) => Number(b.weekday) === weekday && parseInt(b.start, 10) <= h && h < Math.ceil(parseFloat(b.end.replace(":", ".")) ));
  const label = `${days[0].toLocaleDateString(undefined, { day: "numeric", month: "short", timeZone: "UTC" })} – ${days[6].toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })}`;

  return (
    <div className="card p-4 sm:p-6" data-testid="week-view">
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <button onClick={() => setWeekOffset(weekOffset - 1)} className="p-2 rounded-full border border-line hover:bg-sand" data-testid="week-prev-btn"><ChevronLeft className="h-4 w-4 rtl:rotate-180" /></button>
        <button onClick={() => setWeekOffset(0)} className="btn-outline !py-1.5 !px-3 text-xs" data-testid="week-today-btn">This week</button>
        <button onClick={() => setWeekOffset(weekOffset + 1)} className="p-2 rounded-full border border-line hover:bg-sand" data-testid="week-next-btn"><ChevronRight className="h-4 w-4 rtl:rotate-180" /></button>
        <p className="font-semibold ms-2" data-testid="week-range-label">{label}</p>
        <p className="ms-auto text-xs text-ink-soft flex items-center gap-3">
          <span className="inline-flex items-center gap-1"><span className="h-3 w-3 rounded bg-sage/30 border border-sage/60" /> Open hours</span>
          <span data-testid="week-visit-count">{visits.length === 1 ? "1 visit" : `${visits.length} visits`}</span>
        </p>
      </div>
      <div className="overflow-x-auto">
        <div className="grid min-w-[760px]" style={{ gridTemplateColumns: "56px repeat(7, minmax(0, 1fr))" }}>
          <div />
          {days.map((d, i) => {
            const isToday = weekOffset === 0 && d.getUTCDate() === today.getUTCDate();
            return (
              <div key={i} className={`text-center pb-2 text-xs ${isToday ? "text-forest font-bold" : "text-ink-soft"}`} data-testid={`week-day-${i}`}>
                {NAMES[i]} <span className="block text-base font-semibold text-ink">{d.getUTCDate()}</span>
                {blocked.has(d.toISOString().slice(0, 10)) && <span className="text-[10px] text-terracotta">Closed</span>}
              </div>
            );
          })}
          {hours.map((h) => (
            <React.Fragment key={h}>
              <div className="text-[11px] text-ink-soft pe-2 pt-1 text-end border-t border-line">{pad(h)}:00</div>
              {days.map((d, i) => {
                const open = !blocked.has(d.toISOString().slice(0, 10)) && isOpen(i, h);
                const cell = visits.filter((v) => v.local.getUTCDay() === d.getUTCDay() && v.local.getUTCHours() === h);
                return (
                  <div key={i} className={`border-t border-s border-line min-h-[52px] p-1 space-y-1 ${open ? "bg-sage/30" : ""}`} data-testid={`week-cell-${i}-${h}`}>
                    {cell.map((v) => (
                      <button key={v.encounter_id} onClick={() => onOpen(v.encounter_id)} data-testid={`week-visit-${v.encounter_id}`}
                        className={`w-full text-start rounded-md px-2 py-1 text-[11px] leading-tight border ${v.status === "completed" ? "bg-white border-line text-ink-soft" : "bg-forest text-white border-forest"} hover:opacity-90`}
                        style={{ transition: "opacity 0.2s ease" }}>
                        <span className="font-semibold">{pad(v.local.getUTCHours())}:{pad(v.local.getUTCMinutes())}</span> {v.patient_name}
                        {v.record_shared === false && <span className="block opacity-80">Record not shared</span>}
                      </button>
                    ))}
                  </div>
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}
