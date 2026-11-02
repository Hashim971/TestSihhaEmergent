import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AnOverview } from "../../components/analytics/AnOverview";
import { AnHeatmap } from "../../components/analytics/AnHeatmap";
import { AnFunnel } from "../../components/analytics/AnFunnel";
import { AnJourneys } from "../../components/analytics/AnJourneys";
import { AnFrustration } from "../../components/analytics/AnFrustration";
import { AnReplays } from "../../components/analytics/AnReplays";
import { ReplayModal } from "../../components/analytics/ReplayModal";
import { inputCls, labelCls } from "../../components/admin/ui";

const TABS = [["overview", "Overview"], ["heatmaps", "Heatmaps"], ["funnel", "Signup funnel"], ["journeys", "Journeys"],
  ["frustration", "Rage & dead clicks"], ["replays", "Session replays"]];

export default function Analytics() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "overview";
  const filters = { days: +(params.get("days") || 7), role: params.get("role") || "", include_demo: params.get("demo") === "1" };
  const setFilters = (f) => setParams({ ...Object.fromEntries(params), days: f.days, role: f.role, demo: f.include_demo ? "1" : "0" });
  const [replay, setReplay] = useState(null);
  const go = (t, extra = {}) => setParams({ days: filters.days, role: filters.role, demo: filters.include_demo ? "1" : "0", tab: t, ...extra });
  const props = { filters, onWatch: (sessionId, t) => setReplay({ sessionId, t }), go, params };

  return (
    <div className="fade-up space-y-6" data-testid="analytics-page">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Analytics</h1>
        <p className="text-ink-soft mt-1 text-sm">How signed-in people use Sihha. Typed text and on-screen health details are masked in recordings; data is kept for 30 days.</p>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className={labelCls}>Period</label>
          <select value={filters.days} onChange={(e) => setFilters({ ...filters, days: +e.target.value })} className={inputCls} data-testid="analytics-days-filter">
            <option value={1}>Last 24 hours</option><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option>
          </select>
        </div>
        <div>
          <label className={labelCls}>Who</label>
          <select value={filters.role} onChange={(e) => setFilters({ ...filters, role: e.target.value })} className={inputCls} data-testid="analytics-role-filter">
            <option value="">Everyone</option><option value="patient">Patients</option><option value="doctor">Doctors</option><option value="pharmacist">Pharmacists</option>
          </select>
        </div>
        <label className="inline-flex items-center gap-2 text-sm text-ink-soft pb-2 cursor-pointer">
          <input type="checkbox" checked={filters.include_demo} onChange={(e) => setFilters({ ...filters, include_demo: e.target.checked })}
            className="accent-[#1E3F2A]" data-testid="analytics-include-demo-toggle" /> Include demo accounts
        </label>
      </div>
      <nav className="flex gap-1 border-b border-line overflow-x-auto whitespace-nowrap" data-testid="analytics-tabs">
        {TABS.map(([k, label]) => (
          <button key={k} onClick={() => go(k)} data-testid={`analytics-tab-${k}`}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px shrink-0 ${tab === k ? "border-forest text-forest" : "border-transparent text-ink-soft hover:text-ink"}`}>
            {label}
          </button>
        ))}
      </nav>
      {tab === "overview" && <AnOverview {...props} />}
      {tab === "heatmaps" && <AnHeatmap {...props} />}
      {tab === "funnel" && <AnFunnel {...props} />}
      {tab === "journeys" && <AnJourneys {...props} />}
      {tab === "frustration" && <AnFrustration {...props} />}
      {tab === "replays" && <AnReplays {...props} />}
      {replay && <ReplayModal {...replay} onClose={() => setReplay(null)} />}
    </div>
  );
}
