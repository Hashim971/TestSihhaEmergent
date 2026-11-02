import { useEffect, useState } from "react";
import { api } from "../../lib/api";

export const fmtMs = (ms) => {
  if (!ms) return "—";
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return m < 60 ? `${m}m ${s % 60}s` : `${Math.floor(m / 60)}h ${m % 60}m`;
};

export function useAnalytics(endpoint, filters, extra = {}) {
  const [data, setData] = useState(null);
  const key = JSON.stringify({ ...filters, ...extra });
  useEffect(() => {
    let live = true;
    setData(null);
    api.get(`/admin/analytics/${endpoint}`, { params: { ...filters, ...extra } })
      .then(({ data }) => live && setData(data)).catch(() => live && setData(false));
    return () => { live = false; };
    // eslint-disable-next-line
  }, [endpoint, key]);
  return data;
}

export const Empty = ({ children, testid }) => (
  <div className="card p-10 text-center text-sm text-ink-soft" data-testid={testid}>{children}</div>
);

export const Loading = () => (
  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">{[0, 1, 2, 3].map((i) => <div key={i} className="card h-24 animate-pulse bg-sand/60" />)}</div>
);
