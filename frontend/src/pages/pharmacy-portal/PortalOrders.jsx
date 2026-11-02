import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Inbox, FileImage } from "lucide-react";
import { api, API } from "../../lib/api";
import { OrderThread } from "../../components/pharmacy/OrderThread";
import { ORDER_LABEL } from "../../lib/orderStatus";

const ACTIONS = {
  confirmed: { label: "Accept", cls: "btn-primary" },
  rejected: { label: "Reject", cls: "btn-outline !text-terracotta !border-terracotta" },
  ready_for_pickup: { label: "Ready for pickup", cls: "btn-primary" },
  out_for_delivery: { label: "Out for delivery", cls: "btn-outline" },
  completed: { label: "Mark handed over", cls: "btn-primary" },
};
const VIEWS = [["open", "Open"], ["done", "Closed"], ["all", "All"]];

export default function PortalOrders() {
  const [view, setView] = useState("open");
  const [orders, setOrders] = useState(null);

  const load = useCallback(() => api.get("/pharmacy-portal/orders", { params: { view } })
    .then(({ data }) => setOrders(data)).catch(() => setOrders([])), [view]);
  useEffect(() => { setOrders(null); load(); }, [load]);

  return (
    <div className="space-y-6 fade-up" data-testid="portal-orders-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Order inbox</h1>
          <p className="text-ink-soft mt-1">Check each prescription, accept or reject it, and keep the patient posted.</p>
        </div>
        <div className="flex rounded-full border border-line p-1 bg-white">
          {VIEWS.map(([k, label]) => (
            <button key={k} onClick={() => setView(k)} data-testid={`portal-view-${k}`}
              className={`px-4 py-1.5 rounded-full text-sm font-medium ${view === k ? "bg-forest text-white" : "text-ink-soft"}`}>{label}</button>
          ))}
        </div>
      </div>
      {orders === null && <div className="card p-6 text-sm text-ink-soft">Loading orders…</div>}
      {orders?.length === 0 && (
        <div className="card p-10 text-center" data-testid="portal-orders-empty">
          <Inbox className="h-7 w-7 text-forest mx-auto" />
          <p className="mt-3 font-semibold">No {view === "open" ? "open " : ""}orders</p>
          <p className="text-sm text-ink-soft mt-1">New orders from patients land here.</p>
        </div>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {(orders || []).map((o) => <PortalOrderCard key={o.order_id} order={o} onChange={load} />)}
      </div>
    </div>
  );
}

function PortalOrderCard({ order, onChange }) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  const move = async (status) => {
    if (status === "rejected" && !note.trim()) return toast.error("Write the reason in the note first");
    setBusy(true);
    try {
      await api.post(`/pharmacy-portal/orders/${order.order_id}/status`, { status, note });
      toast.success(`Order ${ORDER_LABEL[status]?.toLowerCase() || status} — the patient was notified`);
      setNote("");
      onChange();
    } catch (e) {
      toast.error(e?.response?.data?.detail?.[0]?.msg || e?.response?.data?.detail || "Could not update the order");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card p-5" data-testid={`portal-order-${order.order_id}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold">{order.patient_name}</p>
          <p className="text-xs text-ink-soft font-mono">{order.order_id} · {new Date(order.created_at).toLocaleString()}</p>
        </div>
        <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-sage/30 text-forest" data-testid={`portal-order-status-${order.order_id}`}>{ORDER_LABEL[order.status] || order.status}</span>
      </div>
      <div className="mt-3 space-y-1 text-sm">
        {order.items.map((l) => (
          <div key={l.item_id} className="flex justify-between"><span>{l.name_en} <span className="text-ink-soft">× {l.qty}</span></span><span className="text-ink-soft">{(l.qty * l.price_sar).toFixed(2)} SAR</span></div>
        ))}
        <div className="flex justify-between font-semibold pt-1 border-t border-line"><span>Total</span><span>{order.total_sar} SAR</span></div>
      </div>
      {order.prescription && (
        <p className="mt-3 text-xs flex items-center gap-2" data-testid={`portal-order-rx-${order.order_id}`}>
          <FileImage className="h-3.5 w-3.5 text-forest" /> Prescription attached
          {order.prescription.has_image && (
            <a href={`${API}/pharmacy-portal/orders/${order.order_id}/prescription-image`} target="_blank" rel="noreferrer" className="text-forest underline">View image</a>
          )}
        </p>
      )}
      {order.note && <p className="mt-2 text-xs text-ink-soft">Patient note: “{order.note}”</p>}
      {order.allowed_next.length > 0 && (
        <div className="mt-4 space-y-2">
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder="Note for the patient (required to reject)"
            className="w-full border border-line rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-forest" data-testid={`portal-order-note-${order.order_id}`} />
          <div className="flex flex-wrap gap-2">
            {order.allowed_next.map((s) => (
              <button key={s} disabled={busy} onClick={() => move(s)} className={`${ACTIONS[s].cls} !py-1.5 !px-3 text-xs`} data-testid={`portal-order-${s}-${order.order_id}`}>{ACTIONS[s].label}</button>
            ))}
          </div>
        </div>
      )}
      <OrderThread base={`/pharmacy-portal/orders/${order.order_id}`} me="pharmacy" unread={order.unread_messages} testid={`portal-thread-${order.order_id}`} />
    </div>
  );
}
