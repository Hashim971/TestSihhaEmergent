import React from "react";
import { AlertTriangle, RefreshCw, Search, BadgeCheck } from "lucide-react";

const tone = (days) => (days <= 3 ? "text-terracotta" : "text-forest");

export function RefillsDue({ refills, onReorder, onSearch, busyId }) {
  const due = refills?.due || [];
  const upcoming = refills?.upcoming || [];
  if (!refills) return null;

  return (
    <div className="card p-6" data-testid="refills-due">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <RefreshCw className="h-4 w-4 text-forest" /> Refills due
          </h2>
          <p className="text-xs text-ink-soft mt-0.5">
            Worked out from your pack size and the doses you logged — nothing is ordered without your say.
          </p>
        </div>
        {due.length === 0 && (
          <span className="text-xs text-ink-soft" data-testid="no-refills-due">Nothing runs out this week</span>
        )}
      </div>

      <div className="mt-4 space-y-3">
        {due.map((row) => (
          <div key={row.medication_id} className="border border-line rounded-xl px-4 py-3"
            data-testid={`refill-row-${row.medication_id}`}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-medium text-sm">
                  {row.name} <span className="text-ink-soft">· {row.dosage}</span>
                </p>
                <p className={`text-xs font-semibold mt-0.5 ${tone(row.days_remaining)}`}
                  data-testid={`refill-days-${row.medication_id}`}>
                  {row.days_remaining <= 3 && <AlertTriangle className="h-3 w-3 inline mr-1 -mt-0.5" />}
                  {row.days_remaining} day{row.days_remaining === 1 ? "" : "s"} left
                  {row.projected_runout_date && ` · runs out ${row.projected_runout_date}`}
                  {row.adherence_percent != null && ` · ${row.adherence_percent}% adherence`}
                </p>
              </div>
              {row.offers?.length > 0 ? (
                <span className="text-xs text-ink-soft">Confirm the product below before adding it</span>
              ) : (
                <button onClick={() => onSearch(row.search_query)} className="btn-outline !py-1.5 !px-3 text-xs"
                  data-testid={`refill-search-${row.medication_id}`}>
                  <Search className="h-3.5 w-3.5" /> Find this
                </button>
              )}
            </div>

            {row.offers?.length > 0 && (
              <div className="mt-3 space-y-2" data-testid={`refill-offers-${row.medication_id}`}>
                {row.offers.map((offer) => (
                  <div key={offer.item.item_id}
                    className="flex flex-wrap items-center justify-between gap-2 border border-line rounded-lg px-3 py-2 bg-sand/60">
                    <div>
                      <p className="text-sm font-medium flex items-center gap-2">
                        {offer.item.name_en}
                        <span className="text-ink-soft font-normal">{offer.item.name_ar}</span>
                        {offer.sponsored && (
                          <span className="text-[10px] uppercase tracking-wider bg-forest/10 text-forest px-1.5 py-0.5 rounded-full"
                            data-testid="sponsored-badge">Sponsored</span>
                        )}
                      </p>
                      <p className="text-xs text-ink-soft mt-0.5 flex items-center gap-1">
                        <BadgeCheck className="h-3 w-3" /> {offer.pharmacy.name_en} · SFDA {offer.pharmacy.sfda_license}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-semibold">{offer.item.price_sar} SAR</span>
                      <button onClick={() => onReorder(offer.item)} disabled={busyId === offer.item.item_id}
                        data-testid={`reorder-btn-${offer.item.item_id}`} className="btn-primary !py-1.5 !px-3 text-xs">
                        Reorder
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}

        {upcoming.length > 0 && (
          <div className="pt-2" data-testid="refills-upcoming">
            <p className="text-[10px] uppercase tracking-[0.15em] text-ink-soft mb-1">Coming up</p>
            {upcoming.map((row) => (
              <p key={row.medication_id} className="text-sm text-ink-soft"
                data-testid={`refill-upcoming-${row.medication_id}`}>
                {row.name} · {row.days_remaining} days left
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
