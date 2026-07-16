import React, { useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { HeartPulse, Droplets, Thermometer, Wind, Gauge, Plus, Zap } from "lucide-react";

const vitalCards = [
  { key: "heart_rate", label: "Heart Rate", unit: "bpm", icon: HeartPulse },
  { key: "systolic", label: "Blood Pressure", unit: "mmHg", icon: Gauge, pair: "diastolic" },
  { key: "glucose", label: "Glucose", unit: "mg/dL", icon: Droplets },
  { key: "spo2", label: "SpO₂", unit: "%", icon: Wind },
  { key: "temperature", label: "Temperature", unit: "°C", icon: Thermometer },
];

export default function Dashboard() {
  const { activeProfile } = useAuth();
  const [latest, setLatest] = useState({});
  const [vitals, setVitals] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ heart_rate: "", systolic: "", diastolic: "", glucose: "", spo2: "", temperature: "" });
  const [simulating, setSimulating] = useState(false);

  const load = useCallback(async () => {
    const pid = activeProfile.id;
    const [l, v] = await Promise.all([
      api.get("/vitals/latest", { params: { profile_id: pid } }),
      api.get("/vitals", { params: { profile_id: pid, days: 7 } }),
    ]);
    setLatest(l.data);
    setVitals(v.data.map((d) => ({ ...d, t: new Date(d.recorded_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }) })));
  }, [activeProfile.id]);

  useEffect(() => { load(); }, [load]);

  const submitVital = async (e) => {
    e.preventDefault();
    const payload = { profile_id: activeProfile.id };
    let has = false;
    Object.entries(form).forEach(([k, v]) => {
      if (v !== "") { payload[k] = parseFloat(v); has = true; }
    });
    if (!has) return toast.error("Enter at least one reading");
    await api.post("/vitals", payload);
    toast.success("Vitals recorded");
    setForm({ heart_rate: "", systolic: "", diastolic: "", glucose: "", spo2: "", temperature: "" });
    setShowForm(false);
    load();
  };

  const simulate = async () => {
    setSimulating(true);
    try {
      await api.post("/vitals/simulate", { profile_id: activeProfile.id });
      toast.success("7 days of wearable data synced");
      load();
    } finally {
      setSimulating(false);
    }
  };

  return (
    <div className="space-y-8 fade-up" data-testid="patient-dashboard">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Health Dashboard</h1>
          <p className="text-ink-soft mt-1">Real-time overview for <span className="font-medium text-ink">{activeProfile.name}</span></p>
        </div>
        <div className="flex gap-3">
          <button onClick={simulate} disabled={simulating} data-testid="simulate-wearable-btn" className="btn-outline">
            <Zap className="h-4 w-4" /> {simulating ? "Syncing…" : "Sync Wearable (demo)"}
          </button>
          <button onClick={() => setShowForm(!showForm)} data-testid="add-vitals-btn" className="btn-primary">
            <Plus className="h-4 w-4" /> Log Vitals
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={submitVital} className="card p-6 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4" data-testid="vitals-form">
          {[
            ["heart_rate", "Heart rate (bpm)"], ["systolic", "Systolic"], ["diastolic", "Diastolic"],
            ["glucose", "Glucose"], ["spo2", "SpO₂ %"], ["temperature", "Temp °C"],
          ].map(([k, label]) => (
            <div key={k}>
              <label className="text-xs uppercase tracking-[0.15em] text-ink-soft">{label}</label>
              <input
                type="number" step="any" value={form[k]}
                data-testid={`vital-input-${k}`}
                onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                className="mt-1 w-full border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-forest"
              />
            </div>
          ))}
          <div className="col-span-full">
            <button type="submit" data-testid="vitals-submit-btn" className="btn-primary">Save Readings</button>
          </div>
        </form>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {vitalCards.map(({ key, label, unit, icon: Icon, pair }) => {
          const v = latest[key];
          const p = pair && latest[pair];
          return (
            <div key={key} className="card p-6" data-testid={`vital-card-${key}`}>
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase tracking-[0.15em] text-ink-soft">{label}</span>
                <Icon className="h-4 w-4 text-forest" />
              </div>
              <p className="mt-3 text-3xl font-heading font-bold text-ink">
                {v ? (pair && p ? `${v.value}/${p.value}` : v.value) : "—"}
                <span className="text-sm font-normal text-ink-soft ml-1">{unit}</span>
              </p>
              <p className="text-xs text-ink-soft mt-1">
                {v ? new Date(v.recorded_at).toLocaleString() : "No data yet"}
              </p>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="Heart Rate Trend" data={vitals} dataKey="heart_rate" color="#1E3F2A" testid="chart-heart-rate" />
        <ChartCard title="Blood Glucose Trend" data={vitals} dataKey="glucose" color="#E06D53" testid="chart-glucose" />
      </div>
    </div>
  );
}

function ChartCard({ title, data, dataKey, color, testid }) {
  const filtered = data.filter((d) => d[dataKey] != null);
  return (
    <div className="card p-6" data-testid={testid}>
      <h3 className="text-lg font-semibold mb-4">{title}</h3>
      {filtered.length === 0 ? (
        <p className="text-sm text-ink-soft py-10 text-center">No readings in the last 7 days. Log vitals or sync your wearable.</p>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={filtered}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E4E2" />
            <XAxis dataKey="t" tick={{ fontSize: 11 }} stroke="#525252" />
            <YAxis tick={{ fontSize: 11 }} stroke="#525252" domain={["auto", "auto"]} />
            <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #E5E4E2" }} />
            <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={{ r: 2 }} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
