import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { Toggle, errorText } from "./ui";

export function FeaturesTab({ account, onSaved, isStaging }) {
  const [flags, setFlags] = useState([]);
  useEffect(() => { api.get("/admin/flags").then(({ data }) => setFlags(data.flags)).catch(() => {}); }, []);

  const set = async (key, value) => {
    const features = { ...(account.features || {}) };
    if (value === null) delete features[key];
    else features[key] = value;
    try {
      onSaved((await api.patch(`/admin/accounts/${account.account_id}`, { features })).data);
      toast.success("Features updated");
    } catch (e) {
      toast.error(errorText(e));
    }
  };

  return (
    <div className="card divide-y divide-line" data-testid="account-features-tab">
      {flags.map((f) => {
        const override = account.features?.[f.key];
        const effective = account.effective_flags?.[f.key];
        const locked = f.staging_only && !isStaging;
        return (
          <div key={f.key} className="flex flex-col sm:flex-row sm:items-center gap-3 px-5 py-4" data-testid={`account-feature-${f.key}`}>
            <div className="flex-1 min-w-0">
              <p className="font-medium text-sm">{f.label}</p>
              <p className="text-xs text-ink-soft">{f.description}</p>
            </div>
            <span className="text-[11px] text-ink-soft" data-testid={`account-feature-source-${f.key}`}>
              {override === undefined ? `Uses global (${f.enabled ? "on" : "off"})` : "Custom for this account"}
            </span>
            {override !== undefined && (
              <button onClick={() => set(f.key, null)} data-testid={`account-feature-reset-${f.key}`} className="text-xs underline text-ink-soft">Reset</button>
            )}
            <Toggle checked={!!effective} disabled={locked} onChange={(v) => set(f.key, v)} testid={`account-feature-toggle-${f.key}`} />
          </div>
        );
      })}
    </div>
  );
}
