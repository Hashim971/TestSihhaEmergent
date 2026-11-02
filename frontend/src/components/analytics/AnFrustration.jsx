import React from "react";
import { PlayCircle } from "lucide-react";
import { useAnalytics, Loading, Empty } from "./shared";
import { ago } from "../admin/UserDetailModal";

export function AnFrustration({ filters, onWatch }) {
  const rows = useAnalytics("frustration", filters);
  if (rows === null) return <Loading />;
  if (rows === false) return <Empty>Could not load alerts.</Empty>;
  if (!rows.length) return <Empty testid="an-frustration-empty">No rage or dead clicks in this period.</Empty>;
  return (
    <div className="space-y-2" data-testid="analytics-frustration">
      <p className="text-sm text-ink-soft">Rage click = 3 fast taps in the same spot. Dead click = a tap on something that isn't clickable.</p>
      {rows.map((r, i) => (
        <div key={i} className="card px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-2" data-testid={`an-frustration-row-${i}`}>
          <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-md border w-fit ${r.type === "rage" ? "bg-red-50 text-red-700 border-red-200" : "bg-amber-50 text-amber-700 border-amber-200"}`}>
            {r.type === "rage" ? "Rage click" : "Dead click"}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{r.target || "Unknown element"}</p>
            <p className="text-xs text-ink-soft font-mono truncate">{r.path} · {r.count}× by {r.users} {r.users === 1 ? "person" : "people"} · last {ago(r.last_at)}</p>
          </div>
          <button onClick={() => onWatch(r.session_id, r.t)} className="btn-outline !py-1.5 text-xs w-fit" data-testid={`an-frustration-watch-${i}`}>
            <PlayCircle className="h-4 w-4" /> Watch
          </button>
        </div>
      ))}
    </div>
  );
}
