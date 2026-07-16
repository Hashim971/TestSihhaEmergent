import React, { useState, useEffect, useRef } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Upload, ScanLine, AlertTriangle, CheckCircle2, Clock, ChevronDown } from "lucide-react";

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
