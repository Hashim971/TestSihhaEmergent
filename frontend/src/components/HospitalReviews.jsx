import React, { useEffect, useState } from "react";
import { Modal } from "./ConfirmDialog";
import { Stars } from "./RecentVisits";
import { api } from "../lib/api";

export function HospitalReviews({ hospital, onClose }) {
  const [data, setData] = useState(null);
  useEffect(() => { api.get(`/care/hospitals/${hospital.account_id}/reviews`).then(({ data: d }) => setData(d)).catch(() => setData({ count: 0, reviews: [], breakdown: {} })); }, [hospital.account_id]);
  return (
    <Modal onClose={onClose} testid="hospital-reviews-dialog">
      <h2 className="text-lg font-semibold pe-8">{hospital.name}</h2>
      {!data && <p className="text-sm text-ink-soft mt-3">Loading…</p>}
      {data && (
        <>
          <div className="flex items-center gap-3 mt-2">
            <Stars value={data.average} size="h-5 w-5" />
            <span className="text-sm" data-testid="reviews-summary">{data.average ? <><bdi>{data.average}</bdi> · <bdi>{data.count}</bdi> ratings</> : "No ratings yet"}</span>
          </div>
          {data.count > 0 && (
            <div className="mt-3 space-y-1">
              {Object.entries(data.breakdown).map(([s, n]) => (
                <div key={s} className="flex items-center gap-2 text-xs">
                  <span className="w-3">{s}</span>
                  <div className="flex-1 h-2 rounded-full bg-sand overflow-hidden"><div className="h-full bg-amber-400" style={{ width: `${(n / data.count) * 100}%` }} /></div>
                  <span className="w-6 text-end text-ink-soft">{n}</span>
                </div>
              ))}
            </div>
          )}
          <div className="mt-4 space-y-3">
            {data.reviews.length === 0 && data.count > 0 && <p className="text-sm text-ink-soft">No written comments yet.</p>}
            {data.reviews.map((r) => (
              <div key={r.rating_id} className="border border-line rounded-xl p-3" data-testid={`review-${r.rating_id}`}>
                <p className="text-xs flex items-center gap-2"><Stars value={r.stars} size="h-3 w-3" /> <bdi className="font-semibold">{r.patient_display}</bdi> · <bdi>{r.doctor_name}</bdi></p>
                <p className="text-sm mt-1">{r.comment}</p>
              </div>
            ))}
          </div>
        </>
      )}
    </Modal>
  );
}
