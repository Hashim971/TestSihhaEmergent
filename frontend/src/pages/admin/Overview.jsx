import React, { useEffect, useState } from "react";
import { Users, Activity, Building2, Store } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "../../lib/api";

const ROLES = [["patient", "Patients"], ["doctor", "Doctors"], ["pharmacist", "Pharmacy staff"]];

export default function AdminOverview() {
  const [s, setS] = useState(null);
  useEffect(() => { api.get("/admin/platform-stats").then(({ data }) => setS(data)).catch(() => setS(false)); }, []);
  if (s === null) return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" data-testid="admin-overview-loading">
      {[0, 1, 2, 3].map((i) => <div key={i} className="card h-28 animate-pulse bg-sand/60" />)}
    </div>
  );
  if (s === false) return <p className="text-sm text-terracotta">Could not load platform numbers.</p>;
  const t = s.totals;
  return (
    <div className="space-y-8 fade-up" data-testid="admin-overview-page">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Platform overview</h1>
        <p className="text-ink-soft mt-1">Who is using Sihha AI right now. "Active" means signed in or used the app in the period. Demo and test accounts are not counted.</p>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat icon={Activity} label="Active, last 30 days" value={t.active_month} sub={<><bdi>{t.active_week}</bdi> {"this week"} · <bdi>{t.active_today}</bdi> {"today"}</>} testid="stat-active-month" accent />
        <Stat icon={Users} label="Users in good standing" value={t.in_good_standing} sub={<><bdi>{t.total}</bdi> {"users in total"}</>} testid="stat-good-standing" />
        <Stat icon={Building2} label="Hospitals not suspended" value={s.accounts.not_suspended} sub={<><bdi>{s.accounts.total}</bdi> {"hospital accounts"}</>} testid="stat-accounts" />
        <Stat icon={Store} label="Active pharmacies" value={s.pharmacies} testid="stat-pharmacies" />
      </div>

      <div className="card p-6" data-testid="daily-active-chart">
        <h2 className="text-lg font-semibold">Daily active users — last 30 days</h2>
        <div className="h-56 mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={s.daily_active}>
              <XAxis dataKey="day" tickFormatter={(d) => d.slice(5)} tick={{ fontSize: 10 }} interval={4} />
              <YAxis allowDecimals={false} tick={{ fontSize: 10 }} width={28} />
              <Tooltip />
              <Bar dataKey="active" fill="#1F4D3A" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="text-xs text-ink-soft mt-2">Activity tracking started with this release, so earlier days show zero.</p>
      </div>

      <div className="card overflow-x-auto" data-testid="active-by-role">
        <table className="w-full text-sm min-w-[560px]">
          <thead className="text-xs uppercase tracking-[0.12em] text-ink-soft bg-sand/60">
            <tr><th className="text-start p-3">Role</th><th className="text-end p-3">Today</th><th className="text-end p-3">Last 7 days</th><th className="text-end p-3">Last 30 days</th><th className="text-end p-3">Good standing</th><th className="text-end p-3">Total</th></tr>
          </thead>
          <tbody className="divide-y divide-line">
            {ROLES.map(([k, label]) => {
              const r = s.roles[k];
              return (
                <tr key={k} data-testid={`role-row-${k}`}>
                  <td className="p-3 font-medium">{label}</td>
                  <td className="p-3 text-end">{r.active_today}</td><td className="p-3 text-end">{r.active_week}</td>
                  <td className="p-3 text-end font-semibold">{r.active_month}</td><td className="p-3 text-end">{r.in_good_standing}</td>
                  <td className="p-3 text-end text-ink-soft">{r.total}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const Stat = ({ icon: Icon, label, value, sub, testid, accent }) => (
  <div className={`card p-5 ${accent ? "!bg-forest text-white !border-forest" : ""}`} data-testid={testid}>
    <p className={`text-xs flex items-center gap-1.5 ${accent ? "text-white/80" : "text-ink-soft"}`}><Icon className="h-3.5 w-3.5" /> {label}</p>
    <p className="text-3xl font-bold mt-2"><bdi>{value}</bdi></p>
    {sub && <p className={`text-xs mt-1 ${accent ? "text-white/70" : "text-ink-soft"}`}>{sub}</p>}
  </div>
);
