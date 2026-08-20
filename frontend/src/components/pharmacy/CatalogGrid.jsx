import React from "react";
import { Lock, FileText, Store } from "lucide-react";

const STOCK = {
  in_stock: { label: "In stock", cls: "text-forest" },
  low: { label: "Low stock", cls: "text-terracotta" },
  out_of_stock: { label: "Out of stock", cls: "text-ink-soft" },
};

export function CatalogGrid({ items, onAdd, busyId }) {
  if (!items) return <div className="card p-6 text-sm text-ink-soft">Loading products…</div>;
  if (items.length === 0) {
    return (
      <div className="card p-10 text-center" data-testid="catalog-empty">
        <Store className="h-7 w-7 text-forest mx-auto" />
        <p className="mt-3 font-semibold">Nothing matches that search</p>
        <p className="text-sm text-ink-soft mt-1">Try the generic name, or browse a category.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4" data-testid="catalog-grid">
      {items.map((item) => {
        const stock = STOCK[item.stock_status] || STOCK.in_stock;
        return (
          <div key={item.item_id} className="card p-5 flex flex-col" data-testid={`catalog-item-${item.item_id}`}>
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-semibold text-sm leading-snug">{item.name_en}</p>
                <p className="text-sm text-ink-soft" dir="rtl">{item.name_ar}</p>
              </div>
              {item.pharmacy?.sponsored && (
                <span className="text-[10px] uppercase tracking-wider bg-forest/10 text-forest px-1.5 py-0.5 rounded-full shrink-0"
                  data-testid="sponsored-badge">Sponsored</span>
              )}
            </div>

            <p className="text-xs text-ink-soft mt-1.5">
              {item.form} · {item.strength} · pack of {item.pack_size}
              {item.generic_name ? ` · ${item.generic_name}` : ""}
            </p>

            <div className="flex flex-wrap items-center gap-2 mt-2">
              {item.is_controlled ? (
                <span className="text-[10px] uppercase tracking-wider bg-terracotta/10 text-terracotta px-2 py-0.5 rounded-full flex items-center gap-1"
                  data-testid={`controlled-badge-${item.item_id}`}>
                  <Lock className="h-3 w-3" /> In-store only
                </span>
              ) : item.requires_prescription ? (
                <span className="text-[10px] uppercase tracking-wider bg-sage/30 text-forest px-2 py-0.5 rounded-full flex items-center gap-1"
                  data-testid={`rx-badge-${item.item_id}`}>
                  <FileText className="h-3 w-3" /> Prescription only
                </span>
              ) : null}
              <span className={`text-[10px] uppercase tracking-wider ${stock.cls}`}>{stock.label}</span>
            </div>

            {item.pharmacy && (
              <p className="text-xs text-ink-soft mt-3 leading-relaxed" data-testid={`item-pharmacy-${item.item_id}`}>
                {item.pharmacy.name_en} — SFDA {item.pharmacy.sfda_license} · MOH {item.pharmacy.moh_license} ·
                CR {item.pharmacy.cr_number}
              </p>
            )}

            <div className="mt-auto pt-4 flex items-center justify-between gap-2">
              <span className="font-heading text-lg font-bold text-forest">
                {item.price_sar ? `${item.price_sar} SAR` : "In-store price"}
              </span>
              {item.is_controlled ? (
                <span className="text-xs text-ink-soft text-right max-w-[55%]"
                  data-testid={`controlled-notice-${item.item_id}`}>
                  Controlled medicine — available in-store with a prescription. It cannot be ordered online.
                </span>
              ) : item.orderable ? (
                <div className="flex items-center gap-2">
                  {item.pharmacy?.directions_url && (
                    <a href={item.pharmacy.directions_url} target="_blank" rel="noreferrer"
                      data-testid={`directions-${item.item_id}`} className="btn-outline !py-1.5 !px-3 text-xs">
                      Directions
                    </a>
                  )}
                  <button onClick={() => onAdd(item)} disabled={busyId === item.item_id || item.stock_status === "out_of_stock"}
                    data-testid={`add-to-cart-${item.item_id}`}
                    className={`btn-primary !py-1.5 !px-3 text-xs ${item.stock_status === "out_of_stock" ? "opacity-40 cursor-not-allowed" : ""}`}>
                    Add
                  </button>
                </div>
              ) : (
                <span className="text-xs text-terracotta text-right max-w-[55%]"
                  data-testid={`not-orderable-${item.item_id}`}>
                  {item.violations?.[0]?.message}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
