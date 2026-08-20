import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { ReceiptText, ExternalLink, MapPin, BadgeCheck } from "lucide-react";

const CANCELLABLE = ["draft", "awaiting_pharmacist_verification", "confirmed"];

const LABEL = {
  handed_off: "Handed to the pharmacy",
  awaiting_pharmacist_verification: "Waiting on the pharmacist",
  confirmed: "Confirmed by the pharmacy",
  rejected: "Rejected by the pharmacy",
  cancelled: "Cancelled",
  draft: "Draft",
};

export default function PharmacyOrders() {
  const { activeProfile } = useAuth();
  const [orders, setOrders] = useState(null);

  const load = useCallback(() => api.get("/pharmacy/orders", { params: { profile_id: activeProfile.id } })
    .then(({ data }) => setOrders(data)).catch(() => setOrders([])), [activeProfile.id]);

  useEffect(() => { load(); }, [load]);

  const cancel = async (orderId) => {
    try {
      await api.post(`/pharmacy/orders/${orderId}/cancel`);
      toast.success("Order cancelled");
      load();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Could not cancel this order");
    }
  };

  return (
    <div className="space-y-6 fade-up max-w-4xl" data-testid="pharmacy-orders-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Pharmacy orders</h1>
          <p className="text-ink-soft mt-1">Every order is dispensed by the licensed partner shown on it.</p>
        </div>
        <Link to="/pharmacy" className="btn-outline" data-testid="back-to-pharmacy-btn">Back to pharmacy</Link>
      </div>

      {orders === null && <div className="card p-6 text-sm text-ink-soft">Loading your orders…</div>}

      {orders?.length === 0 && (
        <div className="card p-10 text-center" data-testid="orders-empty">
          <ReceiptText className="h-7 w-7 text-forest mx-auto" />
          <p className="mt-3 font-semibold">No orders yet</p>
          <p className="text-sm text-ink-soft mt-1">Anything you order from a partner pharmacy shows up here.</p>
        </div>
      )}

      {(orders || []).map((order) => (
        <div key={order.order_id} className="card p-6" data-testid={`order-${order.order_id}`}>
          <div className="flex flex-wrap items-start justify-between gap-3 pb-3 border-b border-line">
            <div>
              <p className="font-semibold">{order.pharmacy_snapshot?.name_en}</p>
              <p className="text-xs text-ink-soft mt-0.5 flex items-center gap-1.5"
                data-testid={`order-licences-${order.order_id}`}>
                <BadgeCheck className="h-3.5 w-3.5 text-forest" />
                SFDA {order.pharmacy_snapshot?.sfda_license} · MOH {order.pharmacy_snapshot?.moh_license} ·
                CR {order.pharmacy_snapshot?.cr_number}
              </p>
            </div>
            <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
              order.status === "cancelled" || order.status === "rejected"
                ? "bg-terracotta/10 text-terracotta" : "bg-sage/30 text-forest"}`}
              data-testid={`order-status-${order.order_id}`}>
              {LABEL[order.status] || order.status}
            </span>
          </div>

          <div className="mt-3 space-y-1.5">
            {order.items.map((line) => (
              <div key={line.item_id} className="flex items-center justify-between text-sm">
                <span>{line.name_en} <span className="text-ink-soft">× {line.qty}</span></span>
                <span className="text-ink-soft">{(line.qty * line.price_sar).toFixed(2)} SAR</span>
              </div>
            ))}
            <div className="flex items-center justify-between text-sm font-semibold pt-1.5">
              <span>Total</span>
              <span data-testid={`order-total-${order.order_id}`}>{order.total_sar} SAR</span>
            </div>
          </div>

          <div className="mt-4">
            <p className="text-[10px] uppercase tracking-[0.15em] text-ink-soft mb-2">Timeline</p>
            <ol className="space-y-2" data-testid={`order-timeline-${order.order_id}`}>
              {order.status_history.map((entry, i) => (
                <li key={i} className="flex gap-3">
                  <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-forest shrink-0" />
                  <div>
                    <p className="text-sm font-medium">{LABEL[entry.status] || entry.status}</p>
                    <p className="text-xs text-ink-soft">
                      {new Date(entry.at).toLocaleString()}{entry.note ? ` — ${entry.note}` : ""}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            {order.handoff_url && (
              <a href={order.handoff_url} target="_blank" rel="noreferrer" className="btn-outline !py-1.5 !px-3 text-xs"
                data-testid={`order-handoff-${order.order_id}`}>
                <ExternalLink className="h-3.5 w-3.5" /> Open at the pharmacy
              </a>
            )}
            {order.pickup_branch?.directions_url && (
              <a href={order.pickup_branch.directions_url} target="_blank" rel="noreferrer"
                className="btn-outline !py-1.5 !px-3 text-xs" data-testid={`order-directions-${order.order_id}`}>
                <MapPin className="h-3.5 w-3.5" /> Directions to {order.pickup_branch.city}
              </a>
            )}
            {CANCELLABLE.includes(order.status) && (
              <button onClick={() => cancel(order.order_id)} data-testid={`cancel-order-${order.order_id}`}
                className="btn-outline !py-1.5 !px-3 text-xs !border-terracotta !text-terracotta">
                Cancel order
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
