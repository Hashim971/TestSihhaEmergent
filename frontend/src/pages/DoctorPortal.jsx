import React, { useState, useEffect } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { Stethoscope, Bell, FileText, Pill, ChevronLeft } from "lucide-react";

export default function DoctorPortal() {
  const { user } = useAuth();
  const [patients, setPatients] = useState([]);
  const [selected, setSelected] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user.role === "doctor") {
      api.get("/doctor/patients").then((r) => setPatients(r.data)).catch(() => {});
    }
  }, [user.role]);

  const openPatient = async (p) => {
    setSelected(p);
    setLoading(true);
    try {
      const res = await api.get(`/doctor/patients/${p.user_id}/summary`);
      setSummary(res.data);
    } finally {
      setLoading(false);
    }
  };

  if (user.role !== "doctor") {
    return (
      <div className="card p-10 text-center max-w-lg mx-auto fade-up" data-testid="doctor-access-denied">
        <Stethoscope className="h-10 w-10 text-sage mx-auto mb-3" />
        <p className="text-ink-soft">Switch to the Doctor view (sidebar) to access the provider portal.</p>
      </div>
    );
  }

  if (selected && summary) {
    const vitalsData = summary.vitals.map((v) => ({
      ...v, t: new Date(v.recorded_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
    }));
    return (
      <div className="space-y-6 fade-up" data-testid="doctor-patient-detail">
        <button onClick={() => { setSelected(null); setSummary(null); }} data-testid="back-to-patients-btn" className="btn-outline">
          <ChevronLeft className="h-4 w-4" /> All Patients
        </button>
        <div className="flex items-center gap-4">
          {selected.picture && <img src={selected.picture} alt={selected.name} className="h-12 w-12 rounded-full border border-line" />}
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{selected.name}</h1>
            <p className="text-ink-soft text-sm">{selected.email}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <StatCard label="Adherence Rate" value={summary.adherence.rate != null ? `${summary.adherence.rate}%` : "—"} sub={`${summary.adherence.taken} taken · ${summary.adherence.missed} missed`} />
          <StatCard label="Active Medications" value={summary.medications.length} sub={summary.medications.map((m) => m.name).join(", ") || "None"} />
          <StatCard label="Screening Reports" value={summary.reports.length} sub="AI-generated health screenings" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card p-6">
            <h3 className="text-lg font-semibold mb-4">Heart Rate (recent)</h3>
            {vitalsData.filter((v) => v.heart_rate != null).length === 0 ? (
              <p className="text-sm text-ink-soft py-8 text-center">No vitals shared.</p>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={vitalsData.filter((v) => v.heart_rate != null)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5E4E2" />
                  <XAxis dataKey="t" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} domain={["auto", "auto"]} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #E5E4E2" }} />
                  <Line type="monotone" dataKey="heart_rate" stroke="#1E3F2A" strokeWidth={2} dot={{ r: 2 }} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
          <div className="card p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2"><Bell className="h-4 w-4 text-terracotta" /> Recent Alerts</h3>
            <div className="space-y-2 max-h-56 overflow-y-auto">
              {summary.alerts.length === 0 && <p className="text-sm text-ink-soft">No alerts.</p>}
              {summary.alerts.map((a) => (
                <div key={a.alert_id} className={`text-sm border rounded-lg px-3 py-2 ${a.severity === "critical" ? "border-terracotta/40 bg-terracotta/5" : "border-line"}`}>
                  <span className="text-[10px] uppercase tracking-wider font-bold text-terracotta">{a.type} · {a.severity}</span>
                  <p>{a.message}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="card p-6" data-testid="patient-reports">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2"><FileText className="h-4 w-4 text-forest" /> Screening Reports</h3>
          {summary.reports.length === 0 && <p className="text-sm text-ink-soft">No reports generated yet.</p>}
          <div className="space-y-3">
            {summary.reports.map((r) => (
              <details key={r.report_id} className="border border-line rounded-xl px-4 py-3">
                <summary className="cursor-pointer text-sm font-medium">
                  Report — {new Date(r.generated_at).toLocaleString()}
                </summary>
                <pre className="mt-3 text-xs whitespace-pre-wrap font-body text-ink-soft leading-relaxed">{r.content}</pre>
              </details>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 fade-up" data-testid="doctor-portal-page">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3"><Stethoscope className="h-7 w-7 text-forest" /> Doctor Portal</h1>
        <p className="text-ink-soft mt-1">Patients who have opted in to share their health data.</p>
      </div>
      {loading && <p className="text-ink-soft text-sm">Loading patient…</p>}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="doctor-patients-list">
        {patients.length === 0 && (
          <div className="card p-10 col-span-full text-center">
            <p className="text-ink-soft">No patients are sharing data yet. Patients enable "Share with Doctors" from their sidebar.</p>
          </div>
        )}
        {patients.map((p) => (
          <button key={p.user_id} onClick={() => openPatient(p)} data-testid={`patient-card-${p.user_id}`}
            className="card p-6 text-left hover:shadow-md" style={{ transition: "box-shadow 0.2s ease, transform 0.2s ease" }}>
            <div className="flex items-center gap-3">
              {p.picture ? <img src={p.picture} alt={p.name} className="h-11 w-11 rounded-full border border-line" /> : (
                <span className="h-11 w-11 rounded-full bg-sage text-forest flex items-center justify-center font-bold">{p.name?.charAt(0)}</span>
              )}
              <div>
                <p className="font-semibold">{p.name}</p>
                <p className="text-xs text-ink-soft">{p.email}</p>
              </div>
            </div>
            {p.unread_alerts > 0 && (
              <p className="mt-3 text-xs font-bold text-terracotta flex items-center gap-1">
                <Bell className="h-3.5 w-3.5" /> {p.unread_alerts} unread alert{p.unread_alerts > 1 ? "s" : ""}
              </p>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

function StatCard({ label, value, sub }) {
  return (
    <div className="card p-6">
      <p className="text-xs uppercase tracking-[0.15em] text-ink-soft">{label}</p>
      <p className="text-3xl font-heading font-bold text-forest mt-2">{value}</p>
      <p className="text-xs text-ink-soft mt-1 line-clamp-2">{sub}</p>
    </div>
  );
}
