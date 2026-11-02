import React, { useState, useEffect, useRef } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Mic, Square, ShieldCheck, AlertTriangle, FileText } from "lucide-react";
import { PatientSummaryPanel } from "./PatientSummaryPanel";
import { usePlatform } from "../context/PlatformContext";

const CONSENT_TEXT =
  "The patient has been told this consultation will be recorded to draft a clinical note, that the recording is " +
  "deleted after the retention period, and that they can decline. The patient consents.";

const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
const LIVE_SLICE_MS = 10000;

export function ScribePanel({ encounterId }) {
  const { isOn } = usePlatform();
  const [state, setState] = useState(null);
  const [checked, setChecked] = useState(false);
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [busy, setBusy] = useState("");
  const [draft, setDraft] = useState(null);
  const recorder = useRef(null);
  const chunks = useRef([]);
  const timer = useRef(null);
  const saveTimer = useRef(null);
  const player = useRef(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [liveLines, setLiveLines] = useState([]);
  const [liveStatus, setLiveStatus] = useState("");
  const liveActive = useRef(false);
  const liveRec = useRef(null);
  const liveOffset = useRef(0);
  const liveBox = useRef(null);

  useEffect(() => {
    if (liveBox.current) liveBox.current.scrollTop = liveBox.current.scrollHeight;
  }, [liveLines]);

  const sendSlice = async (blob, offset) => {
    if (blob.size < 1024) return;
    const form = new FormData();
    form.append("chunk", blob, `live-${offset}.webm`);
    form.append("offset_seconds", offset);
    form.append("window_seconds", LIVE_SLICE_MS / 1000);
    try {
      const { data } = await api.post(`/encounters/${encounterId}/audio/live`, form);
      setLiveStatus("");
      setLiveLines((prev) => [...prev, ...data.segments].sort((a, b) => a.start - b.start));
    } catch {
      setLiveStatus("A few seconds couldn't be transcribed live — the full recording is still captured.");
    }
  };

  const startSlice = (stream) => {
    if (!liveActive.current || !stream.active) return;
    const parts = [];
    const offset = liveOffset.current;
    const rec = new MediaRecorder(stream, { mimeType: "audio/webm" });
    rec.ondataavailable = (e) => e.data.size && parts.push(e.data);
    rec.onstop = () => {
      liveOffset.current = offset + LIVE_SLICE_MS / 1000;
      sendSlice(new Blob(parts, { type: "audio/webm" }), offset);
      startSlice(stream);
    };
    rec.start();
    liveRec.current = rec;
    setTimeout(() => rec.state === "recording" && rec.stop(), LIVE_SLICE_MS);
  };

  const load = () => api.get(`/encounters/${encounterId}/soap`).then(({ data }) => {
    setState(data);
    setChecked(!!data.consent?.granted);
    if (data.note) setDraft(data.note.edited_content || data.note.content);
  }).catch(() => {});

  useEffect(() => { load(); return () => { clearInterval(timer.current); liveActive.current = false; }; }, [encounterId]);

  if (!state) return null;
  const note = state.note;
  const consented = !!state.consent?.granted;
  const signed = note?.status === "signed";
  const segments = draft?.low_confidence_segments || [];
  const acknowledged = note?.acknowledged_segments || [];
  const pending = segments.length - acknowledged.length;

  const grantConsent = async () => {
    try {
      await api.post(`/encounters/${encounterId}/consent`, { granted: true });
      toast.success("Consent recorded");
      await load();
    } catch { toast.error("Could not record consent"); }
  };

  const start = async () => {
    if (!consented) return toast.error("Record consent first");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks.current = [];
      const rec = new MediaRecorder(stream, { mimeType: "audio/webm" });
      rec.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      rec.onstop = () => stream.getTracks().forEach((t) => t.stop());
      rec.start(5000);
      recorder.current = rec;
      setLiveLines([]);
      setLiveStatus("");
      liveOffset.current = 0;
      liveActive.current = isOn("live_transcript");
      startSlice(stream);
      setRecording(true);
      setElapsed(0);
      timer.current = setInterval(() => setElapsed((s) => s + 1), 1000);
    } catch {
      toast.error("Microphone unavailable — check browser permissions");
    }
  };

  const stop = async () => {
    clearInterval(timer.current);
    const rec = recorder.current;
    if (!rec) return;
    liveActive.current = false;
    if (liveRec.current?.state === "recording") liveRec.current.stop();
    await new Promise((res) => { rec.addEventListener("stop", res, { once: true }); rec.stop(); });
    setRecording(false);
    setBusy("Uploading the recording…");
    try {
      const { data: audio } = await api.post(`/encounters/${encounterId}/audio/init`);
      const blob = new Blob(chunks.current, { type: "audio/webm" });
      const size = 1024 * 512;
      for (let i = 0, part = 0; i < blob.size; i += size, part += 1) {
        const form = new FormData();
        form.append("index", part);
        form.append("chunk", blob.slice(i, i + size), `part-${part}.webm`);
        await api.post(`/audio/${audio.audio_id}/chunk`, form);
      }
      setBusy("Transcribing and drafting the note…");
      const form = new FormData();
      form.append("duration_seconds", elapsed);
      await api.post(`/audio/${audio.audio_id}/complete`, form);
      toast.success("SOAP note drafted");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not process the recording");
    } finally {
      setBusy("");
    }
  };

  const edit = (path, value) => {
    const next = { ...draft };
    if (path === "assessment") next.assessment = value;
    if (path === "followup") next.plan = { ...next.plan, followup: value };
    if (path === "exam") next.objective = { ...next.objective, exam_findings: value };
    setDraft(next);
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      api.patch(`/artifacts/${note.artifact_id}`, { edited_content: next }).then(load)
        .catch(() => toast.error("Could not save edits"));
    }, 800);
  };

  const loadPlayback = async (audioId) => {
    try {
      const res = await api.get(`/audio/${audioId}/stream`, { responseType: "blob" });
      setAudioUrl(URL.createObjectURL(res.data));
    } catch {
      setAudioUrl("");
      toast.error("Could not load the recording");
    }
  };

  const playSegment = (text) => {
    const match = (state.transcript_segments || []).find((s) => s.text && text && s.text.includes(text.slice(0, 18)));
    if (!player.current) return toast.info("Recording is not available");
    player.current.currentTime = match ? match.start : 0;
    player.current.play();
  };

  const acknowledge = async (index) => {
    try {
      await api.post(`/artifacts/${note.artifact_id}/acknowledge`, { index });
      await load();
    } catch { toast.error("Could not acknowledge that segment"); }
  };

  const sign = async () => {
    if (!window.confirm("Sign this clinical note? It becomes read-only.")) return;
    try {
      await api.post(`/artifacts/${note.artifact_id}/sign`);
      toast.success("Note signed");
      await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not sign the note"); }
  };

  return (
    <div className="card p-6" id="sect-soap" data-testid="scribe-section">
      <h3 className="text-lg font-semibold flex items-center gap-2">
        <FileText className="h-4 w-4 text-forest" /> Clinical Scribe
      </h3>
      <p className="text-xs text-ink-soft mt-1">
        Records the consultation and drafts a SOAP note for you to review and sign. Arabic and English.
      </p>

      {!consented ? (
        <div className="mt-4 border border-line rounded-xl px-4 py-4" data-testid="consent-gate">
          <label className="flex items-start gap-3 text-sm">
            <input type="checkbox" checked={checked} data-testid="consent-checkbox"
              onChange={(e) => setChecked(e.target.checked)} className="mt-1" />
            <span className="text-ink-soft">{CONSENT_TEXT}</span>
          </label>
          <div className="flex items-center gap-3 mt-4">
            <button onClick={grantConsent} disabled={!checked} data-testid="record-consent-btn" className="btn-primary">
              <ShieldCheck className="h-4 w-4" /> Record Consent
            </button>
            <button disabled data-testid="start-recording-btn" className="btn-outline opacity-40 cursor-not-allowed">
              <Mic className="h-4 w-4" /> Start Recording
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-4 flex items-center gap-3 flex-wrap" data-testid="recorder-controls">
          {recording ? (
            <>
              <span className="flex items-center gap-2 px-3 py-2 rounded-full bg-terracotta/10" data-testid="recording-indicator">
                <span className="typing-dot !bg-terracotta" />
                <span className="text-sm font-semibold text-terracotta" data-testid="recording-timer">{fmt(elapsed)}</span>
              </span>
              <button onClick={stop} data-testid="stop-recording-btn" className="btn-primary">
                <Square className="h-4 w-4" /> Stop &amp; Draft Note
              </button>
            </>
          ) : (
            <button onClick={start} disabled={!!busy} data-testid="start-recording-btn" className="btn-primary">
              <Mic className="h-4 w-4" /> {note ? "Record Again" : "Start Recording"}
            </button>
          )}
          {busy && <span className="text-xs text-ink-soft" data-testid="scribe-busy">{busy}</span>}
          {state.audio?.deleted_at && (
            <span className="text-xs text-ink-soft" data-testid="audio-purged">Audio deleted after retention</span>
          )}
        </div>
      )}

      {(recording || (busy && liveLines.length > 0)) && isOn("live_transcript") && (
        <div className="mt-4 border border-line rounded-xl bg-sand/60" data-testid="live-transcript">
          <div className="flex items-center justify-between px-4 py-2 border-b border-line">
            <span className="text-[10px] uppercase tracking-[0.15em] text-ink-soft font-semibold">Live transcript</span>
            <span className="text-[10px] text-ink-soft">updates every ~10 seconds</span>
          </div>
          <div ref={liveBox} dir="auto" className="max-h-56 overflow-y-auto px-4 py-3 space-y-2">
            {liveLines.length === 0 ? (
              <p className="text-xs text-ink-soft" data-testid="live-transcript-waiting">Listening… the first lines appear in a few seconds.</p>
            ) : liveLines.map((l, i) => (
              <div key={`${l.start}-${i}`} className="flex gap-3 fade-up" data-testid={`live-line-${i}`}>
                <span className="text-[10px] text-ink-soft tabular-nums pt-1 shrink-0">{fmt(Math.floor(l.start))}</span>
                <p dir="auto" className={`text-sm leading-relaxed ${l.confidence < 0.65 ? "text-terracotta" : ""}`}>{l.text}</p>
              </div>
            ))}
          </div>
          {liveStatus && <p className="px-4 pb-3 text-[11px] text-terracotta" data-testid="live-transcript-status">{liveStatus}</p>}
        </div>
      )}

      {note && draft && (
        <div className="mt-6 space-y-4" data-testid="soap-note">
          <div className="border border-line bg-sand rounded-xl px-4 py-2.5 text-xs text-ink-soft">
            AI-drafted clinical note — for clinician review. Transcript quality:{" "}
            <span className="font-semibold" data-testid="transcript-quality">{draft.transcript_quality}</span>
          </div>

          {state.audio && !state.audio.deleted_at && (
            <div className="flex items-center gap-3 flex-wrap" data-testid="playback-controls">
              {audioUrl ? (
                <audio ref={player} src={audioUrl} controls className="w-full max-w-md" data-testid="scribe-player" />
              ) : (
                <button onClick={() => loadPlayback(state.audio.audio_id)} data-testid="load-playback-btn"
                  className="btn-outline !py-1.5 !px-3 text-xs">
                  Play the recording alongside the note
                </button>
              )}
            </div>
          )}

          {segments.length > 0 && (
            <div className="border border-terracotta/40 bg-terracotta/5 rounded-xl px-4 py-3" data-testid="low-confidence-block">
              <p className="text-xs font-semibold text-terracotta flex items-center gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5" /> {pending > 0
                  ? `${pending} unclear passage${pending === 1 ? "" : "s"} need your acknowledgement before signing`
                  : "All unclear passages acknowledged"}
              </p>
              <div className="mt-2 space-y-2">
                {segments.map((s, i) => (
                  <div key={i} className="flex items-start gap-3" data-testid={`low-confidence-${i}`}>
                    <button onClick={() => acknowledge(i)} disabled={acknowledged.includes(i) || signed}
                      data-testid={`acknowledge-segment-${i}`}
                      className={`btn-outline !py-1 !px-2 text-[10px] ${acknowledged.includes(i) ? "!bg-sage/30 !border-sage" : ""}`}>
                      {acknowledged.includes(i) ? "Acknowledged" : "Acknowledge"}
                    </button>
                    <p className="text-xs text-ink-soft flex-1">
                      “{s.text}” · {Math.round((s.confidence || 0) * 100)}% · affects {s.affects_section}
                    </p>
                    {audioUrl && (
                      <button onClick={() => playSegment(s.text)} data-testid={`play-segment-${i}`}
                        className="text-[10px] uppercase tracking-wider font-bold text-forest">
                        Play
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <Field label="Chief complaint" value={draft.subjective?.chief_complaint} />
          <Field label="History of presenting illness" value={draft.subjective?.hpi} />
          <Field label="Review of systems" value={draft.subjective?.review_of_systems} />

          <div>
            <p className="text-[10px] uppercase tracking-[0.15em] text-ink-soft mb-1">Objective — vitals</p>
            <div className="space-y-1.5">
              {(draft.objective?.vitals || []).map((v, i) => (
                <div key={i} className={`text-sm border rounded-lg px-3 py-2 ${v.conflict ? "border-terracotta/40 bg-terracotta/5" : "border-line"}`}
                  data-testid={`soap-vital-${i}`}>
                  <span className="font-medium">{v.metric}: {v.value}</span>
                  <span className="text-[10px] uppercase tracking-wider text-ink-soft ml-2">{v.source}</span>
                  {v.conflict && <p className="text-xs text-terracotta mt-0.5" data-testid={`soap-vital-conflict-${i}`}>{v.conflict}</p>}
                </div>
              ))}
            </div>
          </div>

          <Editable label="Exam findings" value={draft.objective?.exam_findings} readOnly={signed}
            testid="soap-exam-input" onChange={(v) => edit("exam", v)} />
          <Editable label="Assessment" value={draft.assessment} readOnly={signed}
            testid="soap-assessment-input" onChange={(v) => edit("assessment", v)} />

          <div>
            <p className="text-[10px] uppercase tracking-[0.15em] text-ink-soft mb-1">Plan</p>
            <ul className="text-sm list-disc pl-5 text-ink-soft" data-testid="soap-plan-actions">
              {(draft.plan?.actions || []).map((a, i) => <li key={i}>{a}</li>)}
            </ul>
            {(draft.plan?.medications_discussed || []).length > 0 && (
              <p className="text-xs text-ink-soft mt-1" data-testid="soap-plan-meds">
                Medications discussed: {draft.plan.medications_discussed.join(", ")}
              </p>
            )}
          </div>
          <Editable label="Follow-up" value={draft.plan?.followup} readOnly={signed}
            testid="soap-followup-input" onChange={(v) => edit("followup", v)} />

          {signed ? (
            <>
              <div className="flex items-center gap-2 text-sm" data-testid="soap-signature-line">
                <ShieldCheck className="h-4 w-4 text-forest" /> Signed {new Date(note.signed_at).toLocaleString()}
              </div>
              <PatientSummaryPanel noteArtifactId={note.artifact_id} summary={state.patient_summary} onChange={load} />
            </>
          ) : (
            <button onClick={sign} disabled={pending > 0} data-testid="sign-soap-btn"
              className={`btn-primary ${pending > 0 ? "opacity-40 cursor-not-allowed" : ""}`}>
              <ShieldCheck className="h-4 w-4" /> Review &amp; Sign Note
            </button>
          )}
        </div>
      )}
    </div>
  );
}

const Field = ({ label, value }) => (
  <div>
    <p className="text-[10px] uppercase tracking-[0.15em] text-ink-soft mb-1">{label}</p>
    <p className="text-sm">{value || <span className="text-ink-soft">Not recorded</span>}</p>
  </div>
);

const Editable = ({ label, value, onChange, readOnly, testid }) => (
  <div>
    <p className="text-[10px] uppercase tracking-[0.15em] text-ink-soft mb-1">{label}</p>
    {readOnly ? (
      <p className="text-sm">{value || <span className="text-ink-soft">Not recorded</span>}</p>
    ) : (
      <textarea value={value || ""} rows={2} data-testid={testid} onChange={(e) => onChange(e.target.value)}
        className="w-full text-sm border border-line rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-forest" />
    )}
  </div>
);
