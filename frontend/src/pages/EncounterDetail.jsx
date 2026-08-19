import React, { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { ChevronLeft, Sparkles, ShieldCheck, ListChecks, HelpCircle, AlertTriangle } from "lucide-react";
import {
  ConcernsCard, VitalsCard, MedicationsCard, ListCard, InteractionCard, Editable,
} from "../components/BriefingSections";
import { FollowUpPanel } from "../components/FollowUpPanel";
import { IntakeCard } from "../components/IntakeCard";

const EMPTY = {
  headline: "", chief_concerns: [], vitals_summary: [], medication_review: [],
  suggested_discussion_points: [], data_gaps: [], confidence: "low",
};

export default function EncounterDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [encounter, setEncounter] = useState(null);
  const [patient, setPatient] = useState(null);
  const [artifact, setArtifact] = useState(null);
  const [draft, setDraft] = useState(EMPTY);
  const [series, setSeries] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [thread, setThread] = useState([]);
  const [asking, setAsking] = useState(false);
  const [intake, setIntake] = useState(null);
  const [generatingIntake, setGeneratingIntake] = useState(false);
  const saveTimer = useRef(null);

  const signed = artifact?.status === "signed";

  const load = useCallback(async () => {
    const res = await api.get(`/encounters/${id}`);
    setEncounter(res.data.encounter);
    setPatient(res.data.patient);
    if (res.data.artifact) {
      setArtifact(res.data.artifact);
      setDraft({ ...EMPTY, ...(res.data.artifact.edited_content || res.data.artifact.content) });
      api.get(`/artifacts/${res.data.artifact.artifact_id}/thread`)
        .then((t) => setThread(t.data.messages || [])).catch(() => {});
    }
    api.get(`/doctor/intake/${id}`).then((r) => setIntake(r.data)).catch(() => {});
    api.get(`/doctor/patients/${res.data.encounter.patient_user_id}/summary`)
      .then((s) => setSeries(s.data.vitals || [])).catch(() => {});
  }, [id]);

  useEffect(() => { load().catch(() => toast.error("Could not load encounter")); }, [load]);

  const generate = async () => {
    setGenerating(true);
    try {
      const res = await api.post(`/agents/previsit/${id}`);
      setArtifact(res.data);
      setDraft({ ...EMPTY, ...res.data.content });
      setThread([]);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Briefing generation failed. Try again.");
    } finally {
      setGenerating(false);
    }
  };

  const generateIntake = async () => {
    setGeneratingIntake(true);
    try {
      const res = await api.post(`/agents/intake/${id}`);
      setIntake(res.data);
      toast.success("Intake questions sent to the patient");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not generate intake questions");
    } finally {
      setGeneratingIntake(false);
    }
  };

  const queueSave = (next) => {
    setDraft(next);
    if (!artifact || signed) return;
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      try {
        const res = await api.patch(`/artifacts/${artifact.artifact_id}`, { edited_content: next });
        setArtifact(res.data);
      } catch (e) {
        toast.error(e?.response?.status === 409 ? "Signed briefings cannot be edited" : "Could not save edits");
      }
    }, 800);
  };

  const editConcern = (i, field, value) => {
    const concerns = draft.chief_concerns.map((c, ci) => (ci === i ? { ...c, [field]: value } : c));
    queueSave({ ...draft, chief_concerns: concerns });
  };

  const sign = async () => {
    if (!window.confirm("Sign this briefing? It becomes read-only.")) return;
    try {
      clearTimeout(saveTimer.current);
      const res = await api.post(`/artifacts/${artifact.artifact_id}/sign`);
      setArtifact(res.data);
      toast.success("Briefing signed");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not sign briefing");
    }
  };

  const ask = async (question) => {
    setAsking(true);
    setThread((t) => [...t, { role: "doctor", content: question, message_id: `local_${Date.now()}` }]);
    try {
      const res = await api.post(`/artifacts/${artifact.artifact_id}/thread`, { question });
      setThread(res.data.messages || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not answer that question");
    } finally {
      setAsking(false);
    }
  };

  const scrollToCite = (c) => {
    const el =
      document.getElementById(`cite-${c.collection}-${c.id}`) ||
      document.getElementById(`sect-${c.collection}`) ||
      (c.collection === "clinical_artifacts" ? document.getElementById("sect-briefing") : null);
    if (!el) return toast.info("That record is not shown in this briefing");
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("ring-2", "ring-terracotta");
    setTimeout(() => el.classList.remove("ring-2", "ring-terracotta"), 2500);
  };

  if (user.role !== "doctor") {
    return (
      <div className="card p-10 text-center max-w-lg mx-auto fade-up" data-testid="encounter-access-denied">
        <p className="text-ink-soft">Doctor access required.</p>
      </div>
    );
  }
  if (!encounter) return <p className="text-ink-soft text-sm">Loading encounter…</p>;

  const starters = (draft.chief_concerns || []).slice(0, 3).map((c) => `Why was ${c.concern} flagged?`);

  return (
    <div className="space-y-6 fade-up" data-testid="encounter-detail-page">
      <button onClick={() => navigate("/doctor/schedule")} data-testid="back-to-schedule-btn" className="btn-outline">
        <ChevronLeft className="h-4 w-4" /> Schedule
      </button>

      <div className="flex items-center gap-4">
        <span className="h-12 w-12 rounded-full bg-sage text-forest flex items-center justify-center font-bold text-lg">
          {patient?.name?.charAt(0)}
        </span>
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="encounter-patient-name">{patient?.name}</h1>
          <p className="text-ink-soft text-sm">
            {new Date(encounter.scheduled_at).toLocaleString()} · {encounter.reason_for_visit || "No reason recorded"}
          </p>
        </div>
      </div>

      <IntakeCard intake={intake} onGenerate={generateIntake} generating={generatingIntake} />

      {!artifact && !generating && (
        <div className="card p-10 text-center" data-testid="briefing-empty-state">
          <Sparkles className="h-9 w-9 text-sage mx-auto mb-3" />
          <p className="text-ink-soft mb-5">No pre-visit briefing yet for this encounter.</p>
          <button onClick={generate} data-testid="generate-briefing-btn" className="btn-primary">
            <Sparkles className="h-4 w-4" /> Generate Pre-Visit Briefing
          </button>
        </div>
      )}

      {generating && (
        <div className="card p-8 space-y-3" data-testid="briefing-skeleton">
          <p className="text-sm text-ink-soft">Reviewing 90 days of patient data…</p>
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-4 bg-sand rounded-full" style={{ width: `${90 - i * 18}%` }} />
          ))}
        </div>
      )}

      {artifact && !generating && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-2 space-y-6">
            <div className="border border-line bg-sand rounded-xl px-4 py-3 text-xs font-medium text-ink-soft"
              data-testid="ai-draft-banner">
              AI-generated draft — for clinician review. Not a diagnosis.
            </div>

            {draft.confidence === "low" && (
              <div className="border border-terracotta/40 bg-terracotta/5 rounded-xl px-4 py-3 flex items-start gap-2"
                data-testid="low-confidence-callout">
                <AlertTriangle className="h-4 w-4 text-terracotta mt-0.5" />
                <p className="text-xs text-ink">
                  Low confidence — the record is sparse or stale. Read the data gaps before relying on this briefing.
                </p>
              </div>
            )}

            <div className="card p-6" id="sect-briefing" data-testid="briefing-headline">
              <p className="text-xs uppercase tracking-[0.15em] text-ink-soft mb-1">Headline</p>
              <div className="text-lg font-heading font-semibold text-forest">
                <Editable value={draft.headline} readOnly={signed} testid="headline-input"
                  onChange={(v) => queueSave({ ...draft, headline: v })} />
              </div>
            </div>

            <ConcernsCard concerns={draft.chief_concerns} onEdit={editConcern} readOnly={signed} intake={intake} />
            <VitalsCard vitals={draft.vitals_summary} series={series} />
            <MedicationsCard meds={draft.medication_review} />
            <ListCard
              title="Discussion Points" icon={ListChecks} items={draft.suggested_discussion_points}
              readOnly={signed} testid="briefing-discussion"
              onChange={(items) => queueSave({ ...draft, suggested_discussion_points: items })}
            />
            <ListCard
              title="Data Gaps" icon={HelpCircle} items={draft.data_gaps} muted
              readOnly={signed} testid="briefing-gaps"
              onChange={(items) => queueSave({ ...draft, data_gaps: items })}
            />
            <InteractionCard reference={artifact.reference_flags} />

            {signed ? (
              <div className="card p-6 flex items-center gap-3" data-testid="signature-line">
                <ShieldCheck className="h-5 w-5 text-forest" />
                <p className="text-sm">
                  Signed by <span className="font-semibold">{user.name}</span> ·{" "}
                  {new Date(artifact.signed_at).toLocaleString()}
                </p>
              </div>
            ) : (
              <div className="flex items-center gap-3 flex-wrap">
                <button onClick={sign} data-testid="sign-briefing-btn" className="btn-primary">
                  <ShieldCheck className="h-4 w-4" /> Review &amp; Sign
                </button>
                <button onClick={generate} data-testid="regenerate-briefing-btn" className="btn-outline">
                  <Sparkles className="h-4 w-4" /> Regenerate
                </button>
                {intake?.status === "complete" && intake.updated_at > artifact.created_at && (
                  <p className="text-xs text-terracotta" data-testid="stale-briefing-hint">
                    The patient answered their intake after this briefing was written — regenerate to include it.
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="xl:col-span-1">
            <FollowUpPanel messages={thread} onAsk={ask} busy={asking} starters={starters} onCite={scrollToCite} />
          </div>
        </div>
      )}
    </div>
  );
}
