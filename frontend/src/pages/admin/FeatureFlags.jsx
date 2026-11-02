import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FlaskConical } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { Toggle, errorText } from "../../components/admin/ui";

export default function FeatureFlags() {
  const [data, setData] = useState(null);
  useEffect(() => { api.get("/admin/flags").then(({ data }) => setData(data)).catch(() => {}); }, []);

  const set = async (key, enabled) => {
    try {
      setData((await api.put(`/admin/flags/${key}`, { enabled })).data);
      toast.success(`${enabled ? "Switched on" : "Switched off"} for everyone without a custom setting`);
    } catch (e) {
      toast.error(errorText(e));
    }
  };

  if (!data) return <p className="text-sm text-ink-soft">Loading…</p>;

  return (
    <div className="fade-up" data-testid="feature-flags-page">
      <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Feature switches</h1>
      <p className="text-sm text-ink-soft mt-2 mb-8 max-w-2xl">
        Global defaults for every account. Each hospital can override a switch in its Features tab.
        Changes here only affect the {data.is_staging ? "staging" : "production"} environment you're in.
      </p>
      <div className="card divide-y divide-line">
        {data.flags.map((f) => {
          const locked = f.staging_only && !data.is_staging;
          return (
            <div key={f.key} className="px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-3" data-testid={`flag-row-${f.key}`}>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm flex items-center gap-2">{f.label}{f.staging_only && <FlaskConical className="h-3.5 w-3.5 text-amber-600" />}</p>
                <p className="text-xs text-ink-soft">{f.description}</p>
                {f.overrides.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2" data-testid={`flag-overrides-${f.key}`}>
                    {f.overrides.map((o) => (
                      <Link key={o.account_id} to={`/admin/accounts/${o.account_id}?tab=features`}
                        className={`text-[11px] px-2 py-0.5 rounded-md border ${o.enabled ? "bg-emerald-50 border-emerald-200 text-emerald-700" : "bg-red-50 border-red-200 text-red-700"}`}>
                        {o.name}: {o.enabled ? "on" : "off"}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
              <span className="text-xs text-ink-soft font-mono">{f.key}</span>
              <Toggle checked={f.enabled} disabled={locked} onChange={(v) => set(f.key, v)} testid={`flag-toggle-${f.key}`} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
