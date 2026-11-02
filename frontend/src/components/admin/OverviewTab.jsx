import React from "react";
import { Users, Stethoscope, CalendarCheck, FileSignature, ClipboardList, Database, UserPlus, CheckCircle2, Circle } from "lucide-react";

const Kpi = ({ icon: Icon, label, value, sub, testid }) => (
  <div className="card p-5" data-testid={testid}>
    <div className="flex items-center gap-2 text-ink-soft text-xs font-semibold uppercase tracking-wider"><Icon className="h-4 w-4 text-forest" /> {label}</div>
    <p className="text-3xl font-bold mt-2 tabular-nums">{value}</p>
    {sub && <p className="text-xs text-ink-soft mt-1">{sub}</p>}
  </div>
);

const PersonList = ({ title, people, testid, empty }) => (
  <div className="card p-5" data-testid={testid}>
    <h3 className="font-semibold mb-3">{title}</h3>
    {people.length === 0 && <p className="text-sm text-ink-soft">{empty}</p>}
    <ul className="divide-y divide-line">
      {people.map((p) => (
        <li key={p.user_id} className="py-2.5 flex items-center gap-3">
          <span className="h-8 w-8 rounded-full bg-sage/40 text-forest flex items-center justify-center text-xs font-bold">{(p.name || "?").charAt(0).toUpperCase()}</span>
          <span className="min-w-0 flex-1"><span className="block text-sm font-medium truncate">{p.name}</span><span className="block text-xs text-ink-soft truncate">{p.email}</span></span>
          {p.role && <span className="text-[11px] text-ink-soft capitalize">{p.account_role === "account_admin" ? "Hospital admin" : p.role}</span>}
        </li>
      ))}
    </ul>
  </div>
);

export function OverviewTab({ overview }) {
  const o = overview;
  const pct = Math.round((o.checklist_done / o.checklist.length) * 100);
  return (
    <div className="space-y-6" data-testid="account-overview-tab">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi icon={Users} label="Customers" value={o.customer_count} sub={`+${o.new_customers_30d} in the last 30 days`} testid="kpi-customers" />
        <Kpi icon={Stethoscope} label="Staff" value={o.staff_count} sub={`${o.doctor_count} doctors · ${o.account_admin_count} hospital admins`} testid="kpi-staff" />
        <Kpi icon={CalendarCheck} label="Visits" value={o.visits} sub={`${o.visits_30d} in the last 30 days`} testid="kpi-visits" />
        <Kpi icon={FileSignature} label="Prescriptions" value={o.prescriptions} testid="kpi-prescriptions" />
        <Kpi icon={ClipboardList} label="AI screenings" value={o.screenings} testid="kpi-screenings" />
        <Kpi icon={Database} label="Imported records" value={o.imported_records} sub="patient history brought in by CSV" testid="kpi-imported" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <PersonList title="Staff" people={o.recent_staff} testid="overview-staff-list" empty="No staff yet — invite the first doctor." />
        <PersonList title="Newest customers" people={o.recent_customers} testid="overview-customers-list" empty="No customers yet." />
        <div className="card p-5" data-testid="overview-onboarding">
          <div className="flex items-center justify-between mb-2"><h3 className="font-semibold">Onboarding</h3><span className="text-sm font-semibold text-forest">{pct}%</span></div>
          <div className="h-2 bg-sand rounded-full overflow-hidden mb-4"><div className="h-full bg-forest rounded-full" style={{ width: `${pct}%`, transition: "width 0.4s ease" }} /></div>
          <ChecklistItems items={o.checklist} />
        </div>
      </div>
    </div>
  );
}

export const ChecklistItems = ({ items }) => (
  <ul className="space-y-2">
    {items.map((c) => (
      <li key={c.key} className="flex items-start gap-2 text-sm" data-testid={`checklist-${c.key}`} data-done={c.done}>
        {c.done ? <CheckCircle2 className="h-4 w-4 text-forest mt-0.5 shrink-0" /> : <Circle className="h-4 w-4 text-line mt-0.5 shrink-0" />}
        <span className={c.done ? "text-ink" : "text-ink-soft"}>{c.label}</span>
      </li>
    ))}
  </ul>
);

export { UserPlus };
