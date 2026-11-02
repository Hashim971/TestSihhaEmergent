import React from "react";
import { TrendingUp, TrendingDown, AlertTriangle, CheckCircle2, Activity, Minus } from "lucide-react";
import { useLang } from "../context/LanguageContext";

const STYLE = {
  above_limit: { cls: "border-terracotta/40 bg-terracotta/5", badge: "bg-terracotta text-white", icon: AlertTriangle, label: "Above limit" },
  below_limit: { cls: "border-terracotta/40 bg-terracotta/5", badge: "bg-terracotta text-white", icon: AlertTriangle, label: "Below limit" },
  rising: { cls: "border-amber-300 bg-amber-50", badge: "bg-amber-500 text-white", icon: TrendingUp, label: "Trending up" },
  falling: { cls: "border-amber-300 bg-amber-50", badge: "bg-amber-500 text-white", icon: TrendingDown, label: "Trending down" },
  ok: { cls: "border-line bg-white", badge: "bg-sage/30 text-forest", icon: CheckCircle2, label: "Within limits" },
  no_data: { cls: "border-line bg-sand/40", badge: "bg-sand text-ink-soft border border-line", icon: Minus, label: "No data" },
};

export function VitalTrends({ data, testid = "vital-trends", footer, audience = "patient" }) {
  const { lang } = useLang();
  if (!data) return null;
  const flagged = data.trends.filter((t) => t.severity).length;
  return (
    <div className="card p-6" data-testid={testid}>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <h2 className="text-lg font-semibold flex items-center gap-2"><Activity className="h-4 w-4 text-forest" /> Vitals trends</h2>
        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${flagged ? "bg-terracotta/10 text-terracotta" : "bg-sage/30 text-forest"}`} data-testid={`${testid}-summary`}>
          {flagged ? (lang === "ar" ? `${flagged} تحتاج إلى انتباه` : `${flagged} need attention`) : "All within limits"}
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {data.trends.map((t) => <TrendCard key={t.metric} t={t} ar={lang === "ar"} audience={audience} testid={`${testid}-${t.metric}`} />)}
      </div>
      <p className="text-xs text-ink-soft mt-3">{audience === "doctor"
        ? "Compares the last 7 days with the 7 before. The patient and their assigned doctor get an alert and email when a warning starts."
        : "Compares the last 7 days with the 7 before. Warnings are a prompt to check in with your doctor, not a diagnosis."}</p>
      {footer}
    </div>
  );
}

function TrendCard({ t, testid, ar, audience }) {
  const s = STYLE[t.status];
  const Icon = s.icon;
  return (
    <div className={`rounded-xl border p-4 ${s.cls}`} data-testid={testid}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold">{ar ? t.label_ar : t.label}</p>
        <span className={`shrink-0 inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full ${s.badge}`} data-testid={`${testid}-status`}>
          <Icon className="h-3 w-3" /> {s.label}
        </span>
      </div>
      <p className="text-2xl font-bold mt-2">
        {t.recent_avg ?? "—"} <span className="text-xs font-medium text-ink-soft">{t.unit} · 7-day avg</span>
      </p>
      {t.change != null && (
        <p className="text-xs text-ink-soft"><bdi>{t.change > 0 ? `+${t.change}` : t.change}</bdi> vs previous week</p>
      )}
      <Sparkline series={t.series} limit={t.limit} />
      <p className="text-xs mt-2" data-testid={`${testid}-message`}>{ar ? t.message_ar : t.message}</p>
      <p className="text-[11px] text-ink-soft mt-2">
        Limit <bdi>{t.limit.min}–{t.limit.max} {t.unit}</bdi> · {t.limit_source === "doctor" ? (audience === "doctor" ? "custom for this patient" : "set by your doctor") : "standard"}
      </p>
    </div>
  );
}

function Sparkline({ series, limit }) {
  if (series.length < 2) return null;
  const vals = series.map((p) => p.value);
  const lo = Math.min(...vals, limit.min) - 5;
  const hi = Math.max(...vals, limit.max) + 5;
  const y = (v) => 40 - ((v - lo) / (hi - lo)) * 40;
  const pts = vals.map((v, i) => `${(i / (vals.length - 1)) * 100},${y(v)}`).join(" ");
  return (
    <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="w-full h-10 mt-2" aria-hidden="true">
      <line x1="0" x2="100" y1={y(limit.max)} y2={y(limit.max)} stroke="#C2410C" strokeDasharray="2 2" strokeWidth="0.6" />
      <polyline points={pts} fill="none" stroke="#1F4D3A" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
