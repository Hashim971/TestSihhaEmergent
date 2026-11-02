import React, { useState } from "react";
import { PlayCircle, Monitor, Smartphone } from "lucide-react";
import { useAnalytics, Loading, Empty, fmtMs } from "./shared";
import { ago } from "../admin/UserDetailModal";

export function AnReplays({ filters, onWatch }) {
  const [frustrated, setFrustrated] = useState(false);
  const rows = useAnalytics("replays", filters, { frustrated });
  return (
    <div className="space-y-3" data-testid="analytics-replays">
      <label className="inline-flex items-center gap-2 text-sm text-ink-soft cursor-pointer">
        <input type="checkbox" checked={frustrated} onChange={(e) => setFrustrated(e.target.checked)} className="accent-[#1E3F2A]" data-testid="an-replays-frustrated-toggle" />
        Only visits with rage or dead clicks
      </label>
      {rows === null ? <Loading /> : rows === false ? <Empty>Could not load recordings.</Empty> : !rows.length ? (
        <Empty testid="an-replays-empty">No recordings in this period.</Empty>
      ) : rows.map((r) => (
        <div key={r.session_id} className="card px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-3" data-testid={`an-replay-row-${r.session_id}`}>
          <div className="flex items-center gap-2 text-ink-soft">{r.device === "mobile" ? <Smartphone className="h-4 w-4" /> : <Monitor className="h-4 w-4" />}</div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{r.email || r.user_id} <span className="text-xs text-ink-soft capitalize">· {r.role}</span></p>
            <p className="text-xs text-ink-soft truncate">{ago(r.last_at)} · {fmtMs(r.duration_ms)} · {r.pageviews || 0} pages{r.pages?.length ? ` · ${r.pages.slice(0, 4).join(", ")}` : ""}</p>
          </div>
          {(r.rage > 0 || r.dead > 0) && <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md border bg-red-50 text-red-700 border-red-200 w-fit">{r.rage} rage · {r.dead} dead</span>}
          <button onClick={() => onWatch(r.session_id)} className="btn-primary !py-1.5 text-xs w-fit" data-testid={`an-replay-watch-${r.session_id}`}>
            <PlayCircle className="h-4 w-4" /> Watch
          </button>
        </div>
      ))}
    </div>
  );
}
