import React, { useState } from "react";
import { toast } from "sonner";
import { Modal } from "../../components/ConfirmDialog";
import { api } from "../../lib/api";

const EMPTY = {
  sku: "", name_en: "", name_ar: "", generic_name: "", form: "", strength: "", category: "otc", requires_prescription: false,
  sfda_registration_number: "", days_supply: "", pack_size: "", price_sar: "", stock_status: "in_stock", active: true,
};
const CATEGORIES = [["otc", "Over the counter"], ["prescription", "Prescription medicine"], ["supplement", "Supplement"], ["device", "Device"], ["personal_care", "Personal care"]];

export function ProductForm({ item, onClose, onSaved }) {
  const [form, setForm] = useState(() => ({ ...EMPTY, ...(item || {}), days_supply: item?.days_supply ?? "", pack_size: item?.pack_size ?? "" }));
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    const body = { ...Object.fromEntries(Object.keys(EMPTY).map((k) => [k, form[k]])), price_sar: Number(form.price_sar),
      days_supply: form.days_supply === "" ? null : Number(form.days_supply), pack_size: form.pack_size === "" ? null : Number(form.pack_size) };
    try {
      if (item) await api.put(`/pharmacy-portal/catalog/${item.item_id}`, body);
      else await api.post("/pharmacy-portal/catalog", body);
      toast.success(item ? "Product updated" : "Product added");
      onSaved();
      onClose();
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : d?.map?.((x) => `${x.loc?.slice(-1)[0]}: ${x.msg}`).join("; ") || "Could not save");
    } finally {
      setBusy(false);
    }
  };

  const input = "mt-1 w-full border border-line rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-forest";
  const F = (k, label, props = {}) => (
    <label className="block text-sm"><span className="text-xs uppercase tracking-[0.12em] text-ink-soft">{label}</span>
      <input value={form[k]} onChange={set(k)} className={input} data-testid={`product-${k}`} {...props} /></label>
  );
  return (
    <Modal onClose={onClose} testid="product-form-dialog">
      <h2 className="text-lg font-semibold pe-8">{item ? "Edit product" : "Add a product"}</h2>
      <form onSubmit={save} className="mt-4 space-y-3">
        <div className="grid grid-cols-2 gap-3">{F("name_en", "Name (English)", { required: true, minLength: 2 })}{F("name_ar", "Name (Arabic)", { dir: "rtl" })}</div>
        <div className="grid grid-cols-2 gap-3">{F("sku", "SKU", { required: true })}{F("price_sar", "Price (SAR)", { required: true, type: "number", step: "0.01", min: "0.01" })}</div>
        <div className="grid grid-cols-3 gap-3">{F("generic_name", "Generic")}{F("form", "Form")}{F("strength", "Strength")}</div>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm"><span className="text-xs uppercase tracking-[0.12em] text-ink-soft">Category</span>
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value, requires_prescription: e.target.value === "prescription" || form.requires_prescription })} className={input} data-testid="product-category">
              {CATEGORIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select></label>
          <label className="block text-sm"><span className="text-xs uppercase tracking-[0.12em] text-ink-soft">Stock</span>
            <select value={form.stock_status} onChange={set("stock_status")} className={input} data-testid="product-stock_status">
              <option value="in_stock">In stock</option><option value="low">Low</option><option value="out_of_stock">Out of stock</option>
            </select></label>
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.requires_prescription} onChange={set("requires_prescription")} data-testid="product-requires_prescription" /> Needs a prescription</label>
        {form.requires_prescription && (
          <div className="grid grid-cols-2 gap-3">{F("sfda_registration_number", "SFDA registration no.", { required: true })}{F("days_supply", "Days supply per pack", { required: true, type: "number", min: 1, max: 365 })}</div>
        )}
        {F("pack_size", "Pack size", { type: "number", min: 1 })}
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.active} onChange={set("active")} data-testid="product-active" /> Show to patients</label>
        <p className="text-[11px] text-ink-soft">Controlled medicines can't be sold through the app.</p>
        <button type="submit" disabled={busy} className="btn-primary w-full justify-center" data-testid="product-save-btn">{busy ? "Saving…" : item ? "Save changes" : "Add product"}</button>
      </form>
    </Modal>
  );
}
