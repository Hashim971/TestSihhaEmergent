import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import jsPDF from "jspdf";
import { api } from "../lib/api";
import { toast } from "sonner";
import { FileSignature, Download, ShoppingBag, Lock, Store } from "lucide-react";

export default function Prescriptions() {
  const [rows, setRows] = useState(null);
  const [options, setOptions] = useState({});
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/prescriptions").then(({ data }) => setRows(data)).catch(() => setRows([]));
  }, []);

  const loadOptions = async (id) => {
    try {
      const { data } = await api.get(`/prescriptions/${id}/basket-options`);
      setOptions((prev) => ({ ...prev, [id]: data.proposals }));
    } catch {
      toast.error("Could not check pharmacy availability");
    }
  };

  const addToBasket = async (offer) => {
    try {
      await api.post("/pharmacy/cart/items", { item_id: offer.item.item_id, qty: 1 });
      toast.success(`${offer.item.name_en} added to your basket at ${offer.pharmacy.name_en}`);
      navigate("/pharmacy");
    } catch (e) {
      const violations = e?.response?.data?.detail?.violations;
      if (violations) violations.forEach((v) => toast.error(v.message));
      else toast.error("Could not add that medicine");
    }
  };

  const download = (rx) => {
    const doc = new jsPDF();
    doc.setFontSize(18);
    doc.text("Prescription", 105, 20, { align: "center" });
    doc.setFontSize(10);
    doc.text(`${rx.issued_by_name || "Clinician"}${rx.issued_by_clinic ? ` · ${rx.issued_by_clinic}` : ""}`,
      105, 28, { align: "center" });
    doc.text(`Signed ${new Date(rx.signed_at).toLocaleString()}`, 105, 34, { align: "center" });
    let y = 48;
    if (rx.diagnosis) { doc.text(`Diagnosis: ${rx.diagnosis}`, 15, y); y += 8; }
    rx.items.forEach((item, i) => {
      doc.setFont(undefined, "bold");
      doc.text(`${i + 1}. ${item.drug_name} ${item.strength || ""}`.trim(), 15, y);
      doc.setFont(undefined, "normal");
      y += 6;
      const line = [item.dose, item.frequency, item.duration_days ? `${item.duration_days} days` : "",
        item.quantity ? `qty ${item.quantity}` : "", item.refills ? `${item.refills} refills` : ""]
        .filter(Boolean).join(" · ");
      if (line) { doc.text(line, 20, y); y += 6; }
      if (item.instructions) { doc.text(item.instructions, 20, y, { maxWidth: 170 }); y += 6; }
      if (item.is_controlled) { doc.text("Controlled — dispensed in clinic only", 20, y); y += 6; }
      y += 2;
    });
    if (rx.notes) { doc.text(`Note: ${rx.notes}`, 15, y + 4, { maxWidth: 180 }); }
    doc.setFontSize(8);
    doc.text("Dispensing pharmacist must verify this prescription before dispensing.", 105, 285,
      { align: "center" });
    doc.save("sihha-prescription.pdf");
  };

  return (
    <div className="space-y-6 fade-up max-w-4xl" data-testid="prescriptions-page">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Prescriptions</h1>
        <p className="text-ink-soft mt-1">
          What your doctor prescribed after a visit. A pharmacist still checks it before anything is dispensed.
        </p>
      </div>

      {rows === null && <div className="card p-6 text-sm text-ink-soft">Loading your prescriptions…</div>}
      {rows?.length === 0 && (
        <div className="card p-10 text-center" data-testid="prescriptions-empty">
          <FileSignature className="h-7 w-7 text-forest mx-auto" />
          <p className="mt-3 font-semibold">No prescriptions yet</p>
          <p className="text-sm text-ink-soft mt-1">Anything your doctor signs after a visit appears here.</p>
        </div>
      )}

      {(rows || []).map((rx) => (
        <div key={rx.prescription_id} className="card p-6" data-testid={`prescription-${rx.prescription_id}`}>
          <div className="flex flex-wrap items-start justify-between gap-3 pb-3 border-b border-line">
            <div>
              <p className="font-semibold">{rx.issued_by_name}</p>
              <p className="text-xs text-ink-soft mt-0.5">
                {[rx.issued_by_clinic, rx.diagnosis].filter(Boolean).join(" · ")} ·
                {" "}signed {new Date(rx.signed_at).toLocaleDateString()}
              </p>
              {rx.transmitted_pharmacy_name && (
                <p className="text-xs text-forest mt-1 flex items-center gap-1.5" data-testid="rx-sent-line">
                  <Store className="h-3 w-3" /> Sent to {rx.transmitted_pharmacy_name}
                </p>
              )}
            </div>
            <button onClick={() => download(rx)} className="btn-outline !py-1.5 !px-3 text-xs"
              data-testid={`download-rx-${rx.prescription_id}`}>
              <Download className="h-3.5 w-3.5" /> PDF
            </button>
          </div>

          <div className="mt-3 space-y-2">
            {rx.items.map((item, i) => (
              <div key={i} className="border border-line rounded-lg px-3 py-2" data-testid={`rx-line-${i}`}>
                <p className="text-sm font-medium">
                  {item.drug_name} {item.strength}
                  {item.is_controlled && (
                    <span className="ml-2 text-[10px] uppercase tracking-wider bg-terracotta/10 text-terracotta px-1.5 py-0.5 rounded-full">
                      <Lock className="h-3 w-3 inline -mt-0.5" /> In clinic only
                    </span>
                  )}
                </p>
                <p className="text-xs text-ink-soft mt-0.5">
                  {[item.dose, item.frequency, item.duration_days ? `${item.duration_days} days` : "",
                    item.quantity ? `qty ${item.quantity}` : ""].filter(Boolean).join(" · ")}
                </p>
                {item.instructions && <p className="text-xs mt-0.5">{item.instructions}</p>}
              </div>
            ))}
          </div>

          {rx.notes && <p className="text-sm text-ink-soft mt-3">{rx.notes}</p>}

          <div className="mt-4">
            {!options[rx.prescription_id] ? (
              <button onClick={() => loadOptions(rx.prescription_id)} className="btn-primary !py-1.5 !px-3 text-xs"
                data-testid={`order-rx-${rx.prescription_id}`}>
                <ShoppingBag className="h-3.5 w-3.5" /> Order this at a pharmacy
              </button>
            ) : (
              <div className="space-y-3" data-testid={`rx-options-${rx.prescription_id}`}>
                <p className="text-xs text-ink-soft">
                  Confirm each medicine before it goes in your basket — we never swap one product for another.
                </p>
                {options[rx.prescription_id].map((proposal, i) => (
                  <div key={i} className="border border-line rounded-xl px-3 py-2.5"
                    data-testid={`proposal-${i}`}>
                    <p className="text-sm font-medium">{proposal.drug_name} {proposal.strength}</p>
                    {!proposal.orderable && (
                      <p className="text-xs text-terracotta mt-1" data-testid={`proposal-blocked-${i}`}>
                        {proposal.reason}
                      </p>
                    )}
                    {proposal.offers.map((offer) => (
                      <div key={offer.item.item_id}
                        className="flex flex-wrap items-center justify-between gap-2 mt-2 bg-sand/60 rounded-lg px-3 py-2">
                        <div>
                          <p className="text-sm">
                            {offer.item.name_en}
                            {offer.sponsored && (
                              <span className="ml-2 text-[10px] uppercase tracking-wider bg-forest/10 text-forest px-1.5 py-0.5 rounded-full">
                                Sponsored
                              </span>
                            )}
                          </p>
                          <p className="text-xs text-ink-soft">
                            {offer.pharmacy.name_en} · SFDA {offer.pharmacy.sfda_license}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold">{offer.item.price_sar} SAR</span>
                          <button onClick={() => addToBasket(offer)} className="btn-primary !py-1.5 !px-3 text-xs"
                            data-testid={`confirm-offer-${offer.item.item_id}`}>
                            This one
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
