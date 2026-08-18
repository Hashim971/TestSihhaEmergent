import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { CalendarDays, Plus, Stethoscope, ChevronRight } from "lucide-react";

const BADGE = {
  signed: { label: "Signed", cls: "bg-forest text-white" },
  reviewed: { label: "Draft", cls: "bg-sage/40 text-forest" },
  draft: { label: "Draft", cls: "bg-sage/40 text-forest" },
};

export default function DoctorSchedule() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [encounters, setEncounters] = useState([]);
  const [patients, setPatients] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ patient_user_id: "", scheduled_at: "", reason_for_visit: "" });
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    api.get("/doctor/patients").then((p) => setPatients(p.data)).catch(() => {});
    try {
      const e = await api.get("/encounters");
      setEncounters(e.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user.role === "doctor") load().catch(() => {});
  }, [user.role]);

  const create = async (ev) => {
    ev.preventDefault();
    setSaving(true);
    try {
      await api.post("/encounters", {
        patient_user_id: form.patient_user_id,
        scheduled_at: form.scheduled_at ? new Date(form.scheduled_at).toISOString() : undefined,
        reason_for_visit: form.reason_for_visit,
      });
      toast.success("Encounter scheduled");
      setShowForm(false);
      setForm({ patient_user_id: "", scheduled_at: "", reason_for_visit: "" });
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not create encounter");
    } finally {
      setSaving(false);
    }
  };

  if (user.role !== "doctor") {
    return (
      <div className="card p-10 text-center max-w-lg mx-auto fade-up" data-testid="schedule-access-denied">
        <Stethoscope className="h-10 w-10 text-sage mx-auto mb-3" />
        <p className="text-ink-soft">Switch to the Doctor view (sidebar) to access the schedule.</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 fade-up" data-testid="doctor-schedule-page">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <CalendarDays className="h-7 w-7 text-forest" /> Schedule
          </h1>
          <p className="text-ink-soft mt-1">Upcoming consultations and their pre-visit briefings.</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} data-testid="new-encounter-btn" className="btn-primary">
          <Plus className="h-4 w-4" /> New Encounter
        </button>
      </div>

      {showForm && (
        <form onSubmit={create} className="card p-6 space-y-4" data-testid="new-encounter-form">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <label className="text-sm">
              <span className="text-xs uppercase tracking-[0.15em] text-ink-soft">Patient</span>
              <select
                required value={form.patient_user_id} data-testid="encounter-patient-select"
                onChange={(e) => setForm({ ...form, patient_user_id: e.target.value })}
                className="mt-1 w-full border border-line rounded-lg px-3 py-2 bg-white"
              >
                <option value="">Select a patient…</option>
                {patients.map((p) => (
                  <option key={p.user_id} value={p.user_id}>{p.name} — {p.email}</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="text-xs uppercase tracking-[0.15em] text-ink-soft">Scheduled</span>
              <input
                type="datetime-local" value={form.scheduled_at} data-testid="encounter-datetime-input"
                onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })}
                className="mt-1 w-full border border-line rounded-lg px-3 py-2 bg-white"
              />
            </label>
            <label className="text-sm">
              <span className="text-xs uppercase tracking-[0.15em] text-ink-soft">Reason for visit</span>
              <input
                type="text" value={form.reason_for_visit} data-testid="encounter-reason-input"
                onChange={(e) => setForm({ ...form, reason_for_visit: e.target.value })}
                placeholder="e.g. blood pressure review"
                className="mt-1 w-full border border-line rounded-lg px-3 py-2 bg-white"
              />
            </label>
          </div>
          <button type="submit" disabled={saving} data-testid="save-encounter-btn" className="btn-primary">
            {saving ? "Saving…" : "Schedule Encounter"}
          </button>
          {patients.length === 0 && (
            <p className="text-xs text-ink-soft">
              No patients are sharing data yet. Patients enable "Share with Doctors" from their sidebar.
            </p>
          )}
        </form>
      )}

      <div className="space-y-3" data-testid="encounters-list">
        {loading && (
          <div className="space-y-3" data-testid="encounters-loading">
            {[0, 1, 2].map((i) => (
              <div key={i} className="card p-5 flex items-center gap-4">
                <div className="h-8 w-24 bg-sand rounded-lg" />
                <div className="flex-1 h-4 bg-sand rounded-full" />
                <div className="h-5 w-20 bg-sand rounded-full" />
              </div>
            ))}
          </div>
        )}
        {!loading && encounters.length === 0 && (
          <div className="card p-10 text-center">
            <p className="text-ink-soft">
              No encounters scheduled yet. Create one for a patient who has opted in to share their data.
            </p>
          </div>
        )}
        {encounters.map((e) => {
          const badge = e.briefing ? BADGE[e.briefing.status] : { label: "Not generated", cls: "bg-sand text-ink-soft" };
          return (
            <button
              key={e.encounter_id}
              onClick={() => navigate(`/doctor/encounters/${e.encounter_id}`)}
              data-testid={`encounter-row-${e.encounter_id}`}
              className="card w-full p-5 text-left flex items-center gap-4 hover:shadow-md"
              style={{ transition: "box-shadow 0.2s ease, transform 0.2s ease" }}
            >
              <div className="w-32 shrink-0">
                <p className="font-semibold text-sm">
                  {new Date(e.scheduled_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                </p>
                <p className="text-xs text-ink-soft">
                  {new Date(e.scheduled_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold truncate">{e.patient_name}</p>
                <p className="text-xs text-ink-soft truncate">{e.reason_for_visit || "No reason recorded"}</p>
              </div>
              <span className={`text-[10px] uppercase tracking-wider font-bold px-2.5 py-1 rounded-full ${badge.cls}`}>
                {badge.label}
              </span>
              <span className="text-[10px] uppercase tracking-wider text-ink-soft hidden sm:block">{e.status}</span>
              <ChevronRight className="h-4 w-4 text-ink-soft" />
            </button>
          );
        })}
      </div>
    </div>
  );
}
