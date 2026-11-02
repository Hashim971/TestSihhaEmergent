import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Star, History } from "lucide-react";
import { api } from "../lib/api";
import { Modal } from "./ConfirmDialog";

export function Stars({ value, size = "h-4 w-4", onPick, testid }) {
  return (
    <span className="inline-flex gap-0.5" data-testid={testid}>
      {[1, 2, 3, 4, 5].map((n) => {
        const icon = <Star className={`${size} ${n <= Math.round(value || 0) ? "fill-amber-400 text-amber-400" : "text-line"}`} />;
        return onPick ? (
          <button key={n} type="button" onClick={() => onPick(n)} data-testid={`${testid}-${n}`} aria-label={`${n} stars`}
            className="p-0.5 rounded hover:scale-110" style={{ transition: "transform 0.15s ease" }}>{icon}</button>
        ) : <span key={n}>{icon}</span>;
      })}
    </span>
  );
}

export function RecentVisits() {
  const [visits, setVisits] = useState(null);
  const [rating, setRating] = useState(null);
  const load = () => api.get("/my-visits").then(({ data }) => setVisits(data.past.filter((v) => v.status === "completed"))).catch(() => setVisits([]));
  useEffect(() => { load(); }, []);

  if (!visits || visits.length === 0) return null;
  return (
    <div className="card p-5" data-testid="recent-visits">
      {rating && <RateVisitDialog visit={rating} onClose={() => setRating(null)} onSaved={load} />}
      <h2 className="text-sm font-semibold flex items-center gap-2 mb-3"><History className="h-4 w-4 text-forest" /> Your recent visits</h2>
      <div className="space-y-2">
        {visits.slice(0, 5).map((v) => (
          <div key={v.encounter_id} className="border border-line rounded-xl px-4 py-3 flex flex-wrap items-center justify-between gap-3" data-testid={`recent-visit-${v.encounter_id}`}>
            <div>
              <p className="text-sm font-medium"><bdi>{v.doctor?.name}</bdi>{v.doctor?.specialty ? <span className="text-ink-soft"> · {v.doctor.specialty}</span> : null}</p>
              <p className="text-xs text-ink-soft">{new Date(v.scheduled_at).toLocaleDateString()}</p>
            </div>
            {v.my_rating ? (
              <button onClick={() => setRating(v)} className="inline-flex items-center gap-2 text-xs text-ink-soft" data-testid={`edit-rating-${v.encounter_id}`}>
                <Stars value={v.my_rating.stars} size="h-3.5 w-3.5" /> Edit
              </button>
            ) : v.can_rate ? (
              <button onClick={() => setRating(v)} className="btn-outline !py-1.5 !px-3 text-xs" data-testid={`rate-visit-${v.encounter_id}`}><Star className="h-3.5 w-3.5" /> Rate this visit</button>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function RateVisitDialog({ visit, onClose, onSaved }) {
  const [stars, setStars] = useState(visit.my_rating?.stars || 0);
  const [comment, setComment] = useState(visit.my_rating?.comment || "");
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      await api.post(`/encounters/${visit.encounter_id}/rating`, { stars, comment });
      toast.success("Thanks — your rating helps other patients choose");
      onSaved();
      onClose();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save your rating");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal onClose={onClose} testid="rate-visit-dialog">
      <h2 className="text-lg font-semibold pe-8">How was your visit?</h2>
      <p className="text-sm text-ink-soft mt-1"><bdi>{visit.doctor?.name}</bdi> · {new Date(visit.scheduled_at).toLocaleDateString()}</p>
      <div className="mt-4"><Stars value={stars} size="h-8 w-8" onPick={setStars} testid="rate-stars" /></div>
      <textarea rows={3} maxLength={500} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Anything other patients should know? (optional)"
        className="mt-4 w-full border border-line rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest" data-testid="rate-comment" />
      <p className="text-[11px] text-ink-soft mt-1">Shown publicly with your first name and last initial.</p>
      <button disabled={!stars || busy} onClick={save} className="btn-primary w-full justify-center mt-4 disabled:opacity-50" data-testid="rate-submit">{busy ? "Saving…" : "Submit rating"}</button>
    </Modal>
  );
}
