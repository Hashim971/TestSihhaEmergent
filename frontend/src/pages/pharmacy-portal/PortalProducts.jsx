import React, { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Package, Plus, Upload, Download, Search, Pencil, AlertTriangle } from "lucide-react";
import { api } from "../../lib/api";
import { ProductForm } from "./ProductForm";
import { LicencesCard } from "./LicencesCard";

const STOCK = { in_stock: "In stock", low: "Low", out_of_stock: "Out of stock" };

export default function PortalProducts() {
  const [data, setData] = useState(null);
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState(null);
  const [result, setResult] = useState(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback((query = "") => api.get("/pharmacy-portal/catalog", { params: { q: query || undefined } })
    .then(({ data: d }) => setData(d)).catch(() => toast.error("Could not load products")), []);
  useEffect(() => { load(); }, [load]);

  const template = async () => {
    const { data: blob } = await api.get("/pharmacy-portal/catalog/template.csv", { responseType: "blob" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sihha-products-template.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const upload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setUploading(true);
    setResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data: r } = await api.post("/pharmacy-portal/catalog/import", form, { headers: { "Content-Type": "multipart/form-data" } });
      setResult(r);
      toast.success(`${r.created} added · ${r.updated} updated${r.errors.length ? ` · ${r.errors.length} skipped` : ""}`);
      load(q);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  if (!data) return <p className="text-sm text-ink-soft">Loading…</p>;
  return (
    <div className="space-y-6 fade-up" data-testid="portal-products-page">
      {editing && <ProductForm item={editing === "new" ? null : editing} onClose={() => setEditing(null)} onSaved={() => load(q)} />}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3"><Package className="h-7 w-7 text-forest" /> Products</h1>
          <p className="text-ink-soft mt-1">What patients can order from you. Upload a spreadsheet or add products one at a time.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={template} className="btn-outline !py-2 text-sm" data-testid="download-template-btn"><Download className="h-4 w-4" /> CSV template</button>
          <button onClick={() => fileRef.current?.click()} disabled={uploading} className="btn-outline !py-2 text-sm" data-testid="upload-csv-btn"><Upload className="h-4 w-4" /> {uploading ? "Uploading…" : "Upload CSV"}</button>
          <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={upload} data-testid="upload-csv-input" />
          <button onClick={() => setEditing("new")} className="btn-primary !py-2 text-sm" data-testid="add-product-btn"><Plus className="h-4 w-4" /> Add product</button>
        </div>
      </div>

      {data.pharmacy_problems.length > 0 && (
        <div className="card p-4 border-amber-200 bg-amber-50 text-sm flex gap-2" data-testid="pharmacy-problems">
          <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
          <div>Patients can't order from you yet. {data.pharmacy_problems.join(" ")}</div>
        </div>
      )}
      <LicencesCard licences={data.licences} onSaved={() => load(q)} />

      {result && (
        <div className="card p-4 text-sm" data-testid="import-result">
          <p className="font-semibold"><bdi>{result.created}</bdi> added · <bdi>{result.updated}</bdi> updated · <bdi>{result.errors.length}</bdi> skipped</p>
          {result.errors.length > 0 && (
            <ul className="mt-2 space-y-1 text-xs text-terracotta max-h-48 overflow-y-auto">
              {result.errors.map((e) => <li key={`${e.row}-${e.sku}`} data-testid={`import-error-${e.row}`}>Row <bdi>{e.row}</bdi>{e.sku ? <> (<bdi>{e.sku}</bdi>)</> : null}: {e.error}</li>)}
            </ul>
          )}
        </div>
      )}

      <form onSubmit={(e) => { e.preventDefault(); load(q); }} className="flex gap-2 max-w-md">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name or SKU" className="flex-1 border border-line rounded-full px-4 py-2 text-sm bg-white" data-testid="product-search-input" />
        <button type="submit" className="btn-outline !py-2 !px-3" data-testid="product-search-btn"><Search className="h-4 w-4" /></button>
      </form>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm min-w-[720px]">
          <thead className="text-xs uppercase tracking-[0.12em] text-ink-soft bg-sand/60">
            <tr><th className="text-start p-3">Product</th><th className="text-start p-3">SKU</th><th className="text-start p-3">Type</th><th className="text-end p-3">Price (SAR)</th><th className="text-start p-3">Stock</th><th className="p-3" /></tr>
          </thead>
          <tbody className="divide-y divide-line">
            {data.items.length === 0 && <tr><td colSpan={6} className="p-6 text-center text-ink-soft" data-testid="products-empty">No products yet — upload the template or add one.</td></tr>}
            {data.items.map((it) => (
              <tr key={it.item_id} className={it.active ? "" : "opacity-50"} data-testid={`product-row-${it.item_id}`}>
                <td className="p-3"><p className="font-medium">{it.name_en}</p><p className="text-xs text-ink-soft" dir="rtl">{it.name_ar}</p></td>
                <td className="p-3 font-mono text-xs">{it.sku}</td>
                <td className="p-3 text-xs">{it.requires_prescription ? "Prescription" : "No prescription"}{it.active ? "" : " · Hidden"}</td>
                <td className="p-3 text-end"><bdi>{Number(it.price_sar).toFixed(2)}</bdi></td>
                <td className="p-3 text-xs">{STOCK[it.stock_status] || it.stock_status}</td>
                <td className="p-3 text-end"><button onClick={() => setEditing(it)} className="p-1.5 rounded-full hover:bg-sand" data-testid={`edit-product-${it.item_id}`} aria-label="Edit"><Pencil className="h-4 w-4 text-ink-soft" /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
