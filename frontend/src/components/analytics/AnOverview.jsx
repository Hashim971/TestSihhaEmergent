import React from "react";
import { Users, Activity, MousePointerClick, Flame, Timer, Smartphone } from "lucide-react";
import { useAnalytics, fmtMs, Loading, Empty } from "./shared";

const Stat = ({ icon: Icon, label, value, testid }) => (
  <div className="card p-4" data-testid={testid}>
    <div className="flex items-center justify-between text-ink-soft"><span className="text-xs uppercase tracking-wider">{label}</span><Icon className="h-4 w-4" /></div>
    <p className="text-2xl font-heading font-bold mt-2">{value}</p>
  </div>
);

export function AnOverview({ filters, go }) {
  const s = useAnalytics("summary", filters);
  if (s === null) return <Loading />;
  if (s === false) return <Empty>Could not load analytics.</Empty>;
  if (!s.sessions) return <Empty testid="analytics-empty">No activity recorded in this period yet. Data appears as soon as signed-in users use the app.</Empty>;
  return (
    <div className="space-y-6" data-testid="analytics-overview">
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
        <Stat icon={Users} label="People" value={s.users} testid="an-stat-users" />
        <Stat icon={Activity} label="Visits" value={s.sessions} testid="an-stat-sessions" />
        <Stat icon={Timer} label="Avg visit" value={fmtMs(s.avg_session_ms)} testid="an-stat-avg" />
        <Stat icon={MousePointerClick} label="Clicks" value={s.clicks} testid="an-stat-clicks" />
        <Stat icon={Flame} label="Rage / dead" value={`${s.rage_clicks} / ${s.dead_clicks}`} testid="an-stat-frustration" />
        <Stat icon={Smartphone} label="Mobile visits" value={`${s.devices.mobile} of ${s.sessions}`} testid="an-stat-mobile" />
      </div>
      <div className="card overflow-x-auto">
        <table className="w-full text-sm" data-testid="an-pages-table">
          <thead><tr className="text-left text-xs uppercase tracking-wider text-ink-soft border-b border-line">
            <th className="px-4 py-3">Page</th><th className="px-4 py-3">Views</th><th className="px-4 py-3">Avg time</th>
            <th className="px-4 py-3">Clicks</th><th className="px-4 py-3">Frustration</th><th className="px-4 py-3" />
          </tr></thead>
          <tbody>
            {s.pages.map((p) => (
              <tr key={p.path} className="border-b border-line last:border-0">
                <td className="px-4 py-2.5 font-mono text-xs">{p.path}</td>
                <td className="px-4 py-2.5">{p.views}</td>
                <td className="px-4 py-2.5">{fmtMs(p.avg_ms)}</td>
                <td className="px-4 py-2.5">{p.clicks}</td>
                <td className={`px-4 py-2.5 ${p.frustration ? "text-terracotta font-semibold" : ""}`}>{p.frustration}</td>
                <td className="px-4 py-2.5 text-right">
                  <button onClick={() => go("heatmaps", { path: p.path })} className="text-xs font-medium text-forest underline" data-testid={`an-heatmap-link-${p.path}`}>Heatmap</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
