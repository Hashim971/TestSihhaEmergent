import React, { useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Plus, Trash2, Check, X, Pill, TrendingUp } from "lucide-react";

export default function Medications() {
  const { activeProfile } = useAuth();
  const [meds, setMeds] = useState([]);
  const [schedule, setSchedule] = useState([]);
  const [stats, setStats] = useState({});
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", dosage: "", times: "08:00", instructions: "" });

  const load = useCallback(async () => {
    const pid = activeProfile.id;
    const [m, s, st] = await Promise.all([
      api.get("/medications", { params: { profile_id: pid } }),
      api.get("/medications/schedule/today", { params: { profile_id: pid } }),
      api.get("/medications/adherence/stats", { params: { profile_id: pid } }),
    ]);
    setMeds(m.data); setSchedule(s.data); setStats(st.data);
  }, [activeProfile.id]);

  useEffect(() => { load(); }, [load]);

  const addMed = async (e) => {
    e.preventDefault();
    const times = form.times.split(",").map((t) => t.trim()).filter(Boolean);
    if (!form.name || !form.dosage || times.length === 0) return toast.error("Fill name, dosage and times");
    await api.post("/medications", { ...form, times, profile_id: activeProfile.id });
    toast.success("Medication added to schedule");
    setForm({ name: "", dosage: "", times: "08:00", instructions: "" });
    setShowForm(false);
    load();
  };

  const removeMed = async (id) => {
    await api.delete(`/medications/${id}`);
    toast.success("Medication removed");
    load();
  };

  const logDose = async (item, status) => {
    await api.post(`/medications/${item.medication_id}/dose`, { time: item.time, status });
    if (status === "taken") toast.success(`${item.name} marked as taken`);
    else toast.warning(`${item.name} marked as missed — alert created`);
    load();
  };

  return (
    <div className="space-y-8 fade-up" data-testid="medications-page">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Medications</h1>
          <p className="text-ink-soft mt-1">Schedule and adherence for <span className="font-medium text-ink">{activeProfile.name}</span></p>
        </div>
        <button onClick={() => setShowForm(!showForm)} data-testid="add-medication-btn" className="btn-primary">
          <Plus className="h-4 w-4" /> Add Medication
        </button>
      </div>

      {showForm && (
        <form onSubmit={addMed} className="card p-6 grid grid-cols-1 md:grid-cols-4 gap-4" data-testid="medication-form">
          <Input label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} testid="med-input-name" placeholder="e.g. Metformin" />
          <Input label="Dosage" value={form.dosage} onChange={(v) => setForm({ ...form, dosage: v })} testid="med-input-dosage" placeholder="e.g. 500mg" />
          <Input label="Times (comma separated)" value={form.times} onChange={(v) => setForm({ ...form, times: v })} testid="med-input-times" placeholder="08:00, 20:00" />
          <Input label="Instructions" value={form.instructions} onChange={(v) => setForm({ ...form, instructions: v })} testid="med-input-instructions" placeholder="With food" />
          <div className="col-span-full">
            <button type="submit" data-testid="med-submit-btn" className="btn-primary">Save Medication</button>
          </div>
        </form>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 card p-6" data-testid="today-schedule">
          <h3 className="text-lg font-semibold mb-4">Today's Schedule</h3>
          {schedule.length === 0 && <p className="text-sm text-ink-soft py-6 text-center">No doses scheduled today. Add a medication to begin adherence tracking.</p>}
          <div className="space-y-2">
            {schedule.map((item, i) => (
              <div key={i} className={`flex items-center justify-between border rounded-xl px-4 py-3 ${
                item.status === "taken" ? "border-sage bg-sage/10" : item.status === "missed" ? "border-terracotta/40 bg-terracotta/5" : "border-line"
              }`} data-testid={`dose-row-${item.medication_id}-${item.time}`}>
                <div className="flex items-center gap-3">
                  <span className="font-heading font-bold text-forest w-14">{item.time}</span>
                  <div>
                    <p className="font-medium text-sm">{item.name} <span className="text-ink-soft">· {item.dosage}</span></p>
                    {item.instructions && <p className="text-xs text-ink-soft">{item.instructions}</p>}
                  </div>
                </div>
                {item.status === "pending" ? (
                  <div className="flex gap-2">
                    <button onClick={() => logDose(item, "taken")} data-testid={`dose-taken-btn-${item.medication_id}-${item.time}`}
                      className="h-8 w-8 rounded-full bg-forest text-white flex items-center justify-center hover:bg-forest-hover" style={{ transition: "background-color 0.2s ease" }} title="Mark taken">
                      <Check className="h-4 w-4" />
                    </button>
                    <button onClick={() => logDose(item, "missed")} data-testid={`dose-missed-btn-${item.medication_id}-${item.time}`}
                      className="h-8 w-8 rounded-full border border-terracotta text-terracotta flex items-center justify-center hover:bg-terracotta/10" style={{ transition: "background-color 0.2s ease" }} title="Mark missed">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ) : (
                  <span className={`text-xs font-bold uppercase tracking-wider ${item.status === "taken" ? "text-forest" : "text-terracotta"}`}>
                    {item.status}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          <div className="card p-6" data-testid="adherence-stats">
            <h3 className="text-lg font-semibold mb-3 flex items-center gap-2"><TrendingUp className="h-4 w-4 text-forest" /> Adherence</h3>
            <p className="text-4xl font-heading font-bold text-forest">{stats.rate != null ? `${stats.rate}%` : "—"}</p>
            <p className="text-sm text-ink-soft mt-1">{stats.taken || 0} taken · {stats.missed || 0} missed</p>
          </div>
          <div className="card p-6" data-testid="medications-list">
            <h3 className="text-lg font-semibold mb-3 flex items-center gap-2"><Pill className="h-4 w-4 text-forest" /> Active Medications</h3>
            {meds.length === 0 && <p className="text-sm text-ink-soft">None yet.</p>}
            <div className="space-y-2">
              {meds.map((m) => (
                <div key={m.medication_id} className="flex items-center justify-between text-sm border border-line rounded-lg px-3 py-2.5">
                  <div>
                    <p className="font-medium">{m.name} · {m.dosage}</p>
                    <p className="text-xs text-ink-soft">{m.times.join(", ")}</p>
                  </div>
                  <button onClick={() => removeMed(m.medication_id)} data-testid={`delete-med-btn-${m.medication_id}`} className="p-1.5 rounded-full hover:bg-terracotta/10 text-terracotta" style={{ transition: "background-color 0.2s ease" }}>
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Input({ label, value, onChange, testid, placeholder }) {
  return (
    <div>
      <label className="text-xs uppercase tracking-[0.15em] text-ink-soft">{label}</label>
      <input value={value} onChange={(e) => onChange(e.target.value)} data-testid={testid} placeholder={placeholder}
        className="mt-1 w-full border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
    </div>
  );
}
