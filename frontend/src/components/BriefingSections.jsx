import React from "react";
import { LineChart, Line, ResponsiveContainer } from "recharts";
import { AlertTriangle, ShieldAlert, ListChecks, HelpCircle, Pill } from "lucide-react";

const METRIC_LABELS = {
  heart_rate: "Heart rate",
  systolic: "Systolic BP",
  diastolic: "Diastolic BP",
  glucose: "Blood glucose",
  spo2: "Oxygen saturation",
  temperature: "Body temperature",
};

export function resolveMetricKey(name = "") {
  const n = name.toLowerCase().replace(/\s+/g, "_");
  const keys = Object.keys(METRIC_LABELS);
  return (
    keys.find((k) => k === n) ||
    keys.find((k) => METRIC_LABELS[k].toLowerCase().replace(/\s+/g, "_") === n) ||
    keys.find((k) => n.includes(k.split("_")[0])) ||
    null
  );
}

export function Editable({ value, onChange, readOnly, testid, multiline, className = "" }) {
  if (readOnly) return <span className={className}>{value}</span>;
  const Tag = multiline ? "textarea" : "input";
  return (
    <Tag
      value={value || ""}
      data-testid={testid}
      onChange={(e) => onChange(e.target.value)}
      rows={multiline ? 3 : undefined}
      className={`w-full bg-transparent border border-transparent hover:border-line focus:border-sage rounded-lg px-2 py-1 outline-none ${className}`}
    />
  );
}

export function ConcernsCard({ concerns, onEdit, readOnly }) {
  return (
    <div className="card p-6" id="sect-alerts" data-testid="briefing-concerns">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <ShieldAlert className="h-4 w-4 text-terracotta" /> Chief Concerns
      </h3>
      {concerns.length === 0 && <p className="text-sm text-ink-soft">No concerns surfaced from the record.</p>}
      <div className="space-y-3">
        {concerns.map((c, i) => (
          <div
            key={i}
            className={`border rounded-xl px-4 py-3 ${
              c.priority === "high" ? "border-terracotta/40 bg-terracotta/5" : "border-line"
            }`}
            data-testid={`concern-${i}`}
          >
            <span
              className={`text-[10px] uppercase tracking-wider font-bold ${
                c.priority === "high" ? "text-terracotta" : "text-ink-soft"
              }`}
            >
              {c.priority} priority
            </span>
            <div className="font-medium text-sm mt-0.5">
              <Editable value={c.concern} readOnly={readOnly} testid={`concern-text-${i}`}
                onChange={(v) => onEdit(i, "concern", v)} />
            </div>
            <div className="text-xs text-ink-soft mt-1">
              <Editable value={c.evidence} readOnly={readOnly} multiline testid={`concern-evidence-${i}`}
                onChange={(v) => onEdit(i, "evidence", v)} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function VitalsCard({ vitals, series }) {
  return (
    <div className="card p-6" id="sect-vitals" data-testid="briefing-vitals">
      <h3 className="text-lg font-semibold mb-4">Vitals Summary</h3>
      {vitals.length === 0 && <p className="text-sm text-ink-soft">No vitals in the last 90 days.</p>}
      <div className="space-y-3">
        {vitals.map((v, i) => {
          const key = resolveMetricKey(v.metric);
          const data = key ? series.filter((d) => d[key] != null) : [];
          return (
            <div key={i} className="flex items-center gap-4 border border-line rounded-xl px-4 py-3"
              data-testid={`vital-row-${i}`}>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">{v.metric}</p>
                <p className="text-xs text-ink-soft">{v.current} · {v.note}</p>
              </div>
              <span className={`text-[10px] uppercase tracking-wider font-bold ${
                v.trend === "worsening" ? "text-terracotta" : "text-ink-soft"}`}>
                {v.trend}
              </span>
              <div className="w-24 h-10">
                {data.length > 1 && (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data}>
                      <Line type="monotone" dataKey={key} stroke="#1E3F2A" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function MedicationsCard({ meds }) {
  return (
    <div className="card p-6" id="sect-medications" data-testid="briefing-medications">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Pill className="h-4 w-4 text-forest" /> Medication Review
      </h3>
      {meds.length === 0 && <p className="text-sm text-ink-soft">No active medications on record.</p>}
      <div className="space-y-3">
        {meds.map((m, i) => (
          <div key={i} className="border border-line rounded-xl px-4 py-3" data-testid={`med-row-${i}`}>
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium">{m.medication}</p>
              <span className={`text-[10px] uppercase tracking-wider font-bold ${
                m.flag === "low_adherence" ? "text-terracotta" : "text-ink-soft"}`}>
                {m.flag?.replace("_", " ")}
              </span>
            </div>
            {m.adherence_pct != null && (
              <div className="mt-2 h-1.5 bg-sand rounded-full overflow-hidden">
                <div
                  className={`h-full ${m.adherence_pct < 80 ? "bg-terracotta" : "bg-forest"}`}
                  style={{ width: `${Math.min(100, m.adherence_pct)}%` }}
                />
              </div>
            )}
            <p className="text-xs text-ink-soft mt-1.5">
              {m.adherence_pct != null ? `${m.adherence_pct}% adherence · ` : ""}{m.note}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ListCard({ title, icon, items, onChange, readOnly, testid, muted }) {
  const Icon = icon;
  return (
    <div className="card p-6" data-testid={testid}>
      <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
        <Icon className={`h-4 w-4 ${muted ? "text-ink-soft" : "text-forest"}`} /> {title}
      </h3>
      {readOnly ? (
        <ul className="space-y-2 text-sm text-ink-soft list-disc pl-5">
          {items.length === 0 && <li>None recorded.</li>}
          {items.map((it, i) => <li key={i}>{it}</li>)}
        </ul>
      ) : (
        <textarea
          value={items.join("\n")}
          data-testid={`${testid}-editor`}
          onChange={(e) => onChange(e.target.value.split("\n"))}
          rows={Math.max(3, items.length + 1)}
          className="w-full text-sm bg-transparent border border-line rounded-lg px-3 py-2 outline-none focus:border-sage"
        />
      )}
    </div>
  );
}

export function InteractionCard({ reference }) {
  if (!reference) return null;
  return (
    <div className="card p-6" id="sect-interactions" data-testid="briefing-interactions">
      <h3 className="text-lg font-semibold mb-1 flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-terracotta" /> Interaction Flags
      </h3>
      <p className="text-xs text-ink-soft mb-4">
        Reference lookup only — source: {reference.source} ({reference.version}). Not a clinical assessment.
      </p>
      {(reference.flags || []).length === 0 ? (
        <p className="text-sm text-ink-soft">No pairs from this patient's active medications appear in the table.</p>
      ) : (
        <div className="space-y-2">
          {reference.flags.map((f, i) => (
            <div key={i} className="border border-line rounded-xl px-4 py-3" data-testid={`interaction-${i}`}>
              <p className="text-sm font-medium">{f.drug_a} + {f.drug_b}</p>
              <p className="text-xs text-ink-soft">{f.severity} · {f.note}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export const ICONS = { ListChecks, HelpCircle };
