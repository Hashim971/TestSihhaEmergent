import React, { useState, useEffect, useRef } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Upload, ScanLine, AlertTriangle, CheckCircle2, Clock, ChevronDown, Plus } from "lucide-react";

export default function PillIdentify() {
  const { activeProfile } = useAuth();
  const [preview, setPreview] = useState(null);
  const [base64, setBase64] = useState(null);
  const [result, setResult] = useState(null);
  const [cam, setCam] = useState(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);

  const loadHistory = async () => {
    const res = await api.get("/pills/history");
    setHistory(res.data);
  };
  useEffect(() => { loadHistory(); }, []);

  const handleFile = (file) => {
    if (!file || !file.type.startsWith("image/")) return toast.error("Please choose an image file");
    const reader = new FileReader();
    reader.onload = () => {
      setPreview(reader.result);
      setBase64(reader.result.split(",")[1]);
      setResult(null);
    };
    reader.readAsDataURL(file);
  };

  const identify = async () => {
    if (!base64) return;
    setLoading(true);
    try {
      const res = await api.post("/pills/identify", { image_base64: base64, profile_id: activeProfile.id });
      setResult(res.data.result);
      setCam(res.data.cam_image_base64 || null);
      loadHistory();
    } catch {
      toast.error("Identification failed. Try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8 fade-up" data-testid="pill-id-page">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Pill Identification</h1>
        <p className="text-ink-soft mt-1">Photograph a medication and let the AI vision engine identify it.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card p-8">
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]); }}
            onClick={() => fileRef.current?.click()}
            data-testid="pill-upload-zone"
            className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer ${
              dragOver ? "border-forest bg-sage/10" : "border-line hover:border-sage"
            }`}
            style={{ transition: "border-color 0.2s ease, background-color 0.2s ease" }}
          >
            {preview ? (
              <img src={preview} alt="Pill preview" className="max-h-56 mx-auto rounded-lg object-contain" data-testid="pill-preview-img" />
            ) : (
              <>
                <Upload className="h-10 w-10 text-sage mx-auto mb-4" />
                <p className="font-medium">Drop a pill photo here, or click to browse</p>
                <p className="text-xs text-ink-soft mt-2">JPEG, PNG or WEBP — clear, well-lit photos work best</p>
              </>
            )}
            <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
              data-testid="pill-file-input"
              onChange={(e) => handleFile(e.target.files[0])} />
          </div>
          <button onClick={identify} disabled={!base64 || loading} data-testid="identify-pill-btn" className="btn-primary w-full justify-center mt-6">
            <ScanLine className="h-4 w-4" /> {loading ? "Analyzing image…" : "Identify Medication"}
          </button>
        </div>

        <div className="card p-8" data-testid="pill-result-card">
          {!result && !loading && (
            <div className="h-full flex flex-col items-center justify-center text-center gap-3 py-10">
              <ScanLine className="h-10 w-10 text-sage" />
              <p className="text-ink-soft">Identification results will appear here.</p>
            </div>
          )}
          {loading && (
            <div className="h-full flex flex-col items-center justify-center gap-3 py-10">
              <span className="flex gap-1.5"><span className="typing-dot" /><span className="typing-dot" style={{ animationDelay: "0.15s" }} /><span className="typing-dot" style={{ animationDelay: "0.3s" }} /></span>
              <p className="text-ink-soft text-sm">Vision AI is analyzing your photo…</p>
            </div>
          )}
          {result && <PillResultDetails result={result} cam={cam} />}
        </div>
      </div>

      {history.length > 0 && (
        <div className="card p-6" data-testid="pill-history">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2"><Clock className="h-4 w-4 text-forest" /> Recent Identifications</h3>
          <div className="space-y-2">
            {history.slice(0, 8).map((h) => (
              <div key={h.pill_id} className="border border-line rounded-lg overflow-hidden">
                <button
                  onClick={() => setExpandedId(expandedId === h.pill_id ? null : h.pill_id)}
                  data-testid={`pill-history-row-${h.pill_id}`}
                  className="w-full flex items-center justify-between px-4 py-3 text-sm hover:bg-sand text-left"
                  style={{ transition: "background-color 0.2s ease" }}
                >
                  <span className="font-medium flex items-center gap-2">
                    <ChevronDown className={`h-4 w-4 text-ink-soft shrink-0 ${expandedId === h.pill_id ? "rotate-180" : ""}`}
                      style={{ transition: "transform 0.2s ease" }} />
                    {h.result?.identified ? h.result.name : "Unidentified"}
                  </span>
                  <span className="text-ink-soft text-xs">{new Date(h.created_at).toLocaleString()}</span>
                </button>
                {expandedId === h.pill_id && (
                  <div className="border-t border-line px-5 py-5 bg-sand/50" data-testid={`pill-history-details-${h.pill_id}`}>
                    <PillResultDetails result={h.result} cam={null} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function AddToMedications({ result }) {
  const { activeProfile } = useAuth();
  const [added, setAdded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [open, setOpen] = useState(false);
  const [dose, setDose] = useState("");
  const [times, setTimes] = useState(["08:00"]);

  const add = async () => {
    const slots = times.filter((t) => /^\d{2}:\d{2}$/.test(t));
    if (!dose.trim()) return toast.error("Enter the dose you take");
    if (slots.length === 0) return toast.error("Pick a time of day first");
    setSaving(true);
    try {
      await api.post("/medications", {
        name: result.name,
        dosage: dose.trim(),
        times: [...new Set(slots)].sort(),
        instructions: "Added from Pill ID — confirm the dose with your pharmacist.",
        units_per_dose: 1,
        profile_id: activeProfile.id,
      });
      setAdded(true);
      toast.success(`${result.name} added to your medication schedule`);
    } catch {
      toast.error("Could not add that medicine");
    } finally {
      setSaving(false);
    }
  };

  if (added) {
    return (
      <p className="text-sm text-forest flex items-center gap-2" data-testid="pill-added-confirmation">
        <CheckCircle2 className="h-4 w-4" /> Added to your Medications page — reminders start at the times you set.
      </p>
    );
  }

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="btn-primary" data-testid="add-pill-open-btn">
        <Plus className="h-4 w-4" /> Add to my medications
      </button>
    );
  }

  return (
    <div className="border border-line rounded-xl p-4 space-y-3" data-testid="add-pill-to-meds">
      <div>
        <label className="text-xs uppercase tracking-[0.15em] text-ink-soft">Dose</label>
        <input value={dose} onChange={(e) => setDose(e.target.value)} placeholder="e.g. 1 tablet · 500 mg"
          data-testid="pill-med-dose-input"
          className="mt-1 w-full border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
      </div>
      <div>
        <label className="text-xs uppercase tracking-[0.15em] text-ink-soft">Times each day</label>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          {times.map((t, i) => (
            <span key={i} className="inline-flex items-center gap-1">
              <input type="time" value={t} onChange={(e) => setTimes(times.map((x, j) => (j === i ? e.target.value : x)))}
                data-testid={`pill-med-time-input-${i}`} className="border border-line rounded-lg px-2.5 py-1.5 text-sm w-32" />
              {times.length > 1 && (
                <button type="button" onClick={() => setTimes(times.filter((_, j) => j !== i))} className="text-ink-soft text-xs"
                  data-testid={`pill-med-time-remove-${i}`} aria-label="Remove time">✕</button>
              )}
            </span>
          ))}
          <button type="button" onClick={() => setTimes([...times, "20:00"])} className="btn-outline !py-1.5 !px-3 text-xs"
            data-testid="pill-med-time-add-btn"><Plus className="h-3.5 w-3.5" /> Add time</button>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button onClick={add} disabled={saving} className="btn-primary" data-testid="add-pill-to-meds-btn">
          <Plus className="h-4 w-4" /> {saving ? "Adding…" : "Add"}
        </button>
        <button onClick={() => setOpen(false)} className="text-sm text-ink-soft underline" data-testid="add-pill-cancel-btn">Cancel</button>
      </div>
      <p className="text-xs text-ink-soft">AI identification — check with a pharmacist first.</p>
    </div>
  );
}

function PillResultDetails({ result, cam }) {
  if (!result) return <p className="text-sm text-ink-soft">No details stored for this entry.</p>;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        {result.identified ? <CheckCircle2 className="h-5 w-5 text-forest" /> : <AlertTriangle className="h-5 w-5 text-terracotta" />}
        <h2 className="text-xl font-bold" data-testid="pill-result-name">
          {result.identified ? result.name : "Not identified"}
        </h2>
        {result.confidence && (
          <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-1 rounded-full bg-sage/30 text-forest">
            {result.confidence} confidence
          </span>
        )}
        {result.source && (
          <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-1 rounded-full bg-forest text-white" data-testid="pill-source-badge">
            {result.source === "cnn_classifier" ? "CNN Model" : "Vision AI"}
          </span>
        )}
      </div>
      {result.generic_name && <p className="text-sm text-ink-soft">Generic: {result.generic_name}</p>}
      {result.identified && <AddToMedications result={result} />}
      {result.description && <Section title="Description" body={result.description} />}
      {result.uses && <Section title="Uses" body={result.uses} />}
      {result.dosage_info && <Section title="Dosage" body={result.dosage_info} />}
      {result.side_effects?.length > 0 && (
        <Section title="Side Effects" body={result.side_effects.join(" · ")} />
      )}
      {result.warnings?.length > 0 && (
        <div className="border border-terracotta/40 bg-terracotta/5 rounded-xl p-4">
          <p className="text-xs uppercase tracking-[0.15em] font-bold text-terracotta mb-1">Warnings</p>
          <ul className="text-sm space-y-1">
            {result.warnings.map((w, i) => <li key={i}>• {w}</li>)}
          </ul>
        </div>
      )}
      {!result.identified && result.reason && <Section title="Reason" body={result.reason} />}
      {cam && (
        <div>
          <p className="text-xs uppercase tracking-[0.15em] font-bold text-forest mb-2">Model Attention Map (Grad-CAM)</p>
          <img src={`data:image/webp;base64,${cam}`} alt="Class activation map"
            data-testid="pill-cam-image"
            className="rounded-xl border border-line max-h-48 object-contain" />
          <p className="text-xs text-ink-soft mt-1">Regions the classifier focused on to make its prediction.</p>
        </div>
      )}
    </div>
  );
}

function Section({ title, body }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-[0.15em] font-bold text-forest mb-1">{title}</p>
      <p className="text-sm leading-relaxed">{body}</p>
    </div>
  );
}
