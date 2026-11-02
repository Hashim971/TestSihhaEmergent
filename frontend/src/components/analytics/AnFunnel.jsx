import React from "react";
import { useAnalytics, Loading, Empty } from "./shared";

export function AnFunnel({ filters }) {
  const [b2c, setB2c] = React.useState(true);
  const f = useAnalytics("funnel", { days: filters.days === 1 ? 7 : filters.days, include_demo: filters.include_demo }, { b2c_only: b2c });
  return (
    <div className="space-y-4" data-testid="analytics-funnel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-ink-soft">Patients who signed up in this period and how far they got.</p>
        <label className="inline-flex items-center gap-2 text-sm text-ink-soft cursor-pointer">
          <input type="checkbox" checked={b2c} onChange={(e) => setB2c(e.target.checked)} className="accent-[#1E3F2A]" data-testid="an-funnel-b2c-toggle" />
          Independent patients only (no hospital)
        </label>
      </div>
      {f === null ? <Loading /> : f === false ? <Empty>Could not load the funnel.</Empty> : !f.total ? (
        <Empty testid="an-funnel-empty">No patients signed up in this period.</Empty>
      ) : (
        <div className="card p-5 space-y-3">
          {f.steps.map((s, i) => {
            const pct = Math.round((s.users / f.total) * 100);
            const prev = i ? f.steps[i - 1].users : s.users;
            return (
              <div key={s.label} data-testid={`an-funnel-step-${i}`}>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="font-medium">{i + 1}. {s.label}</span>
                  <span className="text-ink-soft"><b className="text-ink">{s.users}</b> · {pct}%{i > 0 && prev > s.users ? <span className="text-terracotta"> · −{prev - s.users}</span> : ""}</span>
                </div>
                <div className="h-3 rounded-full bg-sand overflow-hidden"><div className="h-full bg-forest rounded-full" style={{ width: `${pct}%` }} /></div>
              </div>
            );
          })}
          <p className="text-sm pt-2 border-t border-line" data-testid="an-funnel-stuck">
            <b className="text-terracotta">{f.none_after_signup}</b> of {f.total} signed up but never chatted, added a medicine, used Pill ID or opened Find Care.
          </p>
        </div>
      )}
    </div>
  );
}
