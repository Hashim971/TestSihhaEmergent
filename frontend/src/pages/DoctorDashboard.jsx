import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import {
  Users, CalendarClock, Sparkles, ShieldCheck, ClipboardList, Bell, ArrowRight, Activity,
} from "lucide-react";
import { DayView } from "../components/DayView";
import { AlertGroups } from "../components/AlertGroups";

const Stat = ({ icon: Icon, label, value, tone, testid }) => (
  <div className="card p-5" data-testid={testid}>
    <div className="flex items-center justify-between">
      <span className="text-xs uppercase tracking-[0.15em] text-ink-soft">{label}</span>
      <Icon className={`h-4 w-4 ${tone === "alert" ? "text-terracotta" : "text-forest"}`} />
    </div>
    <p className={`text-3xl font-bold mt-2 ${tone === "alert" ? "text-terracotta" : "text-ink"}`}>{value}</p>
  </div>
);

const VisitRow = ({ v, onOpen }) => (
  <button onClick={() => onOpen(v.encounter_id)} data-testid={`dash-visit-${v.encounter_id}`}
    className="w-full text-left px-4 py-3 border border-line rounded-xl flex items-center gap-3 hover:bg-sand"
    style={{ transition: "background-color 0.2s ease" }}>
    <span className="text-xs font-semibold w-20 shrink-0">
      {new Date(v.scheduled_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
      <span className="block text-ink-soft font-normal">
        {new Date(v.scheduled_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
      </span>
    </span>
    <span className="flex-1 min-w-0">
      <span className="block text-sm font-medium truncate">{v.patient_name}</span>
      <span className="block text-xs text-ink-soft truncate">{v.reason_for_visit || "No reason recorded"}</span>
    </span>
    <span className={`text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full ${
      v.briefing_status === "signed" ? "bg-forest text-white"
        : v.briefing_status ? "bg-sage/40 text-forest" : "bg-sand text-ink-soft"}`}>
      {v.briefing_status === "signed" ? "Signed" : v.briefing_status ? "Draft" : "No briefing"}
    </span>
    <ArrowRight className="h-4 w-4 text-ink-soft" />
  </button>
);

const Panel = ({ title, icon: Icon, items, empty, onOpen, testid, action }) => (
  <div className="card p-6" data-testid={testid}>
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-lg font-semibold flex items-center gap-2">
        <Icon className="h-4 w-4 text-forest" /> {title}
      </h2>
      {action}
    </div>
    {items.length === 0 ? (
      <p className="text-sm text-ink-soft">{empty}</p>
    ) : (
      <div className="space-y-2">{items.map((v) => <VisitRow key={v.encounter_id} v={v} onOpen={onOpen} />)}</div>
    )}
  </div>
);

export default function DoctorDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);

  const load = () => api.get("/doctor/dashboard").then((r) => { setData(r.data); setError(false); })
    .catch(() => setError(true));

  useEffect(() => { if (user.role === "doctor") load(); }, [user.role]);

  const open = (id) => navigate(`/doctor/encounters/${id}`);

  if (user.role !== "doctor") {
    return (
      <div className="card p-10 text-center max-w-lg mx-auto fade-up" data-testid="doctor-dashboard-denied">
        <p className="text-ink-soft">Clinician access required.</p>
      </div>
    );
  }
  if (error) {
    return (
      <div className="card p-8 text-center max-w-lg mx-auto fade-up" data-testid="doctor-dashboard-error">
        <p className="text-ink-soft mb-4">Could not load your dashboard.</p>
        <button onClick={load} data-testid="retry-dashboard-btn" className="btn-outline">Try again</button>
      </div>
    );
  }
  if (!data) return <p className="text-sm text-ink-soft" data-testid="doctor-dashboard-loading">Loading your day…</p>;

  const s = data.stats;

  return (
    <div className="space-y-8 fade-up" data-testid="doctor-dashboard-page">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Good day, {user.name?.split(" ").slice(-1)[0]}</h1>
        <p className="text-ink-soft mt-1">
          {s.today === 0 ? "No visits booked for today." : `${s.today} visit${s.today === 1 ? "" : "s"} today`}
          {s.needs_briefing > 0 && ` · ${s.needs_briefing} without a briefing`}
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat icon={Users} label="My patients" value={s.patients} testid="stat-patients" />
        <Stat icon={CalendarClock} label="Visits this week" value={s.this_week} testid="stat-week" />
        <Stat icon={Sparkles} label="Briefings to write" value={s.needs_briefing}
          tone={s.needs_briefing ? "alert" : ""} testid="stat-needs-briefing" />
        <Stat icon={ShieldCheck} label="Awaiting signature" value={s.awaiting_signature}
          tone={s.awaiting_signature ? "alert" : ""} testid="stat-awaiting-signature" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 space-y-6">
          <DayView visits={data.todays_visits} onOpen={open}
            action={<Link to="/doctor/schedule" data-testid="dash-schedule-link" className="btn-outline !py-1.5 !px-3 text-xs">Full schedule</Link>} />

          <Panel title="Later this week" icon={CalendarClock} items={data.upcoming_visits} onOpen={open}
            testid="dash-today" empty="Nothing else booked this week." />

          <Panel title="Needs a briefing" icon={Sparkles} items={data.needs_briefing} onOpen={open}
            testid="dash-needs-briefing" empty="Every visit this week has a briefing." />

          <Panel title="Awaiting your signature" icon={ShieldCheck} items={data.awaiting_signature} onOpen={open}
            testid="dash-awaiting-signature" empty="No drafts waiting on you." />

          <Panel title="Waiting on patients" icon={ClipboardList} items={data.awaiting_intake} onOpen={open}
            testid="dash-awaiting-intake" empty="No outstanding intake questionnaires." />
        </div>

        <div className="space-y-6">
          <AlertGroups groups={data.alert_groups || []} onCleared={load} />

          <div className="card p-6" data-testid="dash-recent-runs">
            <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
              <Activity className="h-4 w-4 text-forest" /> Recent AI activity
            </h2>
            {data.recent_runs.length === 0 && <p className="text-sm text-ink-soft">No agent runs yet.</p>}
            <div className="space-y-2">
              {data.recent_runs.map((r) => (
                <div key={r.agent_run_id} className="text-sm flex items-center gap-2" data-testid={`dash-run-${r.agent_run_id}`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${r.status === "success" ? "bg-forest" : "bg-terracotta"}`} />
                  <span className="font-medium">{r.agent_type.replace("_", " ")}</span>
                  <span className="text-ink-soft text-xs truncate">
                    {r.patient_name || "—"} · {Math.round(r.latency_ms / 1000)}s ·{" "}
                    {new Date(r.created_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <Link to="/doctor/patients" data-testid="dash-patients-link" className="btn-primary w-full justify-center">
            <Users className="h-4 w-4" /> Open patient list
          </Link>
        </div>
      </div>
    </div>
  );
}
