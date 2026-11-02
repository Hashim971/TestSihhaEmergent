import React, { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Camera, FileImage, Plus, Trash2, Check, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";

const toRow = (m) => ({ pick: true, name: m.name, dosage: m.dosage || "", times: (m.times || []).join(", "),
  instructions: m.instructions || m.frequency || "", quantity: m.quantity ? String(m.quantity) : "" });

export function PrescriptionUpload({ onAdded }) {
  const { activeProfile } = useAuth();
  const [uploads, setUploads] = useState([]);
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState(null);
  const input = useRef(null);

  const load = useCallback(() => {
    api.get("/rx-uploads", { params: { profile_id: activeProfile.id } }).then(({ data }) => setUploads(data)).catch(() => {});
  }, [activeProfile.id]);
  useEffect(() => { load(); }, [load]);

  const upload = async (file) => {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    fd.append("profile_id", activeProfile.id);
    setBusy(true);
    try {
      const { data } = await api.post("/rx-uploads", fd);
      setReview(data);
      load();
      if (!data.extracted?.medications?.length) toast.warning("We couldn't find medicines on it — add them below.");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not upload that prescription");
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  };

  return (
    <div className="card p-5 sm:p-6 space-y-4" data-testid="rx-upload-card">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2"><FileImage className="h-4 w-4 text-forest" /> Upload a prescription</h3>
          <p className="text-sm text-ink-soft">Take a photo — AI reads the medicines and you confirm them before they join your schedule.</p>
        </div>
        <button onClick={() => input.current?.click()} disabled={busy} className="btn-primary" data-testid="rx-upload-btn">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />} {busy ? "Reading…" : "Upload photo"}
        </button>
        <input ref={input} type="file" accept="image/*" className="hidden" data-testid="rx-upload-input"
          onChange={(e) => upload(e.target.files?.[0])} />
      </div>
      {review && <RxReview upload={review} onDone={() => { setReview(null); load(); onAdded?.(); }} onCancel={() => setReview(null)} />}
      {uploads.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3" data-testid="rx-upload-list">
          {uploads.map((u) => <RxThumb key={u.upload_id} upload={u} onReview={() => setReview(u)} onDeleted={load} />)}
        </div>
      )}
    </div>
  );
}

function RxThumb({ upload, onReview, onDeleted }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let url;
    api.get(`/rx-uploads/${upload.upload_id}/image`, { responseType: "blob" })
      .then(({ data }) => { url = URL.createObjectURL(data); setSrc(url); }).catch(() => {});
    return () => url && URL.revokeObjectURL(url);
  }, [upload.upload_id]);
  const remove = async () => {
    await api.delete(`/rx-uploads/${upload.upload_id}`);
    toast.success("Prescription photo removed");
    onDeleted();
  };
  const pending = upload.status === "pending_review";
  return (
    <div className="border border-line rounded-xl overflow-hidden bg-white" data-testid={`rx-upload-${upload.upload_id}`}>
      <a href={src || undefined} target="_blank" rel="noreferrer" className="block aspect-[4/3] bg-sand">
        {src && <img src={src} alt="Uploaded prescription" className="h-full w-full object-cover" />}
      </a>
      <div className="p-2 flex items-center justify-between gap-1">
        {pending ? (
          <button onClick={onReview} className="text-xs font-medium text-forest underline" data-testid={`rx-upload-review-${upload.upload_id}`}>Review</button>
        ) : (
          <span className="text-[11px] text-forest flex items-center gap-1"><Check className="h-3 w-3" /> {upload.added_medication_ids?.length || 0} added</span>
        )}
        <button onClick={remove} className="p-1 rounded-full text-terracotta hover:bg-terracotta/10" data-testid={`rx-upload-delete-${upload.upload_id}`}>
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

function RxReview({ upload, onDone, onCancel }) {
  const [rows, setRows] = useState(() => {
    const meds = upload.extracted?.medications || [];
    return meds.length ? meds.map(toRow) : [toRow({ name: "" })];
  });
  const [saving, setSaving] = useState(false);
  const set = (i, k, v) => setRows((r) => r.map((row, j) => (j === i ? { ...row, [k]: v } : row)));
  const picked = rows.filter((r) => r.pick && r.name.trim());

  const save = async () => {
    const medications = picked.map((r) => ({
      name: r.name, dosage: r.dosage, instructions: r.instructions || null,
      times: r.times.split(",").map((t) => t.trim()).filter(Boolean),
      quantity_dispensed: r.quantity ? parseInt(r.quantity, 10) : null,
    }));
    setSaving(true);
    try {
      const { data } = await api.post(`/rx-uploads/${upload.upload_id}/confirm`, { medications });
      toast.success(`${data.added} medicine${data.added === 1 ? "" : "s"} added to your schedule`);
      onDone();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not add those medicines");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="border border-sage rounded-xl p-4 bg-sage/10 space-y-3" data-testid="rx-review">
      <p className="text-sm font-medium">Check what we read{upload.extracted?.prescriber ? ` · ${upload.extracted.prescriber}` : ""}</p>
      <p className="text-xs text-ink-soft">AI can misread handwriting — compare with the paper and fix anything before adding.</p>
      {rows.map((r, i) => <RxRow key={i} row={r} i={i} set={set} />)}
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => setRows([...rows, toRow({ name: "" })])} className="btn-outline" data-testid="rx-review-add-row">
          <Plus className="h-4 w-4" /> Another medicine
        </button>
        <button type="button" onClick={save} disabled={saving || picked.length === 0} className="btn-primary" data-testid="rx-review-confirm-btn">
          <Check className="h-4 w-4" /> {saving ? "Adding…" : `Add ${picked.length} to my medications`}
        </button>
        <button type="button" onClick={onCancel} className="text-sm text-ink-soft underline" data-testid="rx-review-later-btn">Later</button>
      </div>
    </div>
  );
}

function RxRow({ row, i, set }) {
  const field = (k, ph, cls = "") => (
    <input value={row[k]} onChange={(e) => set(i, k, e.target.value)} placeholder={ph} data-testid={`rx-row-${i}-${k}`}
      className={`border border-line rounded-lg px-3 py-2 text-sm bg-white min-w-0 focus:outline-none focus:ring-2 focus:ring-forest ${cls}`} />
  );
  return (
    <div className="grid grid-cols-1 sm:grid-cols-12 gap-2 items-center bg-white/60 rounded-lg p-2" data-testid={`rx-row-${i}`}>
      <label className="sm:col-span-3 flex items-center gap-2 min-w-0">
        <input type="checkbox" checked={row.pick} onChange={(e) => set(i, "pick", e.target.checked)} className="accent-[#1E3F2A]" data-testid={`rx-row-${i}-pick`} />
        {field("name", "Medicine name", "flex-1")}
      </label>
      {field("dosage", "Dose, e.g. 500 mg · 1 tablet", "sm:col-span-3")}
      {field("times", "Times, e.g. 08:00, 20:00", "sm:col-span-3")}
      {field("instructions", "Instructions", "sm:col-span-2")}
      {field("quantity", "Qty", "sm:col-span-1")}
    </div>
  );
}
