import React from "react";
import { MapPin, Clock, BadgeCheck } from "lucide-react";

export function PharmacyList({ pharmacies }) {
  if (!pharmacies?.length) return null;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="pharmacy-list">
      {pharmacies.map((p) => (
        <div key={p.pharmacy_id} className="card p-5" data-testid={`pharmacy-${p.pharmacy_id}`}>
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="font-semibold">{p.name_en}</p>
              <p className="text-sm text-ink-soft" dir="rtl">{p.name_ar}</p>
            </div>
            {p.sponsored && (
              <span className="text-[10px] uppercase tracking-wider bg-forest/10 text-forest px-1.5 py-0.5 rounded-full"
                data-testid="sponsored-badge">Sponsored</span>
            )}
          </div>

          <p className="text-xs text-ink-soft mt-3 flex items-start gap-1.5" data-testid={`licences-${p.pharmacy_id}`}>
            <BadgeCheck className="h-3.5 w-3.5 mt-0.5 shrink-0 text-forest" />
            SFDA {p.sfda_license} · MOH {p.moh_license} · CR {p.cr_number}
          </p>

          <div className="mt-3 space-y-2">
            {(p.branches || []).map((b) => (
              <div key={b.branch_id} className="border border-line rounded-lg px-3 py-2">
                <p className="text-sm font-medium flex items-center gap-1.5">
                  <MapPin className="h-3.5 w-3.5 text-forest" /> {b.city}
                </p>
                <p className="text-xs text-ink-soft mt-0.5 flex items-center gap-1.5">
                  <Clock className="h-3 w-3" /> {b.hours}
                </p>
                {b.directions_url && (
                  <a href={b.directions_url} target="_blank" rel="noreferrer"
                    data-testid={`branch-directions-${b.branch_id}`}
                    className="btn-outline !py-1 !px-2.5 text-[11px] mt-2 inline-flex">Directions</a>
                )}
              </div>
            ))}
          </div>

          <p className="text-[10px] uppercase tracking-wider text-ink-soft mt-3">
            {p.fulfilment_mode === "handoff" ? "Checkout on the pharmacy's own site" : "Order through Sihha, collect in store"}
          </p>
        </div>
      ))}
    </div>
  );
}
