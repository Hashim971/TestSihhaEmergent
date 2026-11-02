import React from "react";
import { ArrowRight, LogIn, LogOut } from "lucide-react";
import { useAnalytics, Loading, Empty } from "./shared";

const List = ({ title, icon: Icon, rows, render, testid }) => (
  <div className="card p-5" data-testid={testid}>
    <h3 className="font-semibold text-sm flex items-center gap-2 mb-3"><Icon className="h-4 w-4 text-forest" /> {title}</h3>
    {rows.length === 0 ? <p className="text-sm text-ink-soft">Nothing yet.</p> : (
      <ul className="space-y-2 text-sm">{rows.map(render)}</ul>
    )}
  </div>
);

export function AnJourneys({ filters }) {
  const j = useAnalytics("journeys", filters);
  if (j === null) return <Loading />;
  if (j === false) return <Empty>Could not load journeys.</Empty>;
  if (!j.sessions) return <Empty testid="an-journeys-empty">No page views recorded in this period.</Empty>;
  const max = j.transitions[0]?.count || 1;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4" data-testid="analytics-journeys">
      <div className="lg:col-span-2">
        <List title={`Most common next steps (${j.sessions} visits)`} icon={ArrowRight} rows={j.transitions} testid="an-transitions"
          render={(t, i) => (
            <li key={i} className="relative rounded-lg px-3 py-2 bg-sand/50 overflow-hidden">
              <span className="absolute inset-y-0 left-0 bg-sage/40" style={{ width: `${(t.count / max) * 100}%` }} />
              <span className="relative flex items-center justify-between gap-2 font-mono text-xs">
                <span className="truncate">{t.from} <ArrowRight className="inline h-3 w-3" /> {t.to}</span><b>{t.count}</b>
              </span>
            </li>
          )} />
      </div>
      <div className="space-y-4">
        <List title="Where visits start" icon={LogIn} rows={j.entries} testid="an-entries"
          render={(r) => <li key={r.path} className="flex justify-between font-mono text-xs"><span className="truncate">{r.path}</span><b>{r.count}</b></li>} />
        <List title="Where people leave" icon={LogOut} rows={j.exits} testid="an-exits"
          render={(r) => <li key={r.path} className="flex justify-between font-mono text-xs"><span className="truncate">{r.path}</span><b className="text-terracotta">{r.count}</b></li>} />
      </div>
    </div>
  );
}
