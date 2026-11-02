import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Eye, EyeOff, Star } from "lucide-react";
import { api } from "../../lib/api";
import { Stars } from "../RecentVisits";

export function RatingsTab({ listUrl, patchUrl }) {
  const [rows, setRows] = useState(null);
  useEffect(() => { api.get(listUrl).then(({ data }) => setRows(data)).catch(() => setRows([])); }, [listUrl]);

  const toggle = async (r) => {
    try {
      const { data } = await api.patch(patchUrl(r.rating_id), { hidden: !r.hidden });
      setRows((list) => list.map((x) => (x.rating_id === r.rating_id ? data : x)));
      toast.success(data.hidden ? "Rating hidden from patients" : "Rating visible again");
    } catch {
      toast.error("Could not update the rating");
    }
  };

  if (!rows) return <p className="text-sm text-ink-soft">Loading…</p>;
  const visible = rows.filter((r) => !r.hidden);
  const avg = visible.length ? (visible.reduce((s, r) => s + r.stars, 0) / visible.length).toFixed(1) : null;
  return (
    <div className="card p-6 space-y-4" data-testid="ratings-tab">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold flex items-center gap-2"><Star className="h-4 w-4 text-forest" /> Patient ratings</h2>
        {avg && <span className="inline-flex items-center gap-2 text-sm" data-testid="ratings-average"><Stars value={avg} /> <bdi>{avg}</bdi> · <bdi>{visible.length}</bdi></span>}
      </div>
      <p className="text-xs text-ink-soft">Ratings are published straight away. Hide anything abusive or identifying — hidden ratings don't count towards the score.</p>
      {rows.length === 0 && <p className="text-sm text-ink-soft" data-testid="ratings-empty">No ratings yet.</p>}
      <div className="divide-y divide-line">
        {rows.map((r) => (
          <div key={r.rating_id} className={`py-3 flex gap-3 ${r.hidden ? "opacity-50" : ""}`} data-testid={`rating-${r.rating_id}`}>
            <div className="flex-1 min-w-0">
              <p className="text-sm flex flex-wrap items-center gap-2"><Stars value={r.stars} size="h-3.5 w-3.5" /> <bdi className="font-medium">{r.patient_display}</bdi>
                <span className="text-xs text-ink-soft">· <bdi>{r.doctor_name}</bdi> · {new Date(r.updated_at).toLocaleDateString()}</span></p>
              {r.comment && <p className="text-sm text-ink-soft mt-1">{r.comment}</p>}
            </div>
            <button onClick={() => toggle(r)} className="btn-outline !py-1 !px-2.5 text-xs h-fit" data-testid={`rating-toggle-${r.rating_id}`}>
              {r.hidden ? <><Eye className="h-3.5 w-3.5" /> Show</> : <><EyeOff className="h-3.5 w-3.5" /> Hide</>}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
