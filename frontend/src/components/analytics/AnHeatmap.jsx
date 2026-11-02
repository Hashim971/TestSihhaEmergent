import React, { useEffect, useRef, useState } from "react";
import { Replayer } from "rrweb";
import "rrweb/dist/style.css";
import { Monitor, Smartphone } from "lucide-react";
import { api } from "../../lib/api";
import { useAnalytics, Loading, Empty } from "./shared";
import { inputCls } from "../admin/ui";

export function AnHeatmap({ filters, params, go }) {
  const summary = useAnalytics("summary", filters);
  const [device, setDevice] = useState("desktop");
  const path = params.get("path") || summary?.pages?.[0]?.path || "";
  const heat = useAnalytics("heatmap", filters, { path, device });
  if (summary === null) return <Loading />;
  if (!summary || !summary.pages.length) return <Empty testid="an-heatmap-empty">No pages visited in this period.</Empty>;

  return (
    <div className="space-y-4" data-testid="analytics-heatmap">
      <div className="flex flex-wrap items-center gap-3">
        <select value={path} onChange={(e) => go("heatmaps", { path: e.target.value })} className={`${inputCls} !w-auto font-mono`} data-testid="an-heatmap-page-select">
          {summary.pages.map((p) => <option key={p.path} value={p.path}>{p.path} ({p.clicks} clicks)</option>)}
        </select>
        <div className="inline-flex rounded-full border border-line bg-white p-1">
          {[["desktop", Monitor], ["mobile", Smartphone]].map(([d, Icon]) => (
            <button key={d} onClick={() => setDevice(d)} data-testid={`an-heatmap-device-${d}`}
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium capitalize ${device === d ? "bg-forest text-white" : "text-ink-soft"}`}>
              <Icon className="h-3.5 w-3.5" /> {d}
            </button>
          ))}
        </div>
        {heat && <span className="text-xs text-ink-soft" data-testid="an-heatmap-count">{heat.points.length} taps</span>}
      </div>
      {heat === null ? <Loading /> : heat === false ? <Empty>Could not load the heatmap.</Empty> : (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
          <div className="xl:col-span-3"><HeatCanvas heat={heat} device={device} /></div>
          <div className="card p-4" data-testid="an-heatmap-targets">
            <h3 className="text-sm font-semibold mb-3">Most tapped</h3>
            {heat.top_targets.length === 0 ? <p className="text-sm text-ink-soft">No taps yet.</p> : (
              <ol className="space-y-1.5 text-xs">
                {heat.top_targets.map((t) => (
                  <li key={t.target} className="flex justify-between gap-2"><span className="font-mono truncate">{t.target}</span><b>{t.clicks}</b></li>
                ))}
              </ol>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function HeatCanvas({ heat, device }) {
  const wrap = useRef(null);
  const shot = useRef(null);
  const canvas = useRef(null);
  const [fit, setFit] = useState(800);
  const vw = heat.snapshot?.vw || (device === "mobile" ? 390 : 1440);
  const dh = Math.max(900, ...heat.points.map((p) => p.y + 80));
  const scale = Math.min(1, fit / vw);

  useEffect(() => {
    const measure = () => wrap.current && setFit(wrap.current.clientWidth);
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  useEffect(() => { drawHeat(canvas.current, heat.points, vw, dh); }, [heat, vw, dh]);

  useEffect(() => {
    const snap = heat.snapshot;
    if (!snap || !shot.current) return undefined;
    let replayer;
    let live = true;
    shot.current.innerHTML = "";
    api.get(`/admin/analytics/replays/${snap.session_id}`).then(({ data }) => {
      if (!live) return;
      replayer = new Replayer(data.events, { root: shot.current, mouseTail: false, showWarning: false, triggerFocus: false });
      const start = data.events[0].timestamp;
      const end = Math.min(snap.until ? snap.until - 300 : Infinity, data.events[data.events.length - 1].timestamp);
      replayer.pause(Math.max(0, Math.min(snap.t + 8000, end) - start));
      const frame = replayer.iframe;
      frame.setAttribute("width", vw);
      frame.setAttribute("height", dh);
      frame.style.pointerEvents = "none";
    }).catch(() => {});
    return () => { live = false; try { replayer?.destroy(); } catch {} };
  }, [heat, vw, dh]);

  return (
    <div ref={wrap} className="card overflow-hidden" data-testid="an-heatmap-canvas">
      {!heat.snapshot && <p className="text-xs text-ink-soft px-4 py-2 border-b border-line">No recording of this page on {device} yet — showing tap positions only.</p>}
      <div style={{ height: dh * scale, overflow: "hidden" }}>
        <div className="relative bg-sand/40" style={{ width: vw, height: dh, transform: `scale(${scale})`, transformOrigin: "top left" }}>
          <div ref={shot} className="absolute inset-0 [&_.replayer-wrapper]:!transform-none [&_.replayer-wrapper]:!left-0 [&_.replayer-wrapper]:!top-0 [&_.replayer-wrapper]:!float-none [&_.replayer-mouse]:hidden" />
          <canvas ref={canvas} width={vw} height={dh} className="absolute inset-0 pointer-events-none" />
        </div>
      </div>
    </div>
  );
}

function drawHeat(el, points, w, h) {
  if (!el) return;
  const ctx = el.getContext("2d");
  ctx.clearRect(0, 0, w, h);
  const r = 28;
  points.forEach((p) => {
    const x = (p.x / 100) * w;
    const g = ctx.createRadialGradient(x, p.y, 0, x, p.y, r);
    g.addColorStop(0, "rgba(0,0,0,0.35)");
    g.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = g;
    ctx.fillRect(x - r, p.y - r, r * 2, r * 2);
  });
  const img = ctx.getImageData(0, 0, w, h);
  const d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    const a = d[i + 3] / 255;
    if (!a) continue;
    const hue = (1 - Math.min(a * 1.4, 1)) * 240;
    const [rr, gg, bb] = hsl(hue, 1, 0.5);
    d[i] = rr; d[i + 1] = gg; d[i + 2] = bb; d[i + 3] = Math.min(220, 60 + a * 255);
  }
  ctx.putImageData(img, 0, 0);
}

function hsl(h, s, l) {
  const k = (n) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return [f(0) * 255, f(8) * 255, f(4) * 255];
}
